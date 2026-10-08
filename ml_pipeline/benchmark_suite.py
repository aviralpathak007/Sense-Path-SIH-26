"""Honest GNSS-outage benchmark on held-out IO-VNBD runs.

Every number comes from running the model; nothing is hard-coded. For every start point in the
test runs we simulate an outage that begins with the true speed (what the last GNSS fix gives) and
ends once the vehicle has travelled 50 m / 1000 m, then compare:

  drnet    the learned dead-reckoning network (this project)
  hold     keep the speed from the last fix (naive DR with no accelerometer)
  integ    integrate the aligned forward accelerometer only (classical INS-style DR)
  oracle   the true speed -> isolates the error that comes from the heading assumption alone

Reported: along-track drift (|distance error| / distance travelled) and 2D position error.
Heading used for the 2D path is the *ground-truth* heading: gyro heading could not be validated on
this dataset (see Sense-Path-Docs.md), so 2D numbers are a speed-only evaluation.

    python ml_pipeline/benchmark_suite.py            # test runs, writes report + figure
"""
import argparse
import json
import os

import numpy as np
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dr_net import DRNet
from features import DT, scale_features
from runs import ROOT, TEST, load_run

HERE = os.path.dirname(os.path.abspath(__file__))
OUTAGES_M = (50, 1000)
TMAX = {50: 300, 1000: 1500}      # cap on outage length in 0.1 s steps (30 s / 150 s)
TARGET_PCT = 10.0
METHODS = ("drnet", "hold", "integ", "oracle")


def to_xy(lat, lon, lat0, lon0):
    return ((lon - lon0) * 111320.0 * np.cos(np.deg2rad(lat0)), (lat - lat0) * 110574.0)


def simulate(model, run, starts, tmax):
    n = len(run["gt_speed"])
    starts = [s for s in starts if s + tmax + 1 < n]
    feats = np.stack([scale_features(run["feat"][s:s + tmax]) for s in starts])
    gt = np.stack([run["gt_speed"][s + 1:s + tmax + 1] for s in starts])
    v0 = np.array([[run["gt_speed"][s]] for s in starts])
    with torch.no_grad():
        v_net = model(torch.tensor(feats, dtype=torch.float32), torch.tensor(v0, dtype=torch.float32)).numpy()
    v_int = np.maximum(v0 + np.cumsum(feats[:, :, 0] * 3.0 * DT, 1), 0)
    return starts, {"drnet": v_net, "hold": np.repeat(v0, tmax, 1), "integ": v_int, "oracle": gt}, gt


def evaluate(model, runs, length_m):
    tmax = TMAX[length_m]
    res = {m: {"drift": [], "pos": []} for m in METHODS}
    examples = None
    for run in runs:
        n = len(run["gt_speed"])
        starts = [s for s in range(1000, n - tmax - 2, 150) if run["gt_speed"][s] > 3.0]
        starts, vel, gt = simulate(model, run, starts, tmax)
        lat0, lon0 = run["gt_lat"], run["gt_lon"]
        xg, yg = to_xy(run["gt_lat"], run["gt_lon"], run["gt_lat"][0], run["gt_lon"][0])
        for i, s in enumerate(starts):
            cum = np.cumsum(gt[i] * DT)
            hit = np.searchsorted(cum, length_m)
            if hit >= tmax:
                continue
            e = hit + 1
            psi = np.deg2rad(run["gt_heading"][s + 1:s + 1 + e])
            if np.isnan(psi).any() or np.isnan(xg[s:s + e + 1]).any():
                continue
            for m in METHODS:
                dist_err = abs(((vel[m][i, :e] - gt[i, :e]) * DT).sum())
                res[m]["drift"].append(100.0 * dist_err / cum[hit])
                px = xg[s] + (vel[m][i, :e] * DT * np.sin(psi)).sum()
                py = yg[s] + (vel[m][i, :e] * DT * np.cos(psi)).sum()
                res[m]["pos"].append(float(np.hypot(px - xg[s + e], py - yg[s + e])))
            if examples is None and length_m == 1000 and cum[hit] > 900:
                examples = (run["name"], s, e, psi, {m: vel[m][i, :e] for m in METHODS}, gt[i, :e], (xg, yg))
    return res, examples


