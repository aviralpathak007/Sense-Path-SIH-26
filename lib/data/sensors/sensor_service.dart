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

  // Latest accelerometer sample (WITH gravity: the IDR core estimates gravity itself).
  double _aX = 0, _aY = 0, _aZ = 9.81;

  SensorService(this.engine);

  Future<void> start() async {
    if (_gpsSub != null || _accelSub != null) return;

    final serviceEnabled = await Geolocator.isLocationServiceEnabled();
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (serviceEnabled && permission != LocationPermission.denied && permission != LocationPermission.deniedForever) {
      _gpsSub = Geolocator.getPositionStream(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.bestForNavigation, distanceFilter: 0),
      ).listen((Position p) {
        engine.feedGpsData(LatLng(p.latitude, p.longitude), p.heading, p.speed, p.accuracy);
      });
    }

    _accelSub = accelerometerEventStream(samplingPeriod: SensorInterval.gameInterval).listen((e) {
      _aX = e.x;
      _aY = e.y;
      _aZ = e.z;
    });
    _gyroSub = gyroscopeEventStream(samplingPeriod: SensorInterval.gameInterval).listen((e) {
      engine.feedSensorData(SensorData(accelX: _aX, accelY: _aY, accelZ: _aZ, gyroX: e.x, gyroY: e.y, gyroZ: e.z));
    });
  }

  void stop() {
    _accelSub?.cancel();
    _gyroSub?.cancel();
    _gpsSub?.cancel();
    _accelSub = _gyroSub = _gpsSub = null;
  }
}
