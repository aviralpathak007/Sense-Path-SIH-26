import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import '../../data/models/kinematics.dart';
import '../dr_engine/dead_reckoning_engine.dart';
import '../../data/sensors/sensor_service.dart';

final navigationProvider = NotifierProvider<NavigationNotifier, KinematicsState>(() {
  return NavigationNotifier();
});

class NavigationNotifier extends Notifier<KinematicsState> {
  late final DeadReckoningEngine _engine;
  late final SensorService _sensorService;
  
  // Track paths
  final List<LatLng> _historicalPath = [];
  final List<LatLng> _drPath = [];

  @override
  KinematicsState build() {
    _initSystem();

    ref.onDispose(() {
      _sensorService.stop();
      _engine.stop();
    });

    return const KinematicsState(
      position: LatLng(37.7749, -122.4194), // Default San Francisco
      bearing: 0,
      speed: 0,
      driftMeters: 0,
      gnssStatus: GnssStatus.strong,
      isAligned: true,
      historicalPath: [],
      drPath: [],
    );
  }

  void _initSystem() async {
    _engine = DeadReckoningEngine(onUpdate: _handleEngineUpdate);
    await _engine.start();
    
    _sensorService = SensorService(_engine);
    await _sensorService.start();
  }

  void _handleEngineUpdate(EngineStateUpdate update) {
    if (update.isOutage) {
      _drPath.add(update.position);
    } else {
      _historicalPath.add(update.position);
      // Optional: Clear DR path when GPS is restored or keep it for visualization
    }

    state = state.copyWith(
      position: update.position,
      bearing: update.bearing,
      speed: update.speed,
      driftMeters: update.driftMeters,
      gnssStatus: update.isOutage ? GnssStatus.blackout : GnssStatus.strong,
      historicalPath: List.from(_historicalPath),
      drPath: List.from(_drPath),
    );
  }

  void toggleSimulateOutage(bool isOutage) {
    _engine.setSimulateOutage(isOutage);
    if (!isOutage) {
      _drPath.clear(); // Reset DR path when outage ends
    }
    state = state.copyWith(
      gnssStatus: isOutage ? GnssStatus.blackout : GnssStatus.strong,
      drPath: List.from(_drPath),
    );
  }

  void calibrateMount() {
    state = state.copyWith(isAligned: false); // Set false until calibration complete
    _engine.calibrateMount();
  }

  void loadPresetScenario() {
    // For demo purposes, we can artificially move the position
    // Real implementation would read from a JSON/CSV dataset and feed it to the engine
  }

}
