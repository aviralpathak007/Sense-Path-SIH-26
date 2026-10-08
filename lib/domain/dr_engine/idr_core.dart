// Streaming Intelligent-Dead-Reckoning core. Port of edge_engine/idr_core.py - keep numerically
// identical (verified by test/idr_core_test.dart against golden vectors generated from Python).
import 'dart:math' as math;

const double kDt = 0.1; // all processing runs at 10 Hz
const double kGravAlpha = 0.03;
const List<double> kFeatureScales = [3.0, 3.0, 3.0, 0.5, 0.5];

double _dot(List<double> a, List<double> b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
double _norm(List<double> a) => math.sqrt(_dot(a, a));
List<double> _cross(List<double> a, List<double> b) =>
    [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];

/// Gravity-aligned accelerometer decomposition.
class AccelDecomposition {
  final double a1, a2, aV;
  final List<double> gHat;
  AccelDecomposition(this.a1, this.a2, this.aV, this.gHat);
}

class FeatureStream {
  List<double>? _g;

  /// [acc] must include gravity (m/s^2).
  AccelDecomposition update(List<double> acc) {
    final g = _g == null
        ? List<double>.from(acc)
        : List<double>.generate(3, (i) => (1 - kGravAlpha) * _g![i] + kGravAlpha * acc[i]);
    _g = g;
    final gNorm = _norm(g);
    final gHat = [g[0] / gNorm, g[1] / gNorm, g[2] / gNorm];
    final ref = gHat[0].abs() < 0.9 ? [1.0, 0.0, 0.0] : [0.0, 1.0, 0.0];
    final d = _dot(ref, gHat);
    var e1 = [ref[0] - d * gHat[0], ref[1] - d * gHat[1], ref[2] - d * gHat[2]];
    final n1 = _norm(e1);
    e1 = [e1[0] / n1, e1[1] / n1, e1[2] / n1];
    final e2 = _cross(gHat, e1);
    return AccelDecomposition(_dot(acc, e1), _dot(acc, e2), _dot(acc, gHat) - gNorm, gHat);
  }
}

/// Returns [headingRate (rad/s, clockwise), w_h]. [u] null -> default -gHat (Android gyro is CCW+).
List<double> yawFeatures(List<double> gyro, List<double>? u, List<double> gHat) {
  final uv = u ?? [-gHat[0], -gHat[1], -gHat[2]];
  final k = _norm(uv);
  final uh = [uv[0] / k, uv[1] / k, uv[2] / k];
  final p = _dot(gyro, uh);
  final r = [gyro[0] - p * uh[0], gyro[1] - p * uh[1], gyro[2] - p * uh[2]];
  return [k * p, _norm(r)];
}

List<double> vehicleFeatures(AccelDecomposition a, List<double> gyro, double theta, List<double>? u) {
  final c = math.cos(theta), s = math.sin(theta);
  final y = yawFeatures(gyro, u, a.gHat);
  return [c * a.a1 + s * a.a2, -s * a.a1 + c * a.a2, a.aV, y[0], y[1]];
}

/// Forward direction in the phone's horizontal plane from GNSS speed changes.
class ForwardAxisCalibrator {
  final double forget, minSpeed;
  final int minFixes;
  ForwardAxisCalibrator({this.forget = 0.995, this.minFixes = 40, this.minSpeed = 2.0});

  final List<double> _xtx = [0, 0, 0, 0]; // [00,01,10,11]
  final List<double> _xty = [0, 0];
  final List<double> _sum = [0, 0];
  int _n = 0, _cnt = 0;
  double? _prevSpeed, _prevT;
  double? theta;

  void onImu(double a1, double a2) {
    _sum[0] += a1;
    _sum[1] += a2;
    _cnt++;
  }

  void reset() {
    for (var i = 0; i < 4; i++) {
      _xtx[i] = 0;
    }
    _xty[0] = _xty[1] = 0;
    _n = 0;
    theta = null;
    _prevSpeed = null;
    _prevT = null;
    _clearInterval();
  }

  void _clearInterval() {
    _sum[0] = _sum[1] = 0;
    _cnt = 0;
  }

  void onGnss(double speed, double t) {
    if (_prevSpeed != null && _cnt > 0 && t > _prevT!) {
      final aGps = (speed - _prevSpeed!) / (t - _prevT!);
      if (speed > minSpeed && _prevSpeed! > minSpeed && aGps.abs() < 6.0) {
        final x0 = _sum[0] / _cnt, x1 = _sum[1] / _cnt;
        _xtx[0] = forget * _xtx[0] + x0 * x0;
        _xtx[1] = forget * _xtx[1] + x0 * x1;
        _xtx[2] = forget * _xtx[2] + x1 * x0;
        _xtx[3] = forget * _xtx[3] + x1 * x1;
        _xty[0] = forget * _xty[0] + x0 * aGps;
        _xty[1] = forget * _xty[1] + x1 * aGps;
        _n++;
        if (_n >= minFixes) {
          final det = _xtx[0] * _xtx[3] - _xtx[1] * _xtx[2];
          if (det > 1e-9) {
            final w0 = (_xtx[3] * _xty[0] - _xtx[1] * _xty[1]) / det;
            final w1 = (-_xtx[2] * _xty[0] + _xtx[0] * _xty[1]) / det;
            theta = math.atan2(w1, w0);
          }
        }
      }
    }
    _prevSpeed = speed;
    _prevT = t;
    _clearInterval();
  }
}

/// Gyro -> compass-heading-rate vector, regressed from GNSS bearing change (mount independent).
class YawAxisCalibrator {
  final double forget, minSpeed;
  final int minFixes;
  YawAxisCalibrator({this.forget = 0.995, this.minFixes = 40, this.minSpeed = 3.0});

  final List<List<double>> _xtx = List.generate(3, (_) => [0.0, 0.0, 0.0]);
  final List<double> _xty = [0, 0, 0];
  final List<double> _sum = [0, 0, 0];
  int _n = 0, _cnt = 0;
  double? _prevB, _prevT;
  List<double>? u;

  void onImu(List<double> gyro) {
    for (var i = 0; i < 3; i++) {
      _sum[i] += gyro[i];
    }
    _cnt++;
  }

  void reset() {
    for (var i = 0; i < 3; i++) {
      _xtx[i].fillRange(0, 3, 0.0);
    }
    _xty.fillRange(0, 3, 0.0);
    _n = 0;
    u = null;
    _prevB = null;
    _prevT = null;
    _clear();
  }

  void _clear() {
    _sum.fillRange(0, 3, 0.0);
    _cnt = 0;
  }

  void onGnss(double bearingDeg, double speed, double t) {
    final b = bearingDeg * math.pi / 180.0;
    if (_prevB != null && _cnt > 0 && t > _prevT! && speed > minSpeed) {
      final d = (b - _prevB! + math.pi) % (2 * math.pi) - math.pi;
      final rate = d / (t - _prevT!);
      if (rate.abs() < 1.0) {
        final x = [_sum[0] / _cnt, _sum[1] / _cnt, _sum[2] / _cnt];
        for (var i = 0; i < 3; i++) {
          for (var j = 0; j < 3; j++) {
            _xtx[i][j] = forget * _xtx[i][j] + x[i] * x[j];
          }
          _xty[i] = forget * _xty[i] + x[i] * rate;
        }
        _n++;
        if (_n >= minFixes) {
          final w = _solve3();
          final nw = math.sqrt(w[0] * w[0] + w[1] * w[1] + w[2] * w[2]);
          if (nw > 0.3 && nw < 3.0) u = w;
        }
      }
    }
    _prevB = b;
    _prevT = t;
    _clear();
  }

  List<double> _solve3() {
    final a = List.generate(3, (i) => [..._xtx[i], _xty[i]]);
    for (var i = 0; i < 3; i++) {
      a[i][i] += 1e-6;
    }
    for (var c = 0; c < 3; c++) {
      var p = c;
      for (var r = c + 1; r < 3; r++) {
        if (a[r][c].abs() > a[p][c].abs()) p = r;
      }
      final tmp = a[c];
      a[c] = a[p];
      a[p] = tmp;
      for (var r = c + 1; r < 3; r++) {
        final f = a[r][c] / a[c][c];
        for (var k = c; k < 4; k++) {
          a[r][k] -= f * a[c][k];
        }
      }
    }
    final w = [0.0, 0.0, 0.0];
    for (var i = 2; i >= 0; i--) {
      var s = a[i][3];
      for (var j = i + 1; j < 3; j++) {
        s -= a[i][j] * w[j];
      }
      w[i] = s / a[i][i];
    }
    return w;
  }
}

/// One DRNet step: raw (unscaled) features in, speed out. State (speed, hidden) lives inside.
abstract class DrStepper {
  void reset(double v0);
  double step(List<double> featRaw);
}

enum IdrMode { gnss, deadReckoning }

class IdrCore {
  final DrStepper stepper;
  final FeatureStream feat = FeatureStream();
  final ForwardAxisCalibrator axis = ForwardAxisCalibrator();
  final YawAxisCalibrator yaw = YawAxisCalibrator();
  double speed = 0.0;
  IdrMode mode = IdrMode.gnss;

  IdrCore(this.stepper);

  bool get canDeadReckon => axis.theta != null;
  bool get yawCalibrated => yaw.u != null;

  void resetCalibration() {
    axis.reset();
    yaw.reset();
  }

  void onGnss(double speedMs, double t, [double? bearingDeg]) {
    axis.onGnss(speedMs, t);
    if (bearingDeg != null) yaw.onGnss(bearingDeg, speedMs, t);
    speed = speedMs;
    mode = IdrMode.gnss;
  }

  void startOutage() {
    if (mode != IdrMode.deadReckoning) {
      mode = IdrMode.deadReckoning;
      stepper.reset(speed);
    }
  }

  /// 10 Hz sample. Returns [speed m/s, heading rate rad/s clockwise].
  List<double> onImu(List<double> acc, List<double> gyro) {
    final a = feat.update(acc);
    axis.onImu(a.a1, a.a2);
    yaw.onImu(gyro);
    if (mode == IdrMode.deadReckoning && canDeadReckon) {
      speed = stepper.step(vehicleFeatures(a, gyro, axis.theta!, yaw.u));
    }
    return [speed, yawFeatures(gyro, yaw.u, a.gHat)[0]];
  }
}
