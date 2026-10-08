import 'dart:math';

class AlignmentCalibrator {
  List<double> gravityVector = [0.0, 0.0, 9.81];
  List<double> forwardVector = [1.0, 0.0, 0.0];
  List<double> lateralVector = [0.0, 1.0, 0.0];

  bool isCalibrated = false;

  final List<List<double>> _accelBuffer = [];
  final int _calibrationFrames = 100; // About 2 seconds at 50Hz

  void feedSensor(double ax, double ay, double az) {
    if (isCalibrated) return;

    _accelBuffer.add([ax, ay, az]);
    
    if (_accelBuffer.length >= _calibrationFrames) {
      _calibrate();
    }
  }

  void forceCalibration() {
    isCalibrated = false;
    _accelBuffer.clear();
  }

  void _calibrate() {
    // 1. Gravity Vector Extraction (Average of initial stationary frames)
    double sumX = 0, sumY = 0, sumZ = 0;
    for (var v in _accelBuffer) {
      sumX += v[0];
      sumY += v[1];
      sumZ += v[2];
    }
    
    int n = _accelBuffer.length;
    double gx = sumX / n;
    double gy = sumY / n;
    double gz = sumZ / n;

    // Normalize gravity vector (Z-axis in vehicle frame)
    double gMag = sqrt(gx * gx + gy * gy + gz * gz);
    gravityVector = [gx / gMag, gy / gMag, gz / gMag];

    // 2. Dynamic Forward Axis Detection (simplified for demo)
    // Assume forward acceleration is dominant along phone's Y-axis as a fallback
    // In real scenario, we'd subtract gravity and look for variance.
    forwardVector = [0.0, 1.0, 0.0];
    
    // Gram-Schmidt process to make forward orthogonal to gravity
    double dot = forwardVector[0] * gravityVector[0] + 
                 forwardVector[1] * gravityVector[1] + 
                 forwardVector[2] * gravityVector[2];
    
    forwardVector[0] -= dot * gravityVector[0];
    forwardVector[1] -= dot * gravityVector[1];
    forwardVector[2] -= dot * gravityVector[2];

    double fMag = sqrt(pow(forwardVector[0], 2) + pow(forwardVector[1], 2) + pow(forwardVector[2], 2));
    forwardVector = [forwardVector[0]/fMag, forwardVector[1]/fMag, forwardVector[2]/fMag];

    // 3. Compute Lateral Axis via Cross Product (Y-axis)
    lateralVector = [
      gravityVector[1] * forwardVector[2] - gravityVector[2] * forwardVector[1],
      gravityVector[2] * forwardVector[0] - gravityVector[0] * forwardVector[2],
      gravityVector[0] * forwardVector[1] - gravityVector[1] * forwardVector[0]
    ];

    isCalibrated = true;
    _accelBuffer.clear();
    print("AlignmentCalibrator: Calibration Complete.");
  }

  /// Projects raw phone IMU (ax, ay, az) into Vehicle Frame (Forward, Right, Down)
  List<double> projectToVehicleFrame(double ax, double ay, double az) {
    if (!isCalibrated) return [ax, ay, az];

    // R_phone_to_vehicle * [ax, ay, az]^T
    double vFwd = forwardVector[0] * ax + forwardVector[1] * ay + forwardVector[2] * az;
    double vLat = lateralVector[0] * ax + lateralVector[1] * ay + lateralVector[2] * az;
    double vDwn = gravityVector[0] * ax + gravityVector[1] * ay + gravityVector[2] * az;

    return [vFwd, vLat, vDwn];
  }
}
