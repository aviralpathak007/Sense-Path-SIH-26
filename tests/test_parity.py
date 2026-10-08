"""Streaming core (edge_engine/idr_core.py) vs vectorised training features (ml_pipeline/runs.py).

    venv/bin/python tests/test_parity.py
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, "ml_pipeline"), os.path.join(ROOT, "edge_engine")]
import idr_core as C  # noqa: E402
import runs as R  # noqa: E402

r = R.load_run("E_Vfa1")
s, n = 4000, 600
run = {"base": r["base"], "gyro": r["gyro"]}
for u in (None, np.array([0.05, -0.8, 0.3])):
    theta = 0.7
    vec = R.make_features(run, s, s + n, theta, u)
    fs = C.FeatureStream()
    for i in range(s + n):
        a1, a2, av, g = fs.update(r["acc"][i])
        if i >= s:
            f = C.vehicle_features(a1, a2, av, r["gyro"][i], g, theta, u)
            assert np.abs(f - vec[i - s]).max() < 1e-9, (i, f, vec[i - s])
print("parity OK: streaming core == vectorised features (default and calibrated yaw axis)")
