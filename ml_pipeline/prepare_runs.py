"""Download IO-VNBD runs (Git LFS) and merge each S (phone) + V (vehicle) pair into one .npz.

Both files are 10 Hz and row-aligned (checked: equal row counts, 100 ms steps). Per run we keep
the raw phone IMU *including gravity*, magnetometer, phone GPS, and the vehicle's ground-truth
speed / heading / position, so the benchmark can score real trajectories.

    python ml_pipeline/prepare_runs.py            # downloads RUNS into data/runs/
"""
import io
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://github.com/onyekpeu/IO-VNBD/raw/master/Synchronised V abd S datasets/Categorised IOVNB Dataset"
OUT = os.path.join(ROOT, "data", "runs")

# name -> (folder, S file, V file). Driver tags are kept in the name so splits are by driver.
RUNS = {
    "B_M": ("M (Driver B)", "S-M.csv", "V-M.csv"),
    "A_S1": ("S (Driver A)/S1", "S-S1.csv", "V-S1.csv"),
    "A_S2": ("S (Driver A)/S2", "S-S2.csv", "V-S2.csv"),
    "A_S4": ("S (Driver A)/S4", "S-S4.csv", "V-S4.csv"),
    "D_Y1": ("Y (Driver D)/Y1", "S-Y1.csv", "V-Y1.csv"),
}
for n in (1, 5, 10, 15, 20, 25):
    RUNS[f"E_Vta{n}"] = (f"Vta (Driver E)/Vta{n:02d}", f"S-Vta{n}.csv", f"V-vta{n}.csv")
for n in (1, 5, 9):
    RUNS[f"E_Vtb{n}"] = (f"Vtb (Driver E)/Vtb{n:02d}", f"S-Vtb{n}.csv", f"V-vtb{n}.csv")
for n in (1, 5, 10, 15):
    RUNS[f"E_Vw{n}"] = (f"Vw (Driver E)/Vw{n:02d}", f"S-Vw{n}.csv", f"V-Vw{n}.csv")
for n in (1, 2):
    RUNS[f"E_Vfa{n}"] = (f"Vf (Driver E)/V-Vfa{n:02d}", f"S-Vfa{n:02d}.csv", f"V-Vfa{n:02d}.csv")


def fetch(path):
    url = "https://github.com/onyekpeu/IO-VNBD/raw/master/" + urllib.parse.quote(
        "Synchronised V abd S datasets/Categorised IOVNB Dataset/" + path)
    with urllib.request.urlopen(url, timeout=180) as r:
        return r.read()


def build(name):
    out = os.path.join(OUT, name + ".npz")
    if os.path.exists(out):
        return name, "cached"
    folder, sf, vf = RUNS[name]
    try:
        s = pd.read_csv(io.BytesIO(fetch(f"{folder}/{sf}")), encoding="latin1", on_bad_lines="skip")
        v = pd.read_csv(io.BytesIO(fetch(f"{folder}/{vf}")), encoding="latin1", on_bad_lines="skip")
    except Exception as e:  # noqa: BLE001
        return name, f"FAILED {e}"
    n = min(len(s), len(v))
    s, v = s.iloc[:n], v.iloc[:n]
    f = lambda df, i: pd.to_numeric(df.iloc[:, i], errors="coerce").values.astype(np.float64)  # noqa: E731
    np.savez_compressed(
        out,
        t=f(s, 7) / 1000.0,
        acc=np.stack([f(s, 9), f(s, 10), f(s, 11)], 1),        # includes gravity
        grav=np.stack([f(s, 12), f(s, 13), f(s, 14)], 1),
        gyro=np.stack([f(s, 15), f(s, 16), f(s, 17)], 1),      # file order: Yaw, Pitch, Roll
        mag=np.stack([f(s, 18), f(s, 19), f(s, 20)], 1),
        phone_gps_speed=f(s, 3) / 3.6,
        phone_lat=f(s, 0), phone_lon=f(s, 1),
        gt_speed=f(v, 4) / 3.6,
        gt_heading=f(v, 5),
        gt_lat=f(v, 2), gt_lon=f(v, 3),
        gt_yaw_rate=np.deg2rad(f(v, 14)),
    )
    return name, f"ok {n} rows"


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    with ThreadPoolExecutor(6) as ex:
        for name, msg in ex.map(build, RUNS):
            print(f"{name:10s} {msg}", flush=True)
