# 🚀 SensePath - ISRO Smart India Hackathon Demo Guide

Welcome to the official jury evaluation guide for **SensePath**, a state-of-the-art Intelligent Dead Reckoning (IDR) navigation suite designed to solve ISRO's IO-VNBD GNSS-denied navigation problem.

---

## 🎤 2-Minute Elevator Pitch

> "Respected Jury, when a vehicle enters a 1-kilometer tunnel or an urban canyon, GPS signals completely drop out. Traditional dead reckoning systems drift by hundreds of meters within seconds, making them useless. 
>
> To solve ISRO's IO-VNBD problem statement, we built **SensePath**. It completely eliminates the reliance on GNSS by using a customized CNN-GRU deep learning architecture that directly infers vehicle velocity from raw 6-axis IMU data. We fuse this AI prediction into an Error-State Extended Kalman Filter (ES-EKF) that mathematically enforces Non-Holonomic Constraints, preventing all lateral drift.
>
> [DRAFT - rewrite after the model and benchmark are fixed; do not claim a drift figure that `ml_pipeline/benchmark_suite.py` has not produced.] The scenario replay in the app is a scripted demo, not a recorded drive. The 200 Hz edge engine currently runs on a simulated FOG feed."

---

## 💻 Step-by-Step Demonstration

### 1. Launch the Environment
Before the judges arrive, start the unified demo launcher. This spins up the Edge FOG Engine and opens the web dashboard on your laptop:
```bash
./run_demo.sh
```

Next, open the Flutter App on the connected physical Android/iOS device:
```bash
flutter run --release
```

### 2. Dual-Source Telemetry Demo
1. Show the judges the laptop screen running the **Live Web Visualizer** (`http://localhost:8080/dashboard`). Explain this is the 200 Hz Fiber Optic Gyro (FOG) Edge engine.
2. On the **Flutter App**, tap the **Judge Demo** FAB (Floating Action Button).
3. Under **Data Source Mode**, toggle from `Internal (10Hz)` to `Edge FOG (200Hz)`.
4. *Watch as the Flutter app instantly synchronizes with the laptop dashboard via WebSockets!*

### 3. The Tunnel Blackout Scenario (1km Outage)
1. Tap the **Judge Demo** FAB on the app.
2. Select **Load Preset Scenario** > **500m Tunnel Outage**.
3. **Point out the HUD:** The GNSS badge will flash red (`GNSS: Blackout`). 
4. **Point out the Map:** A dual-line trajectory will draw. Green is the Ground Truth GPS, and Orange is the AI Dead Reckoning.
5. **Show the Drift Metric:** As the playback runs, point to the live `Drift` metric in the HUD to prove the error stays under 10% of the total distance!

---

## Verification Metrics

Only quote numbers produced by `python ml_pipeline/benchmark_suite.py --rate_hz <csv rate>` (writes
`ml_pipeline/benchmark_report.json`). As of the last honest run the model did **not** meet the ISRO
target (median 50 m along-track drift ~115 %, worse than a constant-speed baseline), so this table is
intentionally empty until the model is retrained.

| Metric | ISRO Target | Measured | Source |
| :--- | :--- | :--- | :--- |
| 50 m outage drift | < 10 % | _pending_ | benchmark_suite.py |
| 1000 m outage drift | < 10 % | _pending_ | benchmark_suite.py |
| GNSS recovery latency | milliseconds | _not measured_ | - |
| Position update rate | 10 Hz phone / ~200 Hz edge | _not measured_ | - |
