"""Load IO-VNBD runs (from prepare_runs.py), time-align them and attach deployment-style features."""
import os

import numpy as np

from features import DT, axis_from_accel, decompose, imu_lag, smooth, vehicle_features

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_DIR = os.path.join(ROOT, "data", "runs")

# Split by driver/run, never by window. Driver A is fully held out for testing.
TRAIN = ["B_M", "E_Vfa2", "E_Vtb5"]
VAL = ["E_Vfa1"]
TEST = ["A_S1", "A_S2"]
MIN_QUALITY = 0.9   # phone-GNSS vs vehicle speed correlation after alignment


def load_run(name):
    d = np.load(os.path.join(RUN_DIR, name + ".npz"))
    acc0 = np.nan_to_num(d["acc"])
    lag, corr = imu_lag(acc0, np.nan_to_num(d["gt_speed"]))
    sl = (slice(lag, None), slice(None, len(d["t"]) - lag)) if lag >= 0 else (slice(None, len(d["t"]) + lag), slice(-lag, None))
    r = {k: d[k][sl[0]] for k in ("acc", "gyro", "mag", "phone_gps_speed", "phone_lat", "phone_lon")}
    r.update({k: d[k][sl[1]] for k in ("gt_speed", "gt_heading", "gt_lat", "gt_lon")})
    n = min(len(r["acc"]), len(r["gt_speed"]))
    r = {k: v[:n] for k, v in r.items()}
    ok = ~(np.isnan(r["acc"]).any(1) | np.isnan(r["gyro"]).any(1) | np.isnan(r["gt_speed"]))
    # keep the longest valid prefix-free segment by simply zero-filling isolated NaNs
    for k in ("acc", "gyro"):
        r[k] = np.nan_to_num(r[k])
    r["gt_speed"] = np.nan_to_num(r["gt_speed"])
    r["phone_gps_speed"] = np.nan_to_num(r["phone_gps_speed"])
    a_h1, a_h2, *_ = decompose(r["acc"], r["gyro"])
    # Forward axis calibrated on the first 5 minutes only (stand-in for a time-synced GNSS speed).
    a_gt = smooth(np.gradient(r["gt_speed"]) / DT)
    theta, q = axis_from_accel(a_h1[:3000], a_h2[:3000], a_gt[:3000], r["gt_speed"][:3000])
    r.update(name=name, lag_s=lag * DT, speed_corr=corr, theta=theta, axis_quality=q, valid_frac=float(ok.mean()))
    r["feat"] = vehicle_features(r["acc"], r["gyro"], theta) if theta is not None else None
    return r
