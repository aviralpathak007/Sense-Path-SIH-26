import 'dart:async';
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:latlong2/latlong.dart';
import '../providers/navigation_provider.dart';
import '../../data/models/kinematics.dart';

class ScenarioPlayer {
  final NavigationNotifier _notifier;
  Timer? _playbackTimer;
  bool isPlaying = false;

  ScenarioPlayer(this._notifier);

  Future<void> playScenario(String assetPath) async {
    if (isPlaying) stop();

    try {
      final String jsonString = await rootBundle.loadString(assetPath);
      final List<dynamic> frames = json.decode(jsonString);

      if (frames.isEmpty) return;

      isPlaying = true;
      int currentIndex = 0;

      // Playback loop (simulating real-time 10Hz playback for demo)
      _playbackTimer = Timer.periodic(const Duration(milliseconds: 100), (timer) {
        if (currentIndex >= frames.length) {
          stop();
          return;
        }

        final frame = frames[currentIndex];
        
        // Push fake sensor data
        _notifier.feedEngineSensorData(
          SensorData(
            accelX: frame['ax'], accelY: frame['ay'], accelZ: frame['az'],
            gyroX: frame['gx'], gyroY: frame['gy'], gyroZ: frame['gz'],
          )
        );

        // Manage simulated GNSS status
        bool isDenied = frame['is_gnss_denied'] == true;
        _notifier.setSimulatedOutageFlag(isDenied);

        if (!isDenied) {
          _notifier.feedEngineGpsData(
            LatLng(frame['lat'], frame['lon']),
            frame['bearing'],
            frame['speed']
          );
        }

        currentIndex++;
      });
    } catch (e) {
      print("Failed to play scenario: \$e");
      isPlaying = false;
    }
  }

  void stop() {
    _playbackTimer?.cancel();
    isPlaying = false;
    _notifier.setSimulatedOutageFlag(false);
  }
}
