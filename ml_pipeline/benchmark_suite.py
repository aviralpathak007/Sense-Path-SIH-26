"""Offline benchmark for the KinematicVelocityNet speed estimator.

Every number written to the report is computed by running the model on the CSV; nothing is
hard-coded. What it measures, and what it does not:

* Speed accuracy (RMSE / MAE) against the odometry ground truth.
* Along-track drift for simulated GNSS outages of 50 m and 1000 m: the error of the distance
  obtained by integrating speed over the outage, as a percentage of the distance travelled.
  This ignores heading error, which needs ground-truth position (not in the prepared CSVs).
* Baselines: hold the speed at outage start (what a naive DR would do) and a constant speed.

The sample rate of the prepared CSVs is not stored in them; pass --rate_hz. The report states the
value used and the acceleration it implies, so an implausible rate is visible.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
import torch
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from dataset import IOVNBDDataset  # noqa: E402
from model import KinematicVelocityNet  # noqa: E402

OUTAGES_M = (50, 1000)
MAX_DRIFT_PCT = 10.0  # PS 26168: < 10 % of distance travelled


def predict_speed(model_path, csv, window, stride):
    ds = IOVNBDDataset(csv, window_size=window, overlap=window - stride, is_train=False)
    model = KinematicVelocityNet(window_size=window)
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()
    preds = []
    with torch.no_grad():
        for i in range(0, len(ds), 256):
            xb = torch.stack([ds[j][0] for j in range(i, min(i + 256, len(ds)))])
            preds.append(model(xb).reshape(-1).numpy())
    end_idx = np.array([end - 1 for _, end in ds.windows])
    return end_idx, np.concatenate(preds), ds.velocity[end_idx]


def outage_drift(pred, gt, dt, length_m, method):
    """Along-track drift (% of distance) for every possible outage start."""
    out = []
    for s in range(len(gt)):
        cum, err, e = 0.0, 0.0, s
        while e < len(gt) and cum < length_m:
            p = gt[s] if method == "hold" else pred[e]
            err += (p - gt[e]) * dt
            cum += gt[e] * dt
            e += 1
        if cum >= length_m:
            out.append(100.0 * abs(err) / cum)
    return np.array(out)


def summarise(x):
    if len(x) == 0:
        return {"n_outages": 0, "status": "NOT EVALUATED (sequence shorter than the outage)"}
    p95 = float(np.percentile(x, 95))
    return {
        "n_outages": int(len(x)),
        "mean_drift_pct": round(float(x.mean()), 2),
        "median_drift_pct": round(float(np.median(x)), 2),
        "p95_drift_pct": round(p95, 2),
        "max_drift_pct": round(float(x.max()), 2),
        "status": f"{'PASS' if p95 <= MAX_DRIFT_PCT else 'FAIL'} (p95 <= {MAX_DRIFT_PCT:.0f}%)",
    }


def run(args):
    end_idx, pred, gt = predict_speed(args.model, args.csv, args.window, args.stride)
    dt = args.stride / args.rate_hz
    train_mean = float(pd.read_csv(args.train_csv)["velocity_forward"].mean())

    implied_acc = float(np.percentile(np.abs(np.diff(pd.read_csv(args.csv)["velocity_forward"].values)), 99)
                        * args.rate_hz)
    report = {
        "csv": os.path.relpath(args.csv, ROOT),
        "assumed_rate_hz": args.rate_hz,
        "p99_implied_acceleration_mps2": round(implied_acc, 1),
        "rate_warning": "implausible (>15 m/s^2): the assumed sample rate is probably wrong"
        if implied_acc > 15 else "plausible",
        "n_windows": int(len(gt)),
        "distance_covered_m": round(float(gt.sum() * dt), 1),
        "speed_rmse_mps": {
            "model": round(float(np.sqrt(np.mean((pred - gt) ** 2))), 3),
            "constant_train_mean": round(float(np.sqrt(np.mean((train_mean - gt) ** 2))), 3),
        },
        "speed_mae_mps": {
            "model": round(float(np.mean(np.abs(pred - gt))), 3),
            "constant_train_mean": round(float(np.mean(np.abs(train_mean - gt))), 3),
        },
        "pred_speed_std_mps": round(float(pred.std()), 3),
        "gt_speed_std_mps": round(float(gt.std()), 3),
        "pred_gt_correlation": round(float(np.corrcoef(pred, gt)[0, 1]), 3) if pred.std() > 0 else 0.0,
        "along_track_drift": {},
    }
    drifts = {}
    for L in OUTAGES_M:
        drifts[L] = {m: outage_drift(pred, gt, dt, L, m) for m in ("model", "hold")}
        report["along_track_drift"][f"{L}m_outage"] = {m: summarise(v) for m, v in drifts[L].items()}

    with open(args.report, "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))
    plot(args, end_idx, pred, gt, dt, drifts)


def plot(args, end_idx, pred, gt, dt, drifts):
    raw = pd.read_csv(args.csv)
    gz = raw["gyro_z"].values[end_idx]
    heading = np.cumsum(gz * dt)  # sign/axis convention of gyro_z is unverified

    def path(speed):
        return np.cumsum(speed * dt * np.cos(heading)), np.cumsum(speed * dt * np.sin(heading))

    fig, ax = plt.subplots(3, 1, figsize=(10, 13))
    t = np.arange(len(gt)) * dt
    ax[0].plot(t, gt, "g", label="ground truth speed")
    ax[0].plot(t, pred, "b--", label="model")
    ax[0].set(title=f"Speed ({os.path.basename(args.csv)}, assumed {args.rate_hz:g} Hz)", xlabel="s", ylabel="m/s")
    ax[0].legend()
    gx, gy = path(gt)
    px, py = path(pred)
    ax[1].plot(gx, gy, "g", label="GT speed + gyro heading")
    ax[1].plot(px, py, "b--", label="model speed + gyro heading")
    ax[1].set(title="Dead-reckoned path (heading from integrated gyro_z; GT position not in CSV)",
              xlabel="m", ylabel="m", aspect="equal")
    ax[1].legend()
    data, labels = [], []
    for L in OUTAGES_M:
        for m in ("model", "hold"):
            if len(drifts[L][m]):
                data.append(drifts[L][m])
                labels.append(f"{L} m\n{m}")
    if data:
        ax[2].boxplot(data, labels=labels)
        ax[2].axhline(MAX_DRIFT_PCT, color="r", ls=":", label="10 % target")
        ax[2].set(title="Along-track drift per simulated outage", ylabel="% of distance")
        ax[2].legend()
    plt.tight_layout()
    plt.savefig(args.figure, dpi=150)
    print(f"Saved {args.figure} and {args.report}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default=os.path.join(ROOT, "data", "test_iovnbd.csv"))
    p.add_argument("--train_csv", default=os.path.join(ROOT, "data", "train_iovnbd.csv"))
    p.add_argument("--model", default=os.path.join(ROOT, "best_model.pt"))
    p.add_argument("--rate_hz", type=float, required=True, help="sample rate of the CSV (not stored in it)")
    p.add_argument("--window", type=int, default=100)
    p.add_argument("--stride", type=int, default=10)
    p.add_argument("--report", default=os.path.join(HERE, "benchmark_report.json"))
    p.add_argument("--figure", default=os.path.join(HERE, "benchmark.png"))
    run(p.parse_args())
