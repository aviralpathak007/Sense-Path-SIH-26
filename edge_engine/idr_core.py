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
    """Per-sample gravity-aligned decomposition. Output angles are relative to the e1/e2 basis."""

    def __init__(self):
        self.g = None

    def update(self, acc, gyro):
        acc = np.asarray(acc, dtype=np.float64)
        gyro = np.asarray(gyro, dtype=np.float64)
        self.g = acc.copy() if self.g is None else (1 - GRAV_ALPHA) * self.g + GRAV_ALPHA * acc
        g_norm = float(np.linalg.norm(self.g))
        g_hat = self.g / g_norm
        ref = np.array([1.0, 0, 0]) if abs(g_hat[0]) < 0.9 else np.array([0, 1.0, 0])
        e1 = ref - (ref @ g_hat) * g_hat
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(g_hat, e1)
        a1, a2 = float(acc @ e1), float(acc @ e2)
        a_v = float(acc @ g_hat) - g_norm
        w_up = float(gyro @ g_hat)
        w_h = float(np.linalg.norm(gyro - w_up * g_hat))
        return a1, a2, a_v, w_up, w_h

    @staticmethod
    def vehicle(a1, a2, a_v, w_up, w_h, theta):
        c, s = np.cos(theta), np.sin(theta)
        return np.array([c * a1 + s * a2, -s * a1 + c * a2, a_v, w_up, w_h])


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

    def __init__(self, onnx_path):
        self.feat = FeatureStream()
        self.axis = ForwardAxisCalibrator()
        self.net = OrtStep(onnx_path)
        self.speed = 0.0
        self.gnss_speed = 0.0
        self.mode = "gnss"          # "gnss" | "dr"
        self.t = 0.0

    @property
    def can_dead_reckon(self):
        return self.axis.theta is not None

    def on_gnss(self, speed, t):
        """Call for every GNSS fix while the signal is usable."""
        self.axis.on_gnss(speed, t)
        self.gnss_speed = speed
        self.speed = speed
        if self.mode == "dr":
            self.mode = "gnss"       # seamless return: the next IMU step already follows GNSS

    def start_outage(self):
        if self.mode != "dr":
            self.mode = "dr"
            self.net.reset(self.gnss_speed if self.speed == 0 else self.speed)

    def on_imu(self, acc, gyro):
        """10 Hz IMU sample. Returns (speed, yaw_rate)."""
        a1, a2, a_v, w_up, w_h = self.feat.update(acc, gyro)
        self.axis.on_imu(a1, a2)
        if self.mode == "dr":
            if self.can_dead_reckon:
                f = FeatureStream.vehicle(a1, a2, a_v, w_up, w_h, self.axis.theta)
                self.speed = self.net.step(f)
            # without a calibrated axis we can only hold the last GNSS speed
        return self.speed, w_up
