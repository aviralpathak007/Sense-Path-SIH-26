// Navigation loop on top of IdrCore (heading from gyro, DR position, GNSS fusion).
// Port of edge_engine/idr_nav.py. Complementary-filter style: no covariance tracking.
import 'dart:math' as math;
import 'idr_core.dart';

const double _rEarth = 6371000.0;
const double _gnssTimeoutS = 1.5;

class NavOutput {
  final double lat, lon, bearingDeg, speed;
  final bool inOutage;
  final double outageDistance;
  NavOutput(this.lat, this.lon, this.bearingDeg, this.speed, this.inOutage, this.outageDistance);
}

class IdrNav {
  final IdrCore core;
  IdrNav(DrStepper stepper) : core = IdrCore(stepper);

  double? lat, lon;
  double psi = 0.0; // compass heading, radians clockwise from north
  double bias = 0.0;
  double speed = 0.0;
  double? _lastFixT;
  double outageDist = 0.0;
  bool inOutage = false;

  void onGnss(double la, double lo, double bearingDeg, double speedMs, double t) {
    core.onGnss(speedMs, t, bearingDeg);
    lat = la;
    lon = lo;
    _lastFixT = t;
    if (speedMs > 2.0) psi = bearingDeg * math.pi / 180.0;
    speed = speedMs;
    inOutage = false;
    outageDist = 0.0;
  }

  void forceOutage() {
    if (!inOutage && lat != null) {
      inOutage = true;
      core.startOutage();
    }
  }

  NavOutput? onImu(List<double> acc, List<double> gyro, double t) {
    if (lat == null) return null;
    if (!inOutage && _lastFixT != null && t - _lastFixT! > _gnssTimeoutS) forceOutage();
    final r = core.onImu(acc, gyro);
    var v = r[0];
    final w = r[1];
    if (v < 0.3) {
      bias = 0.98 * bias + 0.02 * w; // ZUPT: stationary -> learn gyro bias
      v = 0.0;
    }
    psi = (psi + (w - bias) * kDt) % (2 * math.pi);
    final d = v * kDt;
    lat = lat! + (d * math.cos(psi) / _rEarth) * 180.0 / math.pi;
    lon = lon! + (d * math.sin(psi) / (_rEarth * math.cos(lat! * math.pi / 180.0))) * 180.0 / math.pi;
    speed = v;
    if (inOutage) outageDist += d;
    return NavOutput(lat!, lon!, psi * 180.0 / math.pi, v, inOutage, outageDist);
  }
}
