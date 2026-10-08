import 'dart:io' show exit;
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:latlong2/latlong.dart';
import '../../data/models/kinematics.dart';
import '../dr_engine/dead_reckoning_engine.dart';
import '../../data/sensors/sensor_service.dart';
import '../scenario/scenario_player.dart';
import '../services/edge_sync_service.dart';

final navigationProvider = NotifierProvider<NavigationNotifier, KinematicsState>(() => NavigationNotifier());

/// Host of the edge engine (set with --dart-define=EDGE_HOST=LAPTOP_IP when running on a phone).
const String kEdgeHost = String.fromEnvironment('EDGE_HOST', defaultValue: 'localhost');

/// Verification aid: --dart-define=AUTOPLAY_SCENARIO=true replays the held-out scenario at start-up,
/// logs the outage error vs. the reference, and exits when it ends.
const bool kAutoplay = bool.fromEnvironment('AUTOPLAY_SCENARIO');

class NavigationNotifier extends Notifier<KinematicsState> {
  late final DeadReckoningEngine _engine;
  late final SensorService _sensorService;
  late final ScenarioPlayer _scenarioPlayer;
  late final EdgeSyncService _edgeSyncService;

  final List<LatLng> _historicalPath = []; // positions while GNSS is available
  final List<LatLng> _drPath = []; // positions while dead reckoning
  final List<LatLng> _truthPath = []; // reference path (scenario replay only)
  LatLng? _reference;
  bool _wasOutage = false;
  static const int _maxPathPoints = 4000;

  @override
  KinematicsState build() {
    _engine = DeadReckoningEngine(onUpdate: _handleEngineUpdate);
    _sensorService = SensorService(_engine);
    _scenarioPlayer = ScenarioPlayer(this);
    _edgeSyncService = EdgeSyncService(this);
    _initSystem();
    ref.onDispose(() {
      _sensorService.stop();
      _engine.stop();
      _edgeSyncService.disconnect();
    });
    return const KinematicsState(
      position: LatLng(52.4025, -1.5035), // Coventry, UK: where the IO-VNBD data was recorded
      bearing: 0,
      speed: 0,
      driftMeters: -1,
      gnssStatus: GnssStatus.strong,
      isAligned: false,
      historicalPath: [],
      drPath: [],
    );
  }

  Future<void> _initSystem() async {
    await _engine.start();
    if (kAutoplay) {
      await Future.delayed(const Duration(seconds: 2));
      loadPresetScenario('assets/scenarios/heldout_outage_scenario.json', speedup: 10);
      return;
    }
    await _sensorService.start();
  }

  void _trim(List<LatLng> l) {
    if (l.length > _maxPathPoints) l.removeRange(0, l.length - _maxPathPoints);
  }

  void _handleEngineUpdate(EngineStateUpdate u) {
    if (state.dataSourceMode == DataSourceMode.edgeFog) return;
    if (u.isOutage) {
      if (!_wasOutage) _drPath.clear();
      _drPath.add(u.position);
      _trim(_drPath);
    } else {
      _historicalPath.add(u.position);
      _trim(_historicalPath);
    }
    _wasOutage = u.isOutage;
    final ref = _reference;
    if (kAutoplay && u.isOutage && ref != null && _drPath.length % 100 == 0) {
      final e = const Distance().as(LengthUnit.Meter, u.position, ref);
      debugPrint('AUTOPLAY outage: driven ${u.outageDistance.toStringAsFixed(0)} m, error ${e.toStringAsFixed(0)} m, speed ${u.speed.toStringAsFixed(1)} m/s, calibrated=${u.calibrated}');
    }
    state = state.copyWith(
      position: u.position,
      bearing: u.bearing,
      speed: u.speed,
      driftMeters: (u.isOutage && ref != null) ? const Distance().as(LengthUnit.Meter, u.position, ref) : -1,
      outageDistance: u.outageDistance,
      gnssStatus: u.isOutage ? GnssStatus.blackout : GnssStatus.strong,
      isAligned: u.calibrated,
      historicalPath: List.of(_historicalPath),
      drPath: List.of(_drPath),
      truthPath: List.of(_truthPath),
    );
  }

  // --- Judge-demo controls ---
  void toggleSimulateOutage(bool isOutage) {
    _engine.setSimulateOutage(isOutage);
    state = state.copyWith(gnssStatus: isOutage ? GnssStatus.blackout : GnssStatus.strong);
  }

  void calibrateMount() {
    state = state.copyWith(isAligned: false);
    _engine.calibrateMount();
  }

  void loadPresetScenario(String path, {int speedup = 5}) => _scenarioPlayer.play(path, speedup: speedup);

  // --- Scenario replay hooks ---
  void beginScenario() {
    _sensorService.stop();
    _engine.reset();
    _historicalPath.clear();
    _drPath.clear();
    _truthPath.clear();
    _reference = null;
    _wasOutage = false;
    state = state.copyWith(
      gnssStatus: GnssStatus.strong,
      isAligned: false,
      driftMeters: -1,
      outageDistance: 0,
      historicalPath: const [],
      drPath: const [],
      truthPath: const [],
    );
  }

  void endScenario() {
    if (kAutoplay) {
      debugPrint('AUTOPLAY done');
      exit(0);
    }
    _reference = null;
    state = state.copyWith(driftMeters: -1);
    _sensorService.start();
  }

  void setScenarioReference(LatLng p) {
    _reference = p;
    _truthPath.add(p);
    _trim(_truthPath);
  }

  void feedEngineSensorData(SensorData data) => _engine.feedSensorData(data);
  void feedEngineGpsData(LatLng pos, double bearing, double speed) => _engine.feedGpsData(pos, bearing, speed);

  // --- Edge engine (external IMU) ---
  void setDataSourceMode(DataSourceMode mode) {
    if (mode == DataSourceMode.edgeFog) {
      _edgeSyncService.connect('ws://$kEdgeHost:8080/ws/telemetry');
      state = state.copyWith(dataSourceMode: mode, telemetryHz: 200, dataFromEdge: true);
    } else {
      _edgeSyncService.disconnect();
      state = state.copyWith(dataSourceMode: mode, telemetryHz: 10, dataFromEdge: false);
    }
  }

  void feedEdgeTelemetry({
    required LatLng pos,
    required double bearing,
    required double speed,
    required bool isOutage,
    required double outageDistance,
    double? driftMeters,
  }) {
    if (state.dataSourceMode != DataSourceMode.edgeFog) return;
    if (isOutage) {
      if (!_wasOutage) _drPath.clear();
      _drPath.add(pos);
      _trim(_drPath);
    } else {
      _historicalPath.add(pos);
      _trim(_historicalPath);
    }
    _wasOutage = isOutage;
    state = state.copyWith(
      position: pos,
      bearing: bearing,
      speed: speed,
      gnssStatus: isOutage ? GnssStatus.blackout : GnssStatus.strong,
      outageDistance: outageDistance,
      driftMeters: driftMeters ?? -1,
      historicalPath: List.of(_historicalPath),
      drPath: List.of(_drPath),
    );
  }
}
