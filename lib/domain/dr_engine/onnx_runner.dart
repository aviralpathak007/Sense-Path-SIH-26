import 'package:flutter/services.dart';
import 'package:onnxruntime/onnxruntime.dart';
import 'dart:typed_data';

class OnnxVelocityEstimator {
  OrtSession? _session;
  OrtEnv? _env;

  Future<void> init() async {
    // Initialize the ONNX Runtime environment
    _env = OrtEnv.instance;
    _env?.init();

    // Load the model from Flutter assets
    final rawAssetFile = await rootBundle.load('assets/model.onnx');
    final bytes = rawAssetFile.buffer.asUint8List();

    // Create session options
    final sessionOptions = OrtSessionOptions();
    
    // Create the session from the byte array
    _session = OrtSession.fromBuffer(bytes, sessionOptions);
    print("ONNX Model initialized successfully!");
  }

  /// Estimates velocity given a 6-axis IMU window of 100 samples
  /// [imuData] must be a 1D Float32List of length 600 (6 channels * 100 timesteps)
  /// ordered exactly as the model expects.
  double estimateVelocity(Float32List imuData) {
    if (_session == null) {
      throw Exception("ONNX Session not initialized.");
    }

    // Our model expects input shape: [1, 6, 100]
    final shape = [1, 6, 100];
    
    // Create an OrtValue tensor from the Float32List
    final inputTensor = OrtValueTensor.createTensorWithDataList(imuData, shape);

    // The input name in the ONNX model is 'imu_input'
    final runOptions = OrtRunOptions();
    final inputs = {'imu_input': inputTensor};

    // Run inference
    final outputs = _session!.run(runOptions, inputs);

    // The output name is 'velocity_output' with shape [1, 1]
    final outputTensor = outputs[0]?.value as List;
    final velocityList = outputTensor[0] as List;
    final velocity = velocityList[0] as double;

    // Clean up resources to prevent memory leaks in the background isolate
    inputTensor.release();
    runOptions.release();
    for (var element in outputs) {
      element?.release();
    }

    return velocity;
  }

  void dispose() {
    _session?.release();
    _env?.release();
  }
}
