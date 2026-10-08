"""Streams an external-IMU feed at 200 Hz.

Source: edge_engine/replay/heldout_segment.npz, a held-out IO-VNBD drive recorded at 10 Hz. It is
linearly interpolated to 200 Hz, so the *throughput and latency* of the edge pipeline are real but
the extra samples carry no extra information. A real FOG/IMU would replace `ticks()` with a serial
or UDP reader that yields the same dicts.
"""
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_HZ, OUT_HZ = 10, 200
K = OUT_HZ // SRC_HZ


class ReplaySource:
    def __init__(self, path=os.path.join(HERE, "replay", "heldout_segment.npz")):
        d = np.load(path)
        self.n_src = len(d["acc"])
        src = np.arange(self.n_src)
        t = np.arange((self.n_src - 1) * K + 1) / K
        self.acc = np.stack([np.interp(t, src, d["acc"][:, i]) for i in range(3)], 1)
        self.gyro = np.stack([np.interp(t, src, d["gyro"][:, i]) for i in range(3)], 1)
        self.lat, self.lon = d["lat"], d["lon"]
        self.bearing, self.speed = d["bearing"], d["speed"]
        self.outage = tuple(int(x) for x in d["outage"])      # in 10 Hz samples
        self.n = len(self.acc)

    def tick(self, i):
        """Sample i at 200 Hz -> dict with imu, optional GNSS fix (1 Hz, absent in the outage), reference."""
        s = i // K                                            # source (10 Hz) index
        fix = None
        if i % OUT_HZ == 0 and not (self.outage[0] <= s < self.outage[1]):
            fix = (float(self.lat[s]), float(self.lon[s]), float(self.bearing[s]), float(self.speed[s]))
        return {"acc": self.acc[i], "gyro": self.gyro[i], "fix": fix,
                "ref": (float(self.lat[s]), float(self.lon[s])), "t": i / OUT_HZ}
