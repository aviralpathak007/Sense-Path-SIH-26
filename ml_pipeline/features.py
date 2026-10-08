"""Mount-invariant feature extraction shared by training, benchmark and the edge engine.

The Dart port (lib/domain/dr_engine/feature_extractor.dart) must stay numerically identical.
All inputs are 10 Hz phone samples: raw accelerometer INCLUDING gravity (m/s^2) and gyro (rad/s).

Per sample we output 5 features in the vehicle frame (no per-file statistics, fixed scales):
    a_f   forward accel (m/s^2)            - needs the forward axis (see ForwardAxisEstimator)
    a_l   lateral accel
    a_v   vertical accel minus gravity
    w_z   yaw rate (gyro . up)
    w_h   norm of the gyro component in the horizontal plane (pitch/roll activity)
"""
import numpy as np

RATE_HZ = 10.0
DT = 1.0 / RATE_HZ
GRAV_ALPHA = 0.03          # EMA coefficient for the gravity estimate (tau ~ 3 s at 10 Hz)
A_SCALE = 3.0              # m/s^2   -> network input scale
W_SCALE = 0.5              # rad/s


def gravity_ema(acc, alpha=GRAV_ALPHA):
    g = np.empty_like(acc)
    cur = acc[0].copy()
    for i in range(len(acc)):
        cur = (1 - alpha) * cur + alpha * acc[i]
        g[i] = cur
    return g


def horizontal_basis(g_hat):
    """Two orthonormal vectors spanning the plane orthogonal to gravity (per-sample, shape [n,3])."""
    ref = np.where(np.abs(g_hat[:, :1]) < 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]]))
    e1 = ref - (ref * g_hat).sum(1, keepdims=True) * g_hat
    e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
    e2 = np.cross(g_hat, e1)
    return e1, e2


def decompose(acc, gyro):
    """Gravity-aligned decomposition: returns (a_h1, a_h2, a_v, w_up, w_h, g_hat)."""
    g = gravity_ema(acc)
    g_hat = g / np.linalg.norm(g, axis=1, keepdims=True)
    e1, e2 = horizontal_basis(g_hat)
    a_h1 = (acc * e1).sum(1)
    a_h2 = (acc * e2).sum(1)
    a_v = (acc * g_hat).sum(1) - np.linalg.norm(g, axis=1)
    w_up = (gyro * g_hat).sum(1)
    w_h = np.linalg.norm(gyro - w_up[:, None] * g_hat, axis=1)
    return a_h1, a_h2, a_v, w_up, w_h, g_hat


def estimate_forward_axis(a_h1, a_h2, gps_speed, gps_hz=1.0, min_speed=2.0):
    """Angle theta so that forward = cos(theta)*e1 + sin(theta)*e2.

    Least squares of the GNSS-derived acceleration onto the horizontal accelerometer (what the app
    does with the GNSS fixes it receives before an outage). Returns (theta, quality in [0,1]).
    """
    k = int(round(RATE_HZ / gps_hz))  # samples per GNSS second
    # smooth horizontal accel over 1 s, differentiate GNSS speed over +-1 s
    ker = np.ones(k) / k
    s1 = np.convolve(a_h1, ker, mode="same")
    s2 = np.convolve(a_h2, ker, mode="same")
    a_gps = (np.roll(gps_speed, -k) - np.roll(gps_speed, k)) / (2.0 * k * DT)
    ok = (gps_speed > min_speed)
    ok[:2 * k] = False
    ok[-2 * k:] = False
    ok &= np.abs(a_gps) < 6.0
    if ok.sum() < 200:
        return None, 0.0
    X = np.stack([s1[ok], s2[ok]], 1)
    y = a_gps[ok]
    w, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ w
    quality = float(np.corrcoef(pred, y)[0, 1]) if pred.std() > 0 else 0.0
    return float(np.arctan2(w[1], w[0])), quality


def vehicle_features(acc, gyro, theta):
    a_h1, a_h2, a_v, w_up, w_h, _ = decompose(acc, gyro)
    c, s = np.cos(theta), np.sin(theta)
    a_f = c * a_h1 + s * a_h2
    a_l = -s * a_h1 + c * a_h2
    return np.stack([a_f, a_l, a_v, w_up, w_h], 1)


def scale_features(f):
    return f / np.array([A_SCALE, A_SCALE, A_SCALE, W_SCALE, W_SCALE])


def best_lag(phone_speed, gt_speed, max_lag=600):
    """Samples to shift so phone GNSS speed lines up with the vehicle ground-truth speed."""
    ps = np.nan_to_num(phone_speed)
    gt = np.nan_to_num(gt_speed)
    best, best_c = 0, -2
    for L in range(-max_lag, max_lag + 1, 2):
        x, y = (ps[L:], gt[:len(gt) - L]) if L >= 0 else (ps[:len(ps) + L], gt[-L:])
        if len(x) < 2000 or x.std() == 0 or y.std() == 0:
            continue
        c = np.corrcoef(x, y)[0, 1]
        if c > best_c:
            best, best_c = L, c
    return best, float(best_c)


def smooth(x, k=10):
    return np.convolve(x, np.ones(k) / k, mode="same")


def axis_from_accel(a_h1, a_h2, a_target, speed, min_speed=2.0):
    """Forward-axis angle by least squares against a target longitudinal acceleration."""
    s1, s2 = smooth(a_h1), smooth(a_h2)
    ok = speed > min_speed
    ok[:20] = ok[-20:] = False
    if ok.sum() < 200:
        return None, 0.0
    X = np.stack([s1[ok], s2[ok]], 1)
    w, *_ = np.linalg.lstsq(X, a_target[ok], rcond=None)
    p = X @ w
    q = float(np.corrcoef(p, a_target[ok])[0, 1]) if p.std() > 0 else 0.0
    return float(np.arctan2(w[1], w[0])), q


def imu_lag(acc, gt_speed, max_lag=300, use=12000):
    """Lag (samples) between the phone IMU and the vehicle speed record, found on the IMU itself.

    Positive L: IMU sample j+L corresponds to ground-truth sample j.
    """
    a_gt = smooth(np.gradient(gt_speed) / DT)
    A = np.stack([smooth(acc[:, i] - acc[:, i].mean()) for i in range(3)], 1)
    n = len(gt_speed)
    lo = min(n // 3, 2000)
    sl = slice(lo, min(n - max_lag - 1, lo + use))
    best, best_c = 0, -1.0
    for L in range(-max_lag, max_lag + 1, 2):
        x = A[sl.start + L: sl.stop + L]
        y = a_gt[sl]
        if len(x) != len(y):
            continue
        w, *_ = np.linalg.lstsq(x, y, rcond=None)
        p = x @ w
        c = np.corrcoef(p, y)[0, 1] if p.std() > 0 else 0
        if c > best_c:
            best, best_c = L, float(c)
    return best, best_c
