import 'dart:async';
import 'dart:isolate';
import 'package:flutter/services.dart';
import 'package:latlong2/latlong.dart';
import '../../data/models/kinematics.dart';
import 'idr_core.dart';
import 'idr_nav.dart';
import 'map_matcher.dart';
import 'onnx_runner.dart';

// ---- Messages (UI isolate -> engine isolate) ----
class InitEngineMsg {
  final SendPort sendPort;
  final RootIsolateToken token;
  final Uint8List modelBytes;
  final String roadsJson;
  InitEngineMsg(this.sendPort, this.token, this.modelBytes, this.roadsJson);
}

class UpdateSensorMsg {
  final SensorData data;
  UpdateSensorMsg(this.data);
}

class UpdateGpsMsg {
  final LatLng position;
  final double bearing;
  final double speed;
  final double accuracy;
  UpdateGpsMsg(this.position, this.bearing, this.speed, this.accuracy);
}

class SimulateOutageMsg {
  final bool isOutage;
  SimulateOutageMsg(this.isOutage);
}

class CalibrateMountMsg {}

class ResetMsg {}

// ---- Engine -> UI ----
class EngineStateUpdate {
  final LatLng position;
  final double bearing;
  final double speed;
  final double outageDistance;
  final bool isOutage;
  final bool calibrated; // forward + yaw axes learned from GNSS
  EngineStateUpdate({
    required this.position,
    required this.bearing,
    required this.speed,
    required this.outageDistance,
    required this.isOutage,
    required this.calibrated,
  });
}

/// Runs the whole IDR stack (features, calibration, DRNet via ONNX, navigation) in a background
/// isolate at 10 Hz. Raw phone sensors arrive at ~50 Hz and are averaged into 10 Hz samples.
class DeadReckoningEngine {
  SendPort? _isolateSendPort;
  final ReceivePort _receivePort = ReceivePort();
  Isolate? _isolate;
  final void Function(EngineStateUpdate) onUpdate;

  DeadReckoningEngine({required this.onUpdate});

  Future<void> start() async {
    final rootToken = RootIsolateToken.instance!;
    // Assets are read here: rootBundle does not exist inside a background isolate.
    final model = (await rootBundle.load('assets/dr_net.onnx')).buffer.asUint8List();
    final roads = await rootBundle.loadString('assets/maps/road_network.json');
    _isolate = await Isolate.spawn(_engineEntry, InitEngineMsg(_receivePort.sendPort, rootToken, model, roads));
    _receivePort.listen((message) {
      if (message is SendPort) {
        _isolateSendPort = message;
      } else if (message is EngineStateUpdate) {
        onUpdate(message);
      }
    });
  }

  void stop() {
    _receivePort.close();
    _isolate?.kill(priority: Isolate.immediate);
  }

  void feedSensorData(SensorData data) => _isolateSendPort?.send(UpdateSensorMsg(data));
  void feedGpsData(LatLng position, double bearing, double speed, [double accuracy = 5.0]) =>
      _isolateSendPort?.send(UpdateGpsMsg(position, bearing, speed, accuracy));
  void setSimulateOutage(bool isOutage) => _isolateSendPort?.send(SimulateOutageMsg(isOutage));
  void calibrateMount() => _isolateSendPort?.send(CalibrateMountMsg());
  void reset() => _isolateSendPort?.send(ResetMsg());

  static const double _maxFixAccuracyM = 50.0;
  static const bool _enableMapMatching = false; // see Sense-Path-Docs.md (not yet shown to help)

  static void _engineEntry(InitEngineMsg init) async {
    BackgroundIsolateBinaryMessenger.ensureInitialized(init.token);
    final receivePort = ReceivePort();
    init.sendPort.send(receivePort.sendPort);

    final runner = DrStepRunner()..init(init.modelBytes);
    final mapMatcher = MapMatcher()..loadFromString(init.roadsJson);

    var nav = IdrNav(runner);
    var forcedOutage = false;
    var tick = 0; // virtual 10 Hz clock: deterministic and independent of replay speed

    // 50 Hz -> 10 Hz binning (live sensors only)
    final accSum = [0.0, 0.0, 0.0], gyroSum = [0.0, 0.0, 0.0];
    var binCount = 0;
    var lastBinMs = DateTime.now().millisecondsSinceEpoch;

    void emit(NavOutput o) {
      var pos = LatLng(o.lat, o.lon);
      if (_enableMapMatching && o.inOutage) {
        pos = mapMatcher.snapToMap(pos, o.bearingDeg);
        nav.lat = pos.latitude;
        nav.lon = pos.longitude;
      }
      init.sendPort.send(EngineStateUpdate(
        position: pos,
        bearing: o.bearingDeg,
        speed: o.speed,
        outageDistance: o.outageDistance,
        isOutage: o.inOutage,
        calibrated: nav.core.canDeadReckon,
      ));
    }

    void processSample(List<double> acc, List<double> gyro) {
      final o = nav.onImu(acc, gyro, tick * kDt);
      tick++;
      if (o != null) emit(o);
    }

    receivePort.listen((message) {
      if (message is UpdateGpsMsg) {
        if (forcedOutage || message.accuracy > _maxFixAccuracyM) return; // unusable fix
        nav.onGnss(message.position.latitude, message.position.longitude, message.bearing, message.speed, tick * kDt);
      } else if (message is UpdateSensorMsg) {
        final d = message.data;
        if (d.preBinned) {
          processSample([d.accelX, d.accelY, d.accelZ], [d.gyroX, d.gyroY, d.gyroZ]);
          return;
        }
        accSum[0] += d.accelX;
        accSum[1] += d.accelY;
        accSum[2] += d.accelZ;
        gyroSum[0] += d.gyroX;
        gyroSum[1] += d.gyroY;
        gyroSum[2] += d.gyroZ;
        binCount++;
        final now = DateTime.now().millisecondsSinceEpoch;
        if (now - lastBinMs >= 100 && binCount > 0) {
          lastBinMs = now;
          processSample([for (final v in accSum) v / binCount], [for (final v in gyroSum) v / binCount]);
          accSum.fillRange(0, 3, 0.0);
          gyroSum.fillRange(0, 3, 0.0);
          binCount = 0;
        }
      } else if (message is SimulateOutageMsg) {
        forcedOutage = message.isOutage;
        if (forcedOutage) nav.forceOutage();
      } else if (message is CalibrateMountMsg) {
        nav.core.resetCalibration();
      } else if (message is ResetMsg) {
        nav = IdrNav(runner);
        forcedOutage = false;
        tick = 0;
        binCount = 0;
        accSum.fillRange(0, 3, 0.0);
        gyroSum.fillRange(0, 3, 0.0);
      }
    });
  }
}
