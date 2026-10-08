import 'dart:isolate';
import 'package:latlong2/latlong.dart';
import '../../data/models/kinematics.dart';

// Messages for isolate
class InitEngineMsg {
  final SendPort sendPort;
  InitEngineMsg(this.sendPort);
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
  
  // Callback to emit updates to provider
  final void Function(EngineStateUpdate) onUpdate;

  DeadReckoningEngine({required this.onUpdate});

  Future<void> start() async {
    _isolate = await Isolate.spawn(_engineEntry, InitEngineMsg(_receivePort.sendPort));
    
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

  // --- Isolate Entry Point ---
  static void _engineEntry(InitEngineMsg initMsg) {
    final receivePort = ReceivePort();
    initMsg.sendPort.send(receivePort.sendPort);

    // Initial state
    LatLng currentPosition = const LatLng(0, 0);
    double currentBearing = 0.0;
    double currentSpeed = 0.0;
    double driftMeters = 0.0;
    bool isOutage = false;

    // Time tracking for integration
    int lastTime = DateTime.now().millisecondsSinceEpoch;

    receivePort.listen((message) {
      int now = DateTime.now().millisecondsSinceEpoch;
      double dt = (now - lastTime) / 1000.0;
      lastTime = now;

      if (message is UpdateGpsMsg) {
        if (!isOutage) {
          currentPosition = message.position;
          currentBearing = message.bearing;
          currentSpeed = message.speed;
          driftMeters = 0.0; // Reset drift when we have strong GPS
          
          initMsg.sendPort.send(EngineStateUpdate(
            position: currentPosition,
            bearing: currentBearing,
            speed: currentSpeed,
            driftMeters: driftMeters,
            isOutage: isOutage,
          ));
        }
      } else if (message is UpdateSensorMsg) {
        if (isOutage) {
          // Simple Dead Reckoning logic based on IMU
          // (In a real scenario, this involves a Kalman Filter with Matrix math)
          // For demo: Use gyroZ for turn rate, accelY for acceleration
          double turnRate = message.data.gyroZ; // simplified
          double forwardAccel = message.data.accelY; // simplified
          
          currentSpeed += forwardAccel * dt;
          if (currentSpeed < 0) currentSpeed = 0; // No reverse for simplicity
          
          currentBearing += (turnRate * 180 / pi) * dt;
          currentBearing = currentBearing % 360;

          // Calculate new position
          double dist = currentSpeed * dt;
          driftMeters += dist * 0.05; // Simulate cumulative drift (5% error)

          // Haversine approximation to move lat/lng
          final Distance distance = const Distance();
          currentPosition = distance.offset(currentPosition, dist, currentBearing);

          initMsg.sendPort.send(EngineStateUpdate(
            position: currentPosition,
            bearing: currentBearing,
            speed: currentSpeed,
            driftMeters: driftMeters,
            isOutage: isOutage,
          ));
        }
      } else if (message is SimulateOutageMsg) {
        isOutage = message.isOutage;
      }
    });
  }
}
