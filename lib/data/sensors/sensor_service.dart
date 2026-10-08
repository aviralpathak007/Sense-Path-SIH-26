import 'dart:async';
import 'package:sensors_plus/sensors_plus.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import '../models/kinematics.dart';
import '../../domain/dr_engine/dead_reckoning_engine.dart';

class SensorService {
  final DeadReckoningEngine engine;
  StreamSubscription? _accelSub;
  StreamSubscription? _gyroSub;
  StreamSubscription? _gpsSub;

  // Store latest values to combine them
  double _aX = 0, _aY = 0, _aZ = 0;
  
  SensorService(this.engine);

  Future<void> start() async {
    // Check GPS permissions
    bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return;
    }

    LocationPermission permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied) {
        return;
      }
    }
    
    // Start GPS stream
    _gpsSub = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.bestForNavigation,
        distanceFilter: 0,
      )
    ).listen((Position position) {
      engine.feedGpsData(
        LatLng(position.latitude, position.longitude),
        position.heading,
        position.speed,
      );
    });

    // Start IMU streams
    _accelSub = userAccelerometerEventStream(samplingPeriod: SensorInterval.gameInterval).listen((event) {
      _aX = event.x;
      _aY = event.y;
      _aZ = event.z;
    });

    _gyroSub = gyroscopeEventStream(samplingPeriod: SensorInterval.gameInterval).listen((event) {
      engine.feedSensorData(SensorData(
        accelX: _aX,
        accelY: _aY,
        accelZ: _aZ,
        gyroX: event.x,
        gyroY: event.y,
        gyroZ: event.z,
      ));
    });
  }

  void stop() {
    _accelSub?.cancel();
    _gyroSub?.cancel();
    _gpsSub?.cancel();
  }
}
