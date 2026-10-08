"""Load IO-VNBD runs (from prepare_runs.py), time-align them and attach deployment-style features.

Alignment: the S (phone) and V (vehicle) files are 10 Hz but are not sample-synchronised, so each
run is shifted by the lag at which the phone accelerometer best explains the vehicle's longitudinal
acceleration (features.imu_lag). Forward axis and gyro yaw axis are then calibrated *causally* from
1 Hz speed / bearing fixes, exactly as the app does with GNSS before an outage.
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "edge_engine"))
from idr_core import ForwardAxisCalibrator, FeatureStream, YawAxisCalibrator  # noqa: E402
from features import DT, imu_lag  # noqa: E402

RUN_DIR = os.path.join(ROOT, "data", "runs")

# Split by driver/run, never by window. Driver A is fully held out for testing.
TRAIN = ["B_M", "E_Vfa2", "E_Vtb5"]
VAL = ["E_Vfa1"]
TEST = ["A_S1", "A_S2"]


def load_run(name):
    d = np.load(os.path.join(RUN_DIR, name + ".npz"))
    lag, fit = imu_lag(np.nan_to_num(d["acc"]), np.nan_to_num(d["gt_speed"]))
    n0 = len(d["t"])
    sa, sg = (slice(lag, None), slice(None, n0 - lag)) if lag >= 0 else (slice(None, n0 + lag), slice(-lag, None))
    r = {k: d[k][sa] for k in ("acc", "gyro")}
    r.update({k: d[k][sg] for k in ("gt_speed", "gt_heading", "gt_lat", "gt_lon")})
    n = min(len(r["acc"]), len(r["gt_speed"]))
    r = {k: v[:n] for k, v in r.items()}
    for k in ("acc", "gyro", "gt_speed"):
        r[k] = np.nan_to_num(r[k])
    r["gt_heading"] = np.nan_to_num(r["gt_heading"])
    r.update(name=name, lag_s=lag * DT, imu_fit_corr=fit)
    r["theta_t"], r["u_t"], r["base"] = streaming_axis(r)
    return r


def streaming_axis(run):
    """Causal calibration over the run. Returns (theta_t [n], u_t [n,3], base) with NaN until ready.

    base = dict(a=[a1,a2,a_v], g_hat) per sample. 1 Hz vehicle speed/bearing stand in for GNSS fixes.
    """
    fs, cal, yaw = FeatureStream(), ForwardAxisCalibrator(), YawAxisCalibrator()
    n = len(run["acc"])
    a, g = np.zeros((n, 3)), np.zeros((n, 3))
    theta, u = np.full(n, np.nan), np.full((n, 3), np.nan)
    for i in range(n):
        a1, a2, av, gh = fs.update(run["acc"][i])
        a[i], g[i] = (a1, a2, av), gh
        cal.on_imu(a1, a2)
        yaw.on_imu(run["gyro"][i])
        if i % 10 == 0:
            cal.on_gnss(run["gt_speed"][i], i * DT)
            yaw.on_gnss(run["gt_heading"][i], run["gt_speed"][i], i * DT)
        if cal.theta is not None:
            theta[i] = cal.theta
        if yaw.u is not None:
            u[i] = yaw.u
    return theta, u, {"a": a, "g": g}


def make_features(run, s, e, theta, u):
    """Vectorised twin of idr_core.vehicle_features for samples [s, e). u=None -> default -g_hat."""
    a, g, gy = run["base"]["a"][s:e], run["base"]["g"][s:e], run["gyro"][s:e]
    c, sn = np.cos(theta), np.sin(theta)
    if u is None:
        uvec, k = -g, np.ones(len(g))
        uh = uvec
    else:
        k = np.full(len(g), np.linalg.norm(u))
        uh = np.tile(u / np.linalg.norm(u), (len(g), 1))
    p = (gy * uh).sum(1)
    w_h = np.linalg.norm(gy - p[:, None] * uh, axis=1)
    return np.stack([c * a[:, 0] + sn * a[:, 1], -sn * a[:, 0] + c * a[:, 1], a[:, 2], k * p, w_h], 1)


def outage_features(run, s, length):
    """Features for an outage starting at s: axes frozen at their value when the outage begins."""
    theta = run["theta_t"][s]
    if np.isnan(theta):
        return None
    u = run["u_t"][s]
    return make_features(run, s, s + length, theta, None if np.isnan(u).any() else u)
