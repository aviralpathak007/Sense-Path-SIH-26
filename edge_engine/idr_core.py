"""Streaming Intelligent-Dead-Reckoning core (numpy only, no dataset dependencies).

This is the reference for the Dart port (lib/domain/dr_engine/idr_core.dart) and is used by the
edge engine and the benchmark. It must stay numerically identical to ml_pipeline/features.py
(checked by tests/test_parity.py).

Pipeline at 10 Hz:
    raw accel (with gravity) + gyro --> gravity-aligned decomposition --> forward axis rotation
    --> 5 scaled features --> DRNet step (speed integrator with learned correction)

GNSS: while fixes are good the speed is the GNSS speed and the forward axis keeps calibrating;
when GNSS drops, DRNet starts from the last GNSS speed with a zeroed hidden state.
"""
import numpy as np

RATE_HZ = 10.0
DT = 1.0 / RATE_HZ
GRAV_ALPHA = 0.03
A_SCALE = 3.0
W_SCALE = 0.5
SCALES = np.array([A_SCALE, A_SCALE, A_SCALE, W_SCALE, W_SCALE], dtype=np.float64)


class FeatureStream:
    """Per-sample gravity-aligned accelerometer decomposition (angles relative to the e1/e2 basis)."""

    def __init__(self):
        self.g = None

    def update(self, acc):
        """Returns (a1, a2, a_v, g_hat): horizontal accel along e1/e2, vertical accel minus g, up unit vector."""
        acc = np.asarray(acc, dtype=np.float64)
        self.g = acc.copy() if self.g is None else (1 - GRAV_ALPHA) * self.g + GRAV_ALPHA * acc
        g_norm = float(np.linalg.norm(self.g))
        g_hat = self.g / g_norm
        ref = np.array([1.0, 0, 0]) if abs(g_hat[0]) < 0.9 else np.array([0, 1.0, 0])
        e1 = ref - (ref @ g_hat) * g_hat
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(g_hat, e1)
        return float(acc @ e1), float(acc @ e2), float(acc @ g_hat) - g_norm, g_hat


def yaw_features(gyro, u, g_hat):
    """(heading_rate, w_h). u is the calibrated gyro->heading-rate vector; default is -g_hat
    (Android gyro is counter-clockwise positive about up, compass heading is clockwise)."""
    gyro = np.asarray(gyro, dtype=np.float64)
    u = -g_hat if u is None else np.asarray(u, dtype=np.float64)
    k = float(np.linalg.norm(u))
    uh = u / k
    p = float(gyro @ uh)
    return k * p, float(np.linalg.norm(gyro - p * uh))


def vehicle_features(a1, a2, a_v, gyro, g_hat, theta, u):
    c, s = np.cos(theta), np.sin(theta)
    w, w_h = yaw_features(gyro, u, g_hat)
    return np.array([c * a1 + s * a2, -s * a1 + c * a2, a_v, w, w_h])


class ForwardAxisCalibrator:
    """Learns the vehicle forward direction in the phone's horizontal plane from GNSS speed changes.

    Between consecutive GNSS fixes we regress the GNSS-derived acceleration onto the mean
    horizontal accelerometer vector. Exponential forgetting lets it follow a re-mounted phone.
    """

    def __init__(self, forget=0.995, min_fixes=40, min_speed=2.0):
        self.forget, self.min_fixes, self.min_speed = forget, min_fixes, min_speed
        self.xtx = np.zeros((2, 2))
        self.xty = np.zeros(2)
        self.n = 0
        self.sum = np.zeros(2)
        self.cnt = 0
        self.prev_speed = None
        self.prev_t = None
        self.theta = None

    def on_imu(self, a1, a2):
        self.sum += (a1, a2)
        self.cnt += 1

    def reset_interval(self):
        self.sum[:] = 0
        self.cnt = 0

    def on_gnss(self, speed, t):
        if self.prev_speed is not None and self.cnt > 0 and t > self.prev_t:
            a_gps = (speed - self.prev_speed) / (t - self.prev_t)
            if speed > self.min_speed and self.prev_speed > self.min_speed and abs(a_gps) < 6.0:
                x = self.sum / self.cnt
                self.xtx = self.forget * self.xtx + np.outer(x, x)
                self.xty = self.forget * self.xty + x * a_gps
                self.n += 1
                if self.n >= self.min_fixes:
                    det = np.linalg.det(self.xtx)
                    if det > 1e-9:
                        w = np.linalg.solve(self.xtx, self.xty)
                        self.theta = float(np.arctan2(w[1], w[0]))
        self.prev_speed, self.prev_t = speed, t
        self.reset_interval()


