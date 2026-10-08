"""Learned dead-reckoning cell.

State: speed v (m/s) and a GRU hidden vector. Each 10 Hz step it takes the 5 scaled vehicle-frame
features and its own speed, and outputs a bounded correction to the measured forward acceleration
plus a soft stop-gate (learned ZUPT). Speed is integrated inside the network, so it can be trained
end to end on long outage-like sequences and started from the last GNSS speed at runtime.
"""
import torch
import torch.nn as nn

from features import A_SCALE, DT

DA_MAX = 2.0   # max learned acceleration correction (m/s^2)
V_SCALE = 30.0


class DRNet(nn.Module):
    def __init__(self, hidden=32):
        super().__init__()
        self.hidden = hidden
        self.cell = nn.GRUCell(6, hidden)
        self.head = nn.Linear(hidden, 2)
        nn.init.zeros_(self.head.weight)
        nn.init.zeros_(self.head.bias)
        with torch.no_grad():
            self.head.bias[1] = 8.0  # gate starts at ~1 (no damping)

    def step(self, feat, v, h):
        """feat (B,5) scaled features, v (B,1) m/s, h (B,H) -> (v_next, h_next)."""
        h = self.cell(torch.cat([feat, v / V_SCALE], 1), h)
        o = self.head(h)
        da = DA_MAX * torch.tanh(o[:, 0:1])
        gate = torch.sigmoid(o[:, 1:2])
        a = feat[:, 0:1] * A_SCALE + da
        return torch.relu(v + a * DT) * gate, h

    def forward(self, feats, v0, h0=None):
        """feats (B,T,5), v0 (B,1) -> speeds (B,T)."""
        B, T, _ = feats.shape
        h = torch.zeros(B, self.hidden) if h0 is None else h0
        v = v0
        out = []
        for t in range(T):
            v, h = self.step(feats[:, t], v, h)
            out.append(v)
        return torch.cat(out, 1)
