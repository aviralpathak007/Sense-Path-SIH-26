"""Navigation loop on top of IdrCore: heading from the gyro, position by dead reckoning, GNSS fusion.

Deliberately simple (complementary-filter style, no covariance tracking). Mirrors
lib/domain/dr_engine/dead_reckoning_engine.dart.
"""
import math

import numpy as np

from idr_core import DT, IdrCore

R_EARTH = 6371000.0
GNSS_TIMEOUT_S = 1.5


def wrap_pi(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class IdrNav:
    def __init__(self, onnx_path=None, stepper=None):
        self.core = IdrCore(onnx_path, stepper)
        self.lat = self.lon = None
        self.psi = 0.0            # compass heading, radians clockwise from north
        self.bias = 0.0           # gyro-about-up bias, rad/s
        self.speed = 0.0
        self.last_fix_t = None
        self.t = 0.0
        self.outage_dist = 0.0
        self.mode = "gnss"

    @property
    def in_outage(self):
        return self.mode == "dr"

    def on_gnss(self, lat, lon, bearing_deg, speed, t):
        self.core.on_gnss(speed, t, bearing_deg)
        self.lat, self.lon, self.last_fix_t = lat, lon, t
        if speed > 2.0:
            self.psi = math.radians(bearing_deg)
        self.speed = speed
        if self.mode == "dr":
            self.mode = "gnss"
        self.outage_dist = 0.0

    def force_outage(self):
        if self.mode != "dr" and self.lat is not None:
            self.mode = "dr"
            self.core.start_outage()

    def on_imu(self, acc, gyro, t):
        """One 10 Hz step. Returns (lat, lon, bearing_deg, speed, mode)."""
        self.t = t
        if self.lat is None:
            return None
        if self.mode == "gnss" and self.last_fix_t is not None and t - self.last_fix_t > GNSS_TIMEOUT_S:
            self.force_outage()
        speed, w_yaw = self.core.on_imu(acc, gyro)
        if speed < 0.3:                                   # ZUPT: stationary -> learn the gyro bias
            self.bias = 0.98 * self.bias + 0.02 * w_yaw
            speed = 0.0
        self.psi = (self.psi + (w_yaw - self.bias) * DT) % (2 * math.pi)
        d = speed * DT
        self.lat += math.degrees(d * math.cos(self.psi) / R_EARTH)
        self.lon += math.degrees(d * math.sin(self.psi) / (R_EARTH * math.cos(math.radians(self.lat))))
        self.speed = speed
        if self.mode == "dr":
            self.outage_dist += d
        return self.lat, self.lon, math.degrees(self.psi), speed, self.mode
