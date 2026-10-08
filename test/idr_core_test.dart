import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:sense_path/domain/dr_engine/idr_core.dart';
import 'package:sense_path/domain/dr_engine/idr_nav.dart';

/// Same stub as tests/make_golden.py (native ONNX cannot run in `flutter test`).
class StubStep implements DrStepper {
  double v = 0;
  @override
  void reset(double v0) => v = v0;
  @override
  double step(List<double> f) {
    v = (0.98 * v + 0.05 * f[0] + 0.01 * f[1]);
    if (v < 0) v = 0;
    return v;
  }
}

void main() {
  test('Dart IdrNav matches the Python reference (golden vectors)', () {
    final g = json.decode(File('test/golden_idr.json').readAsStringSync());
    final nav = IdrNav(StubStep());
    final expected = {for (final e in g['expected']) e['i'] as int: e};
    final frames = g['frames'] as List;
    for (var i = 0; i < frames.length; i++) {
      final f = frames[i];
      final t = i * 0.1;
      if (f['fix'] != null) {
        final x = (f['fix'] as List).map((e) => (e as num).toDouble()).toList();
        nav.onGnss(x[0], x[1], x[2], x[3], t);
      }
      final acc = (f['acc'] as List).map((e) => (e as num).toDouble()).toList();
      final gyro = (f['gyro'] as List).map((e) => (e as num).toDouble()).toList();
      final o = nav.onImu(acc, gyro, t);
      final e = expected[i];
      if (e != null && o != null) {
        expect(o.lat, closeTo(e['lat'] as double, 1e-7), reason: 'lat @ $i');
        expect(o.lon, closeTo(e['lon'] as double, 1e-7), reason: 'lon @ $i');
        expect(o.bearingDeg, closeTo(e['psi'] as double, 1e-4), reason: 'psi @ $i');
        expect(o.speed, closeTo((e['speed'] as num).toDouble(), 1e-6), reason: 'speed @ $i');
        expect(o.inOutage, e['mode'] == 'dr', reason: 'mode @ $i');
      }
    }
    expect(nav.core.axis.theta, closeTo(g['theta'] as double, 1e-6));
    final u = (g['u'] as List).map((e) => (e as num).toDouble()).toList();
    for (var i = 0; i < 3; i++) {
      expect(nav.core.yaw.u![i], closeTo(u[i], 1e-6));
    }
  });
}
