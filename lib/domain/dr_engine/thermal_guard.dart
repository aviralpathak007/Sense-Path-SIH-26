class ThermalGuard {
  final int maxLatencyMs = 80;
  final int thresholdFrames = 5;
  
  List<int> _latencies = [];
  bool _isThrottled = false;

  /// Logs the latency of a single ONNX inference call in milliseconds
  void logInferenceLatency(int latencyMs) {
    _latencies.add(latencyMs);
    if (_latencies.length > thresholdFrames) {
      _latencies.removeAt(0);
    }
  }

  /// Evaluates whether the system should throttle the inference rate to 5Hz
  /// returns true if throttling should be active (5 Hz), false if normal (10 Hz)
  bool shouldThrottle() {
    if (_latencies.length < thresholdFrames) return _isThrottled;
    
    int overThresholdCount = _latencies.where((l) => l > maxLatencyMs).length;
    
    // If all recent frames exceed the latency budget, we throttle down
    if (overThresholdCount == thresholdFrames && !_isThrottled) {
      print("THERMAL GUARD: Latency > 80ms for \$thresholdFrames frames. Throttling to 5Hz.");
      _isThrottled = true;
    } 
    // Hysteresis: Only recover if all recent frames are well under budget (e.g. < 40ms)
    else if (_isThrottled) {
      int underThresholdCount = _latencies.where((l) => l < 40).length;
      if (underThresholdCount == thresholdFrames) {
        print("THERMAL GUARD: Thermals recovered. Restoring to 10Hz.");
        _isThrottled = false;
      }
    }

    return _isThrottled;
  }
}
