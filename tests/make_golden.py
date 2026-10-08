"""Generate golden vectors for the Dart port (test/golden_idr.json).

Uses a deterministic stub instead of the ONNX model (native ONNX cannot run in `flutter test`), so
this checks everything around the network: features, calibrators, GNSS handling, heading/position.

    venv/bin/python tests/make_golden.py
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "edge_engine"))
from idr_nav import IdrNav  # noqa: E402


class StubStep:
    def reset(self, v0):
        self.v = v0

    def step(self, f):
        self.v = max(0.0, 0.98 * self.v + 0.05 * f[0] + 0.01 * f[1])
        return self.v


d = np.load(os.path.join(ROOT, "edge_engine", "replay", "heldout_segment.npz"))
acc, gyro, lat, lon, hd, sp = (d[k] for k in ("acc", "gyro", "lat", "lon", "bearing", "speed"))
o0 = int(d["outage"][0])
N = o0 + 400                                  # through 40 s of outage
nav = IdrNav(stepper=StubStep())
frames, out = [], []
for i in range(N):
    t = i * 0.1
    fix = None
    if not (o0 <= i) and i % 10 == 0:
        fix = [float(lat[i]), float(lon[i]), float(hd[i]), float(sp[i])]
        nav.on_gnss(*fix, t)
    r = nav.on_imu(acc[i], gyro[i], t)
    frames.append({"acc": [float(x) for x in acc[i]], "gyro": [float(x) for x in gyro[i]], "fix": fix})
    if i % 50 == 0 or i == N - 1:
        out.append({"i": i, "lat": r[0], "lon": r[1], "psi": r[2], "speed": r[3], "mode": r[4]})
res = {"frames": frames, "expected": out,
       "theta": nav.core.axis.theta, "u": [float(x) for x in nav.core.yaw.u] if nav.core.yaw.u is not None else None}
os.makedirs(os.path.join(ROOT, "test"), exist_ok=True)
json.dump(res, open(os.path.join(ROOT, "test", "golden_idr.json"), "w"), separators=(",", ":"))
print("golden:", len(frames), "frames; theta", res["theta"], "u", res["u"], "final", out[-1])
