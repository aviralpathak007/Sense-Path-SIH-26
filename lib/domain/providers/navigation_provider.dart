import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import '../../data/models/kinematics.dart';
import '../dr_engine/dead_reckoning_engine.dart';
import '../../data/sensors/sensor_service.dart';
import '../scenario/scenario_player.dart';
import '../services/edge_sync_service.dart';

final navigationProvider = NotifierProvider<NavigationNotifier, KinematicsState>(() {
  return NavigationNotifier();
});

class NavigationNotifier extends Notifier<KinematicsState> {
  late final DeadReckoningEngine _engine;
  late final SensorService _sensorService;
  late final ScenarioPlayer _scenarioPlayer;
  late final EdgeSyncService _edgeSyncService;
  
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

    _scenarioPlayer = ScenarioPlayer(this);
    _edgeSyncService = EdgeSyncService(this);
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

  void loadPresetScenario(String path) {
    _scenarioPlayer.playScenario(path);
  }

  void feedEngineSensorData(SensorData data) {
    _engine.feedSensorData(data);
  }

  void setSimulatedOutageFlag(bool isOutage) {
    toggleSimulateOutage(isOutage);
  }

  void feedEngineGpsData(LatLng pos, double bearing, double speed) {
    _engine.feedGpsData(pos, bearing, speed);
  }

  void setDataSourceMode(DataSourceMode mode) {
    if (mode == DataSourceMode.edgeFog) {
      _edgeSyncService.connect("ws://localhost:8080/ws/telemetry");
      state = state.copyWith(dataSourceMode: mode, telemetryHz: 200);
    } else {
      _edgeSyncService.disconnect();
      state = state.copyWith(dataSourceMode: mode, telemetryHz: 10);
    }
  }

  void feedEdgeTelemetry(LatLng pos, double bearing, double speed) {
    if (state.dataSourceMode == DataSourceMode.edgeFog) {
      // In edge mode, we bypass local engine drift computations
      _drPath.add(pos);
      state = state.copyWith(
        position: pos,
        bearing: bearing,
        speed: speed,
        gnssStatus: GnssStatus.blackout, // Simulate edge doing DR
        drPath: List.from(_drPath),
      );
    }
  }
}
