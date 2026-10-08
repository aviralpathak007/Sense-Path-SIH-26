import 'dart:math';
import 'package:latlong2/latlong.dart';

class KalmanFilter {
  // State Vector: [Latitude, Longitude, Forward Velocity (vx), Yaw/Heading (psi), Gyro Bias (b_psi)]
  double lat = 0.0;
  double lon = 0.0;
  double vx = 0.0;
  double psi = 0.0;
  double b_psi = 0.0;

  // Earth radius in meters
  final double R = 6371000.0;

  void initState(LatLng gpsPos, double gpsBearing, double gpsSpeed) {
    lat = gpsPos.latitude;
    lon = gpsPos.longitude;
    vx = gpsSpeed;
    psi = gpsBearing * pi / 180.0; // Convert to radians
    b_psi = 0.0;
  }

  /// Prediction Step (50 Hz): Propagate state using gyroscope yaw rate and forward acceleration
  void predict(double dt, double forwardAccel, double yawRate) {
    // Correct yaw rate with bias
    double correctedYawRate = yawRate - b_psi;
    
    // Propagate Heading
    psi += correctedYawRate * dt;
    
    // Propagate Velocity
    vx += forwardAccel * dt;
    if (vx < 0.0) vx = 0.0; // Reverse constraint

    // Propagate Position (simplified flat-earth for very short dt)
    double dist = vx * dt;
    double dLat = dist * cos(psi) / R;
    double dLon = dist * sin(psi) / (R * cos(lat * pi / 180.0));

    lat += dLat * 180.0 / pi;
    lon += dLon * 180.0 / pi;

    // Normalize heading to 0-2PI
    psi = psi % (2 * pi);
  }

  /// GNSS Measurement Update (1 Hz when available)
  void updateGNSS(LatLng gpsPos, double gpsBearing, double gpsSpeed) {
    // Simple EKF measurement update approximation via complementary filter logic
    // In full EKF, we would compute innovation and update covariance matrix P.
    
    // Blend position (Trust GPS heavily)
    lat = gpsPos.latitude;
    lon = gpsPos.longitude;
    
    // Blend velocity
    vx = (vx * 0.1) + (gpsSpeed * 0.9);
    
    // Update Heading and compute Gyro Bias
    double measPsi = gpsBearing * pi / 180.0;
    
    // Handle wrap-around
    double diff = measPsi - psi;
    if (diff > pi) diff -= 2 * pi;
    if (diff < -pi) diff += 2 * pi;

    psi += diff * 0.5; // Gain
    b_psi -= diff * 0.01; // Estimate bias
  }

  /// GNSS Outage / AI DR Update (10 Hz)
  void updateAI(double aiVelocity) {
    // Fuse the forward velocity vx predicted by OnnxVelocityEstimator.
    // Trust AI velocity heavily during outages.
    vx = (vx * 0.1) + (aiVelocity * 0.9);

    // Non-Holonomic Constraints (NHC) are implicitly enforced here because 
    // we strictly propagate only `vx` (forward velocity) and set lateral (vy=0).
    
    // Zero-Velocity Update (ZUPT)
    if (vx < 0.2 && aiVelocity < 0.2) {
      vx = 0.0; // Clamp
      // Halt heading drift when stationary
      b_psi = b_psi * 0.99; 
    }
  }

  LatLng get position => LatLng(lat, lon);
  double get bearing => psi * 180.0 / pi;
  double get speed => vx;
}
