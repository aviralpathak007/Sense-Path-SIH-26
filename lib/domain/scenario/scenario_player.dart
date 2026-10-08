import 'dart:async';
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:latlong2/latlong.dart';
import '../providers/navigation_provider.dart';
import '../../data/models/kinematics.dart';

/// Replays a recorded drive (assets/scenarios/*.json): raw phone IMU at 10 Hz, a 1 Hz "GNSS" fix from
/// the vehicle's reference logger, and a GNSS-denied interval that simply stops the fixes. The
/// engine sees exactly what it would see live; the reference position is used only for the HUD
/// drift readout and the green reference path.
class ScenarioPlayer {
  final NavigationNotifier _notifier;
  Timer? _timer;
  bool isPlaying = false;

  ScenarioPlayer(this._notifier);

  Future<void> play(String assetPath, {int speedup = 5}) async {
    stop(restoreSensors: false);
    final doc = json.decode(await rootBundle.loadString(assetPath));
    final frames = doc['frames'] as List;
    _notifier.beginScenario();
    isPlaying = true;
    var i = 0;
    _timer = Timer.periodic(Duration(milliseconds: (100 / speedup).round()), (t) {
      if (i >= frames.length) {
        stop();
        return;
      }
      final f = (frames[i] as List).map((e) => (e as num).toDouble()).toList();
      final denied = f[10] > 0.5;
      _notifier.feedEngineSensorData(SensorData(
        accelX: f[0], accelY: f[1], accelZ: f[2], gyroX: f[3], gyroY: f[4], gyroZ: f[5], preBinned: true));
      if (!denied && i % 10 == 0) {
        _notifier.feedEngineGpsData(LatLng(f[6], f[7]), f[8], f[9]);
      }
      _notifier.setScenarioReference(LatLng(f[6], f[7]));
      i++;
    });
  }

  void stop({bool restoreSensors = true}) {
    _timer?.cancel();
    if (isPlaying && restoreSensors) _notifier.endScenario();
    isPlaying = false;
  }
}
