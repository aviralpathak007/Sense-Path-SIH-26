"""Train DRNet on outage-like sequences: start from the true speed, integrate IMU for T steps.

    python ml_pipeline/train_dr.py [--iters 600]
"""
import argparse
import os
import time

import numpy as np
import torch

from dr_net import DRNet
from features import DT, scale_features
from runs import ROOT, TEST, TRAIN, VAL, load_run, outage_features

CFG = {"seq": 300}
SEQ = 300  # steps per training sequence (overridden by --seq)


def sample_batch(runs, batch, rng, aug=True):
    SEQ = CFG["seq"]
    xs, v0, ys = [], [], []
    for _ in range(batch):
        f = None
        while f is None:                       # only start where the axes were already calibrated
            r = runs[rng.integers(len(runs))]
            s = int(rng.integers(0, len(r["gt_speed"]) - SEQ - 1))
            f = outage_features(r, s, SEQ)
        if aug:
            d = np.deg2rad(rng.uniform(-8, 8))           # forward-axis estimation error
            c, si = np.cos(d), np.sin(d)
            f[:, 0], f[:, 1] = c * f[:, 0] - si * f[:, 1], si * f[:, 0] + c * f[:, 1]
            f[:, 0] += rng.uniform(-0.15, 0.15)           # accelerometer bias / road grade
        xs.append(scale_features(f))
        g = r["gt_speed"]
        v0.append([g[s] + (rng.normal(0, 0.3) if aug else 0.0)])
        ys.append(g[s + 1:s + SEQ + 1])
    t = lambda a: torch.tensor(np.array(a), dtype=torch.float32)  # noqa: E731
    return t(xs), t(v0), t(ys)


def eval_chain(model, runs, seq=600, stride=600):
    """Mean |speed error| and hold-baseline over 60 s chained windows on whole runs."""
    errs, hold = [], []
    model.eval()
    with torch.no_grad():
        for r in runs:
            g = r["gt_speed"]
            for s in range(1000, len(g) - seq - 1, stride):
                f = outage_features(r, s, seq)
                if f is None:
                    continue
                x = torch.tensor(scale_features(f), dtype=torch.float32)[None]
                v = model(x, torch.tensor([[g[s]]], dtype=torch.float32))[0].numpy()
                errs.append(np.abs(v - g[s + 1:s + seq + 1]).mean())
                hold.append(np.abs(g[s] - g[s + 1:s + seq + 1]).mean())
    model.train()
    return float(np.mean(errs)), float(np.mean(hold))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=600)
    ap.add_argument("--batch", type=int, default=48)
    ap.add_argument("--seq", type=int, default=300)
    ap.add_argument("--hidden", type=int, default=32)
    ap.add_argument("--dist_w", type=float, default=0.05)
    ap.add_argument("--out", default=os.path.join(ROOT, "dr_net.pt"))
    a = ap.parse_args()
    CFG["seq"] = a.seq

    torch.manual_seed(0)
    rng = np.random.default_rng(0)
    train = [load_run(n) for n in TRAIN]
    val = [load_run(n) for n in VAL]
    print("train:", TRAIN, "val:", VAL, "(test runs are never touched here:", TEST, ")")
    model = DRNet(a.hidden)
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    best, t0 = 1e9, time.time()
    for it in range(1, a.iters + 1):
        x, v0, y = sample_batch(train, a.batch, rng)
        pred = model(x, v0)
        l1 = (pred - y).abs().mean()
        dist = ((pred - y).cumsum(1) * DT).abs().mean()      # integrated-distance error
        loss = l1 + a.dist_w * dist
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        if it % 50 == 0:
            e, h = eval_chain(model, val)
            print(f"it {it:4d} loss {loss.item():.3f} | val 60s mean|err| {e:.3f} m/s vs hold {h:.3f} | {time.time() - t0:.0f}s", flush=True)
            if e < best:
                best = e
                torch.save(model.state_dict(), a.out)
    print("best val mean|err|:", best, "->", a.out)
