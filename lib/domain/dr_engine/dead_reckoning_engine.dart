import 'dart:async';
import 'dart:isolate';
import 'dart:typed_data';
import 'package:flutter/services.dart';
import 'package:latlong2/latlong.dart';
import '../../data/models/kinematics.dart';
import 'alignment_calibrator.dart';
import 'kalman_filter.dart';
import 'map_matcher.dart';
import 'onnx_runner.dart';

// Messages for isolate
class InitEngineMsg {
  final SendPort sendPort;
  final RootIsolateToken token;
  InitEngineMsg(this.sendPort, this.token);
}

class UpdateSensorMsg {
  final SensorData data;
  UpdateSensorMsg(this.data);
}

class UpdateGpsMsg {
  final LatLng position;
  final double bearing;
  final double speed;
  UpdateGpsMsg(this.position, this.bearing, this.speed);
}

class SimulateOutageMsg {
  final bool isOutage;
  SimulateOutageMsg(this.isOutage);
}

class CalibrateMountMsg {}

class EngineStateUpdate {
  final LatLng position;
  final double bearing;
  final double speed;
  final double driftMeters;
  final bool isOutage;

  EngineStateUpdate({
    required this.position,
    required this.bearing,
    required this.speed,
    required this.driftMeters,
    required this.isOutage,
  });
}

class DeadReckoningEngine {
  SendPort? _isolateSendPort;
  final ReceivePort _receivePort = ReceivePort();
  Isolate? _isolate;
  
  final void Function(EngineStateUpdate) onUpdate;

  DeadReckoningEngine({required this.onUpdate});

  Future<void> start() async {
    RootIsolateToken rootToken = RootIsolateToken.instance!;
    _isolate = await Isolate.spawn(_engineEntry, InitEngineMsg(_receivePort.sendPort, rootToken));
    
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

  void feedSensorData(SensorData data) {
    _isolateSendPort?.send(UpdateSensorMsg(data));
  }

  void feedGpsData(LatLng position, double bearing, double speed) {
    _isolateSendPort?.send(UpdateGpsMsg(position, bearing, speed));
  }

  void setSimulateOutage(bool isOutage) {
    _isolateSendPort?.send(SimulateOutageMsg(isOutage));
  }

  void calibrateMount() {
    _isolateSendPort?.send(CalibrateMountMsg());
  }

  // --- Isolate Entry Point ---
  static void _engineEntry(InitEngineMsg initMsg) async {
    BackgroundIsolateBinaryMessenger.ensureInitialized(initMsg.token);
    
    final receivePort = ReceivePort();
    initMsg.sendPort.send(receivePort.sendPort);

    // Initialize modules
    final calibrator = AlignmentCalibrator();
    final kf = KalmanFilter();
    final mapMatcher = MapMatcher();
    final aiEstimator = OnnxVelocityEstimator();
    
    await mapMatcher.loadMap('assets/maps/sample_road_network.json');
    await aiEstimator.init();

    bool isOutage = false;
    double driftMeters = 0.0;
    LatLng startOutagePos = const LatLng(0, 0);
    
    int lastTime = DateTime.now().millisecondsSinceEpoch;
    int lastGpsTime = DateTime.now().millisecondsSinceEpoch;

    // AI sliding window (6 channels, 100 samples)
    List<double> imuWindow = [];

    receivePort.listen((message) {
      int now = DateTime.now().millisecondsSinceEpoch;
      double dt = (now - lastTime) / 1000.0;
      lastTime = now;

      // Seamless Deficit Handler: Auto-outage if GPS lost for >1.0s
      if (!isOutage && (now - lastGpsTime > 1000) && kf.lat != 0) {
        isOutage = true;
        startOutagePos = kf.position;
        driftMeters = 0.0;
      }

      if (message is CalibrateMountMsg) {
        calibrator.forceCalibration();
      } else if (message is UpdateGpsMsg) {
        lastGpsTime = now;
        if (!isOutage) {
          if (kf.lat == 0) { // first fix
            kf.initState(message.position, message.bearing, message.speed);
          } else {
            kf.updateGNSS(message.position, message.bearing, message.speed);
          }
          driftMeters = 0.0;
          
          initMsg.sendPort.send(EngineStateUpdate(
            position: kf.position,
            bearing: kf.bearing,
            speed: kf.speed,
            driftMeters: driftMeters,
            isOutage: isOutage,
          ));
        } else {
          // Smoothly transition from Outage back to GNSS
          kf.updateGNSS(message.position, message.bearing, message.speed);
          isOutage = false;
          driftMeters = 0.0;
        }
      } else if (message is UpdateSensorMsg) {
        // 1. Calibrate / Project to vehicle frame
        calibrator.feedSensor(message.data.accelX, message.data.accelY, message.data.accelZ);
        List<double> vAccel = calibrator.projectToVehicleFrame(message.data.accelX, message.data.accelY, message.data.accelZ);
        List<double> vGyro = calibrator.projectToVehicleFrame(message.data.gyroX, message.data.gyroY, message.data.gyroZ);
        
        // Use vehicle Forward Accel (X-axis) and Yaw Rate (Z-axis)
        double forwardAccel = vAccel[0];
        double yawRate = vGyro[2];

        // Append to sliding window (normalized)
        imuWindow.addAll([vAccel[0], vAccel[1], vAccel[2], vGyro[0], vGyro[1], vGyro[2]]);
        if (imuWindow.length > 600) {
          imuWindow.removeRange(0, 6);
        }

        if (kf.lat != 0) {
          // 2. Predict step
          kf.predict(dt, forwardAccel, yawRate);

          if (isOutage) {
            // 3. AI Dead Reckoning Update & NHC Constraint
            if (imuWindow.length == 600) {
              Float32List tensorData = Float32List.fromList(imuWindow);
              double aiVelocity = aiEstimator.estimateVelocity(tensorData);
              kf.updateAI(aiVelocity);
            }

            // 4. Offline Map Matching Snapping
            LatLng snappedPos = mapMatcher.snapToMap(kf.position, kf.bearing);
            kf.lat = snappedPos.latitude;
            kf.lon = snappedPos.longitude;

            // Compute drift
            final Distance distance = const Distance();
            driftMeters = distance.as(LengthUnit.Meter, startOutagePos, kf.position);

            initMsg.sendPort.send(EngineStateUpdate(
              position: kf.position,
              bearing: kf.bearing,
              speed: kf.speed,
              driftMeters: driftMeters,
              isOutage: isOutage,
            ));
          }
        }
      } else if (message is SimulateOutageMsg) {
        if (message.isOutage && !isOutage) {
          isOutage = true;
          startOutagePos = kf.position;
          driftMeters = 0.0;
        } else if (!message.isOutage) {
          isOutage = false;
        }
      }
    });
  }
}
