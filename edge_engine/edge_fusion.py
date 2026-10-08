"""Edge engine: IdrNav (10 Hz AI step) + a 200 Hz propagation layer for external IMUs.

Every 20 IMU samples are averaged into one 10 Hz sample for the AI/calibration core; between those
steps heading and position are propagated at the full IMU rate from the latest AI speed. With a
low-noise FOG gyro the high-rate heading is where the extra accuracy comes from; with the
interpolated replay it only demonstrates throughput.
"""
import math
import os
import time

import numpy as np

from idr_core import yaw_features
from idr_nav import IdrNav, R_EARTH

HERE = os.path.dirname(os.path.abspath(__file__))
IMU_HZ = 200
K = IMU_HZ // 10


def _dist_m(la1, lo1, la2, lo2):
    return math.hypot((lo2 - lo1) * 111320.0 * math.cos(math.radians(la1)), (la2 - la1) * 110574.0)


class EdgeFusionEngine:
    def __init__(self, model_path=os.path.join(HERE, "..", "assets", "dr_net.onnx"), average=False):
        """average=True: box-average each 20 IMU samples into the 10 Hz AI sample (use for a real
        200 Hz IMU, as anti-aliasing). average=False: take every 20th sample (use for the replay, whose
        10 Hz samples are the original recorded data and whose in-between samples are interpolated)."""
        self.average = average
        self.nav = IdrNav(model_path)
        self.reset()
        self.ai_ms, self.tick_ms = [], []

    def reset(self):
        self._acc_sum, self._gyro_sum, self._n = np.zeros(3), np.zeros(3), 0
        self.lat = self.lon = None
        self.psi = 0.0
        self.speed = 0.0

    def update(self, s):
        t0 = time.perf_counter()
        if s["fix"] is not None:
            self.nav.on_gnss(*s["fix"], s["t"])
            self.lat, self.lon = s["fix"][0], s["fix"][1]
            self.psi = math.radians(s["fix"][2]) if s["fix"][3] > 2.0 else self.psi
            self.speed = s["fix"][3]
        step = False
        if self.average:
            self._acc_sum += s["acc"]
            self._gyro_sum += s["gyro"]
            self._n += 1
            step = self._n == K
            acc, gyro = self._acc_sum / K, self._gyro_sum / K
        else:
            step = self._n % K == 0
            self._n += 1
            acc, gyro = s["acc"], s["gyro"]
        if step:
            t1 = time.perf_counter()
            out = self.nav.on_imu(acc, gyro, s["t"])
            if self.nav.in_outage:
                self.ai_ms.append((time.perf_counter() - t1) * 1000.0)
                self.ai_ms = self.ai_ms[-200:]
            if self.average:
                self._acc_sum[:] = 0
                self._gyro_sum[:] = 0
                self._n = 0
            if out is not None:
                self.lat, self.lon, psi_deg, self.speed, _ = out
                self.psi = math.radians(psi_deg)
        elif self.lat is not None:
            # high-rate propagation between AI steps
            g = self.nav.core.feat.g
            w = yaw_features(s["gyro"], self.nav.core.yaw.u, g / np.linalg.norm(g))[0] if g is not None else 0.0
            dt = 1.0 / IMU_HZ
            self.psi = (self.psi + (w - self.nav.bias) * dt) % (2 * math.pi)
            d = self.speed * dt
            self.lat += math.degrees(d * math.cos(self.psi) / R_EARTH)
            self.lon += math.degrees(d * math.sin(self.psi) / (R_EARTH * math.cos(math.radians(self.lat))))
        self.tick_ms.append((time.perf_counter() - t0) * 1000.0)
        self.tick_ms = self.tick_ms[-2000:]
        if self.lat is None:
            return None
        ref_lat, ref_lon = s["ref"]
        outage = self.nav.in_outage
        return {
            "lat": self.lat, "lon": self.lon, "speed": self.speed,
            "bearing": math.degrees(self.psi), "mode": "dr" if outage else "gnss",
            "outage_distance": self.nav.outage_dist if outage else 0.0,
            "drift_m": _dist_m(self.lat, self.lon, ref_lat, ref_lon) if outage else None,
            "ref_lat": ref_lat, "ref_lon": ref_lon,
            "calibrated": self.nav.core.can_dead_reckon,
        }

    def stats(self):
        avg = lambda a: round(float(np.mean(a)), 3) if a else 0.0  # noqa: E731
        return {"avg_ai_latency_ms": avg(self.ai_ms), "avg_tick_ms": avg(self.tick_ms),
                "max_tick_ms": round(float(np.max(self.tick_ms)), 3) if self.tick_ms else 0.0}
