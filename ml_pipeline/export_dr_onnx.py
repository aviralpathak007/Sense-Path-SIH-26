"""Export one DRNet step to ONNX and verify it against PyTorch.

Inputs : feat (1,5) scaled vehicle-frame features, v (1,1) speed m/s, h (1,H) hidden state
Outputs: v_next (1,1), h_next (1,H)
The caller (Dart app or Python edge engine) keeps v and h between 10 Hz steps.

    python ml_pipeline/export_dr_onnx.py
"""
import os

import numpy as np
import onnxruntime as ort
import torch

from dr_net import DRNet
from runs import ROOT


class Step(torch.nn.Module):
    def __init__(self, net):
        super().__init__()
        self.net = net

    def forward(self, feat, v, h):
        return self.net.step(feat, v, h)


def main(pt=os.path.join(ROOT, "dr_net.pt"), out=os.path.join(ROOT, "assets", "dr_net.onnx")):
    sd = torch.load(pt, map_location="cpu")
    net = DRNet(sd["cell.weight_hh"].shape[1])
    net.load_state_dict(sd)
    net.eval()
    H = net.hidden
    ex = (torch.randn(1, 5), torch.tensor([[10.0]]), torch.randn(1, H))
    torch.onnx.export(Step(net), ex, out, opset_version=13, dynamo=False,
                      input_names=["feat", "v", "h"], output_names=["v_next", "h_next"])
    sess = ort.InferenceSession(out, providers=["CPUExecutionProvider"])
    worst = 0.0
    rng = np.random.default_rng(1)
    v, h = torch.tensor([[12.0]]), torch.zeros(1, H)
    vo, ho = v.numpy(), h.numpy()
    for _ in range(300):                       # 30 s of chained steps, not just one
        f = rng.normal(0, 0.6, (1, 5)).astype(np.float32)
        with torch.no_grad():
            v, h = net.step(torch.tensor(f), v, h)
        vo, ho = sess.run(None, {"feat": f, "v": vo.astype(np.float32), "h": ho.astype(np.float32)})
        worst = max(worst, float(abs(v.numpy() - vo).max()))
    print(f"exported {out} ({os.path.getsize(out)} bytes), hidden={H}, max |torch-onnx| over 300 chained steps = {worst:.2e}")
    assert worst < 1e-3


if __name__ == "__main__":
    main()
