import 'package:latlong2/latlong.dart';

enum GnssStatus { strong, degraded, blackout }
enum DataSourceMode { internalImu, edgeFog }

class KinematicsState {
  final LatLng position;
  final double bearing; // in degrees
  final double speed; // in m/s
  final double driftMeters; // error vs. reference during an outage; < 0 = no reference available
  final double outageDistance; // metres travelled since GNSS was lost
  final List<LatLng> truthPath;
  final bool dataFromEdge;
  final GnssStatus gnssStatus;
  final bool isAligned;
  final List<LatLng> historicalPath;
  final List<LatLng> drPath;
  final DataSourceMode dataSourceMode;
  final int telemetryHz;

  const KinematicsState({
    required this.position,
    required this.bearing,
    required this.speed,
    required this.driftMeters,
    this.outageDistance = 0,
    this.truthPath = const [],
    this.dataFromEdge = false,
    required this.gnssStatus,
    required this.isAligned,
    required this.historicalPath,
    required this.drPath,
    this.dataSourceMode = DataSourceMode.internalImu,
    this.telemetryHz = 10,
  });

  KinematicsState copyWith({
    LatLng? position,
    double? bearing,
    double? speed,
    double? driftMeters,
    double? outageDistance,
    List<LatLng>? truthPath,
    bool? dataFromEdge,
    GnssStatus? gnssStatus,
    bool? isAligned,
    List<LatLng>? historicalPath,
    List<LatLng>? drPath,
    DataSourceMode? dataSourceMode,
    int? telemetryHz,
  }) {
    return KinematicsState(
      position: position ?? this.position,
      bearing: bearing ?? this.bearing,
      speed: speed ?? this.speed,
      driftMeters: driftMeters ?? this.driftMeters,
      outageDistance: outageDistance ?? this.outageDistance,
      truthPath: truthPath ?? this.truthPath,
      dataFromEdge: dataFromEdge ?? this.dataFromEdge,
      gnssStatus: gnssStatus ?? this.gnssStatus,
      isAligned: isAligned ?? this.isAligned,
      historicalPath: historicalPath ?? this.historicalPath,
      drPath: drPath ?? this.drPath,
      dataSourceMode: dataSourceMode ?? this.dataSourceMode,
      telemetryHz: telemetryHz ?? this.telemetryHz,
    );
  }
}

class SensorData {
  final double accelX;
  final double accelY;
  final double accelZ;
  final double gyroX;
  final double gyroY;
  final double gyroZ;
  final bool preBinned; // already one 10 Hz sample (scenario replay)

  const SensorData({
    required this.accelX,
    required this.accelY,
    required this.accelZ,
    required this.gyroX,
    required this.gyroY,
    required this.gyroZ,
    this.preBinned = false,
  });
}