class YawAxisCalibrator:
    """Learns the gyro -> compass-heading-rate vector by regressing GNSS bearing change onto the gyro.

    Independent of how the phone is mounted (and of the sensor-frame conventions of the source).
    """

    def __init__(self, forget=0.995, min_fixes=40, min_speed=3.0):
        self.forget, self.min_fixes, self.min_speed = forget, min_fixes, min_speed
        self.xtx = np.zeros((3, 3))
        self.xty = np.zeros(3)
        self.n = 0
        self.sum = np.zeros(3)
        self.cnt = 0
        self.prev = None          # (bearing_rad, t)
        self.u = None

    def on_imu(self, gyro):
        self.sum += gyro
        self.cnt += 1

    def on_gnss(self, bearing_deg, speed, t):
        b = np.radians(bearing_deg)
        if self.prev is not None and self.cnt > 0 and t > self.prev[1] and speed > self.min_speed:
            d = (b - self.prev[0] + np.pi) % (2 * np.pi) - np.pi
            rate = d / (t - self.prev[1])
            if abs(rate) < 1.0:
                x = self.sum / self.cnt
                self.xtx = self.forget * self.xtx + np.outer(x, x)
                self.xty = self.forget * self.xty + x * rate
                self.n += 1
                if self.n >= self.min_fixes:
                    w = np.linalg.solve(self.xtx + 1e-6 * np.eye(3), self.xty)
                    if 0.3 < np.linalg.norm(w) < 3.0:
                        self.u = w
        self.prev = (b, t)
        self.sum[:] = 0
        self.cnt = 0


class OrtStep:
    """DRNet single step through onnxruntime; keeps v and h between calls."""

    def __init__(self, path):
        import onnxruntime as ort
        self.sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        self.hidden = self.sess.get_inputs()[2].shape[1]
        self.v = np.zeros((1, 1), np.float32)
        self.h = np.zeros((1, self.hidden), np.float32)

    def reset(self, v0):
        self.v = np.array([[v0]], np.float32)
        self.h = np.zeros((1, self.hidden), np.float32)

    def step(self, feat_raw):
        f = (np.asarray(feat_raw) / SCALES).astype(np.float32)[None]
        self.v, self.h = self.sess.run(None, {"feat": f, "v": self.v, "h": self.h})
        return float(self.v[0, 0])


class IdrCore:
    """Speed estimator with seamless GNSS <-> dead-reckoning switching."""

    def __init__(self, onnx_path=None, stepper=None):
        self.feat = FeatureStream()
        self.axis = ForwardAxisCalibrator()
        self.yaw = YawAxisCalibrator()
        self.net = stepper if stepper is not None else OrtStep(onnx_path)
        self.speed = 0.0
        self.gnss_speed = 0.0
        self.mode = "gnss"          # "gnss" | "dr"

    @property
    def can_dead_reckon(self):
        return self.axis.theta is not None

    def on_gnss(self, speed, t, bearing_deg=None):
        """Call for every usable GNSS fix."""
        self.axis.on_gnss(speed, t)
        if bearing_deg is not None:
            self.yaw.on_gnss(bearing_deg, speed, t)
        self.gnss_speed = speed
        self.speed = speed
        self.mode = "gnss"           # seamless return: the next IMU step already follows GNSS

    def start_outage(self):
        if self.mode != "dr":
            self.mode = "dr"
            self.net.reset(self.speed)

    def on_imu(self, acc, gyro):
        """10 Hz IMU sample. Returns (speed m/s, heading rate rad/s clockwise)."""
        gyro = np.asarray(gyro, dtype=np.float64)
        a1, a2, a_v, g_hat = self.feat.update(acc)
        self.axis.on_imu(a1, a2)
        self.yaw.on_imu(gyro)
        if self.mode == "dr" and self.can_dead_reckon:
            f = vehicle_features(a1, a2, a_v, gyro, g_hat, self.axis.theta, self.yaw.u)
            self.speed = self.net.step(f)
        # without a calibrated axis we can only hold the last GNSS speed
        return self.speed, yaw_features(gyro, self.yaw.u, g_hat)[0]
