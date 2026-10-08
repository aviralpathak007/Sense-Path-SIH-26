import 'dart:typed_data';
import 'package:onnxruntime/onnxruntime.dart';
import 'idr_core.dart';

/// Runs one DRNet step per call through ONNX Runtime and keeps speed + hidden state in between.
/// Model: assets/dr_net.onnx  (feat[1,5], v[1,1], h[1,32]) -> (v_next[1,1], h_next[1,32]).
class DrStepRunner implements DrStepper {
  static const int hidden = 32;
  OrtSession? _session;
  final OrtRunOptions _runOptions = OrtRunOptions();
  double _v = 0;
  Float32List _h = Float32List(hidden);

  /// [modelBytes] = assets/dr_net.onnx, loaded on the main isolate (rootBundle is unavailable here).
  void init(Uint8List modelBytes) {
    OrtEnv.instance.init();
    _session = OrtSession.fromBuffer(modelBytes, OrtSessionOptions());
  }

  @override
  void reset(double v0) {
    _v = v0;
    _h = Float32List(hidden);
  }

  @override
  double step(List<double> featRaw) {
    final session = _session;
    if (session == null) return _v;
    final feat = Float32List.fromList([for (var i = 0; i < 5; i++) featRaw[i] / kFeatureScales[i]]);
    final inputs = {
      'feat': OrtValueTensor.createTensorWithDataList(feat, [1, 5]),
      'v': OrtValueTensor.createTensorWithDataList(Float32List.fromList([_v]), [1, 1]),
      'h': OrtValueTensor.createTensorWithDataList(_h, [1, hidden]),
    };
    final outputs = session.run(_runOptions, inputs);
    _v = ((outputs[0]?.value as List)[0] as List)[0] as double;
    _h = Float32List.fromList(List<double>.from(((outputs[1]?.value as List)[0] as List).cast<num>()));
    for (final t in inputs.values) {
      t.release();
    }
    for (final o in outputs) {
      o?.release();
    }
    return _v;
  }

  void dispose() {
    _session?.release();
    _runOptions.release();
  }
}