def stats(drift, pos):
    d, p = np.array(drift), np.array(pos)
    if len(d) == 0:
        return {"n_outages": 0}
    return {
        "n_outages": int(len(d)),
        "drift_pct_median": round(float(np.median(d)), 2),
        "drift_pct_mean": round(float(d.mean()), 2),
        "drift_pct_p95": round(float(np.percentile(d, 95)), 2),
        "frac_within_10pct": round(float((d <= TARGET_PCT).mean()), 3),
        "pos_err_m_median": round(float(np.median(p)), 1),
        "pos_err_m_p95": round(float(np.percentile(p, 95)), 1),
    }


def main(a):
    model = DRNet()
    model.load_state_dict(torch.load(a.model, map_location="cpu"))
    model.eval()
    runs = [load_run(n) for n in a.runs]
    report = {"model": os.path.relpath(a.model, ROOT), "test_runs": a.runs,
              "note": "heading for 2D error is ground-truth heading; along-track drift is the speed-only metric",
              "outages": {}}
    box, example = {}, None
    for L in OUTAGES_M:
        res, ex = evaluate(model, runs, L)
        report["outages"][f"{L}m"] = {m: stats(res[m]["drift"], res[m]["pos"]) for m in METHODS}
        box[L] = res
        example = example or ex
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    with open(a.report, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    plot(a, box, example)


def plot(a, box, example):
    fig, ax = plt.subplots(3, 1, figsize=(10, 14))
    labels, data = [], []
    for L in OUTAGES_M:
        for m in METHODS[:3]:
            if len(box[L][m]["drift"]):
                labels.append(f"{L} m\n{m}")
                data.append(np.clip(box[L][m]["drift"], 0, 100))
    ax[0].boxplot(data, tick_labels=labels, showfliers=False)
    ax[0].axhline(TARGET_PCT, color="r", ls=":", label="10 % target")
    ax[0].set(ylabel="along-track drift (% of distance)", title="Held-out drivers: drift per simulated GNSS outage")
    ax[0].legend()
    if example:
        name, s, e, psi, vel, gt, (xg, yg) = example
        t = np.arange(e) * DT
        for m, st in (("oracle", "g-"), ("drnet", "b--"), ("hold", "r:"), ("integ", "m-.")):
            ax[1].plot(t, vel[m], st, label=m if m != "oracle" else "ground truth")
        ax[1].set(title=f"Speed during a ~1 km outage ({name}, t={s * DT:.0f}s)", xlabel="s", ylabel="m/s")
        ax[1].legend()
        ax[2].plot(xg[s:s + e + 1], yg[s:s + e + 1], "g", lw=2, label="ground-truth path")
        for m, st in (("drnet", "b--"), ("hold", "r:")):
            ax[2].plot(xg[s] + np.cumsum(vel[m] * DT * np.sin(psi)), yg[s] + np.cumsum(vel[m] * DT * np.cos(psi)), st, label=m)
        ax[2].set(title="Dead-reckoned path (ground-truth heading)", xlabel="m", ylabel="m", aspect="equal")
        ax[2].legend()
    plt.tight_layout()
    plt.savefig(a.figure, dpi=140)
    print("saved", a.figure, a.report)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.path.join(ROOT, "dr_net.pt"))
    ap.add_argument("--runs", nargs="+", default=TEST)
    ap.add_argument("--report", default=os.path.join(HERE, "benchmark_report.json"))
    ap.add_argument("--figure", default=os.path.join(HERE, "benchmark.png"))
    main(ap.parse_args())
