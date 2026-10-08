# Sense-Path

AI/ML-assisted dead reckoning for smartphone navigation during GNSS outages (SIH 2026, PS 26168, ISRO).
Full details, results and limitations: **[Sense-Path-Docs.md](Sense-Path-Docs.md)**.

| Part | Where |
|---|---|
| Flutter app (ONNX on-device, replay demo, offline OSM roads) | `lib/` |
| Model training, export, benchmark | `ml_pipeline/` |
| Streaming core (reference), edge engine (200 Hz replay), dashboard | `edge_engine/` |
| Parity / golden tests | `tests/`, `test/` |

## Run

```bash
# App (desktop smoke test or phone)
flutter pub get && flutter run            # Judge Demo -> Load Preset Scenario
flutter test                              # Dart core vs Python golden vectors

# Edge engine + dashboard
cd edge_engine && ./run_edge.sh           # http://localhost:8080/dashboard
# phone -> edge engine: flutter run --dart-define=EDGE_HOST=<laptop-ip>

# ML pipeline (venv with torch, numpy, matplotlib, onnx, onnxruntime)
python ml_pipeline/prepare_runs.py        # downloads IO-VNBD runs into data/runs
python ml_pipeline/train_dr.py --iters 3000
python ml_pipeline/export_dr_onnx.py      # -> assets/dr_net.onnx
python ml_pipeline/benchmark_suite.py     # -> ml_pipeline/benchmark_report.json, benchmark.png
python tests/test_parity.py
```

Headline result (held-out driver, 1 km simulated outages): median along-track drift 9.4 % vs 25 % for
naive dead reckoning; 53 % of outages within the 10 % target. Not yet tested in a real vehicle.
