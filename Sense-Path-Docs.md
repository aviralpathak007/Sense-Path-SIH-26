# Sense-Path-Docs

## Overview

SensePath is an Intelligent Dead Reckoning (IDR) navigation system built with Flutter. It is designed to function fully offline, track vehicle kinematics continuously (10-50 Hz), and seamlessly handle GNSS blackouts using smartphone IMU sensors (accelerometer and gyroscope). 

This documentation serves as a comprehensive guide to the architecture, state management, and implementation details of the application for future reference and learning.

## Table of Contents

1. [Architecture & Patterns](#architecture--patterns)
2. [Core Components](#core-components)
    - [State Management (Riverpod)](#state-management-riverpod)
    - [Background Processing (Dart Isolates)](#background-processing-dart-isolates)
    - [Sensor Integration](#sensor-integration)
3. [User Interface (UI)](#user-interface-ui)
    - [Navigation Map](#navigation-map)
    - [Heads-Up Display (HUD)](#heads-up-display-hud)
    - [Hackathon Demo Controls](#hackathon-demo-controls)
4. [File Structure Overview](#file-structure-overview)
5. [Phase 2: ML Pipeline & Kinematics Engine](#phase-2-ml-pipeline--kinematics-engine)
    - [Dataset Preprocessing (IO-VNBD)](#dataset-preprocessing-io-vnbd)
    - [CNN-GRU Architecture](#cnn-gru-architecture)
    - [Benchmarks & Evaluation](#benchmarks--evaluation)
    - [Training & Export Instructions](#training--export-instructions)

---

## Architecture & Patterns

The application follows a **Feature-First Clean Architecture**, separating the application into distinct layers:

- **Data Layer:** Responsible for fetching raw data from hardware sensors (`sensors_plus`, `geolocator`) and defining the data models.
- **Domain Layer:** Contains the core business logic, including the Dead Reckoning (DR) math engine running in a background isolate, and the Riverpod providers that orchestrate state changes.
- **Presentation Layer:** Contains purely UI components (widgets, screens) that react to the state provided by the Domain Layer.

---

## Core Components

### State Management (Riverpod)

The application uses `NotifierProvider` from the `flutter_riverpod` package to manage the `KinematicsState`.

- **`KinematicsState`:** An immutable data class containing the current vehicle position, bearing, speed, cumulative drift, GNSS status, and historical paths.
- **`NavigationNotifier`:** A `Notifier` class that initializes the sensor services and the DR engine. It listens to the updates from the background isolate and updates the UI state reactively.

### Background Processing (Dart Isolates)

To maintain a smooth 60/120 FPS UI, all heavy math and constant sensor stream processing are offloaded to a **Dart Isolate**.

- **`DeadReckoningEngine`:** Uses `Isolate.spawn` to create an independent thread of execution.
- **Communication:** The main UI thread and the Isolate communicate via `SendPort` and `ReceivePort`. 
  - The UI sends `UpdateSensorMsg` and `UpdateGpsMsg`.
  - The Isolate processes these using Haversine formulas and simplified matrix math, then sends back `EngineStateUpdate` containing the new coordinates and drift metrics.

### Sensor Integration

The `SensorService` class bridges the hardware to the software.
- **`geolocator`:** Streams raw GPS fixes when available.
- **`sensors_plus`:** Streams `userAccelerometerEventStream` and `gyroscopeEventStream` at `SensorInterval.gameInterval` (~50 Hz) to capture rapid vehicle kinematics.

---

## User Interface (UI)

### Navigation Map

Built using `flutter_map` and `latlong2`, ensuring offline capability by caching OpenStreetMap tiles.

- **Dual-Path Rendering:** The map utilizes `PolylineLayer` to draw the historical ground-truth path (Solid Green) and the AI Dead Reckoning trajectory (Dashed Orange).
- **Custom Puck:** The vehicle marker (`CustomPuck.dart`) uses `AnimatedRotation` to smoothly interpolate (slerp) the bearing angle as updates arrive.

### Heads-Up Display (HUD)

- **`GnssBadge`:** A dynamic top app bar chip that changes color based on the current `GnssStatus` (Strong/Green, Degraded/Orange, Blackout/Red).
- **`TelemetryHud`:** A bottom panel that reads out the current AI-predicted velocity, cumulative drift (meters), and alignment matrix status.

### Hackathon Demo Controls

A Floating Action Button opens a bottom sheet with tools for testing the app in a controlled environment:
- **Simulate GNSS Outage:** Instantly cuts off the `geolocator` feed and forces the app to rely purely on the IMU Dead Reckoning isolate.
- **Load Preset Scenario:** (Placeholder) Designed to load pre-recorded JSON/CSV kinematics data like the IO-VNBD dataset.
- **Calibrate Mount:** Simulates the phone-to-vehicle reference frame re-alignment routine.

---

## File Structure Overview

```text
lib/
├── data/
│   ├── models/
│   │   └── kinematics.dart          # Data structures for state & sensor payload
│   └── sensors/
│       └── sensor_service.dart      # Streams IMU and GPS data
├── domain/
│   ├── dr_engine/
│   │   └── dead_reckoning_engine.dart # Dart Isolate running the math computations
│   └── providers/
│       └── navigation_provider.dart # Riverpod state manager
├── presentation/
│   ├── screens/
│   │   └── navigation_map_screen.dart # Main view with MapLibre/flutter_map
│   └── widgets/
│       ├── custom_puck.dart         # Animated navigation marker
│       ├── hackathon_controls.dart  # Judge Demo toggle/simulators
│       └── hud_overlay.dart         # Telemetry & GNSS status chips
└── main.dart                        # ProviderScope & Theme Entry Point
```

## Setup & Run Instructions

1. Ensure your device has location permissions enabled.
2. For iOS, ensure `NSLocationWhenInUseUsageDescription` is in `ios/Runner/Info.plist`.
3. For Android, ensure `android.permission.ACCESS_FINE_LOCATION` is in `android/app/src/main/AndroidManifest.xml`.
4. Run the app: `flutter run`

---

## Phase 2: ML Pipeline & Kinematics Engine

The Intelligent Dead Reckoning (IDR) relies on a deep learning model to estimate forward velocity purely from IMU data during GNSS blackouts. The pipeline is located in the `ml_pipeline` folder and uses PyTorch.

### Dataset Preprocessing (IO-VNBD)

The IO-VNBD dataset provides synchronized vehicle GPS and smartphone IMU telemetry. The pipeline prepares this data as follows:
- **Feature Extraction**: 6-axis IMU data (3-axis accelerometer and 3-axis gyroscope) is extracted and Z-score normalized.
- **Sliding Windows**: The continuous data stream is chunked into 1-second sequences (100 samples at 100 Hz) using a sliding window approach with a 50% overlap.
- **Target Value**: The ground-truth forward vehicle velocity at the end of the sliding window is extracted from GPS/odometry columns for supervision.

### CNN-GRU Architecture

The core of the kinematics engine is the `KinematicVelocityNet` (`model.py`), which leverages a hybrid deep learning architecture:
1. **1D CNN Layer**: Acts as a high-frequency filter, using two convolutional blocks (`Conv1d` + `ReLU` + `MaxPool1d`) to suppress road vibrations and isolate vehicle dynamics.
2. **Bidirectional GRU**: A 2-layer BiGRU captures the complex temporal dependencies and integration mechanics required to convert acceleration events into velocity states over the window period.
3. **Dense Regression Head**: The output of the final time step is passed through a dense layer with dropout, producing a single continuous output predicting the current forward velocity in m/s.

### Benchmarks & Evaluation

The pipeline includes an evaluation script (`evaluate.py`) that runs inference on a test sequence and generates a matplotlib chart (`drift_benchmark.png`). This benchmark compares:
- **Ground Truth Velocity**: The true speed recorded by vehicle odometry.
- **Raw Double-Integration**: A classical naive approach plotting velocity from integrating forward acceleration, demonstrating rapid exponential drift.
- **AI-Predicted Velocity**: The stable, drift-corrected predictions from the `KinematicVelocityNet`.

### Training & Export Instructions

The ML pipeline is designed to automatically detect and utilize Apple Silicon `mps` or Nvidia `cuda` acceleration, falling back to CPU.

**Dependencies:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install torch pandas numpy matplotlib onnx
```

**1. Preparing the Real Dataset:**
Extract the raw Git LFS IO-VNBD dataset using the included python script to format it for our model (this fetches the true dataset, not the LFS pointers!):
```bash
python3 prepare_data.py
```

**2. Training the Model:**
Run the training script with paths to your train and validation IO-VNBD splits. It uses Mean Squared Error (MSE) loss, the Adam optimizer, and implements early stopping based on validation loss.
```bash
python3 ml_pipeline/train.py --train_csv data/train_iovnbd.csv --val_csv data/val_iovnbd.csv
```

**3. Running the Benchmark:**
Generate the drift benchmark plot against a test sequence:
```bash
python3 ml_pipeline/evaluate.py --test_csv data/test_iovnbd.csv
```

**4. Exporting for Edge Deployment (ONNX):**
Convert the PyTorch `.pt` weights directly to `.onnx`. We bypass TFLite to avoid Apple Silicon C++ mutex compilation deadlocks:
```bash
python3 ml_pipeline/export_onnx.py
```
This generates `model.onnx` which is moved to the `assets/` directory of the Flutter app.

### Flutter ONNX Integration

We use the official `onnxruntime` package for Flutter to execute the kinematics model directly in a Dart Isolate.
- **`onnx_runner.dart`**: Contains the `OnnxVelocityEstimator` class that initializes the `OrtEnv` and `OrtSession` using the `model.onnx` asset.
- **Input**: Accepts a 600-element `Float32List` representing the 1-second 6-axis IMU window (`1x6x100` tensor).
- **Output**: Predicts real-time velocity instantly on the device, bridging the AI into the `DeadReckoningEngine` for continuous navigation during GPS blackouts!

---

## Phase 3: Sensor Fusion, Kinematic Constraints & Map Matching

Phase 3 implements the full robotics math stack inside the Dart Isolate to translate raw AI predictions and sensor telemetry into map-matched geospatial coordinates.

### 1. Frame Auto-Alignment Engine
The smartphone can be mounted in any arbitrary orientation. The `AlignmentCalibrator` dynamically resolves the `R_phone_to_vehicle` rotation matrix by:
- **Gravity Extraction**: Low-pass filtering stationary accelerometer data to find the global "Down" (Z) axis.
- **Dynamic Forward Axis**: Monitoring acceleration during initial vehicle motion to find the "Forward" (X) axis orthogonal to gravity.
- **Cross Product**: Deriving the lateral (Y) axis, forming a complete frame transformation.

### 2. Error-State Extended Kalman Filter (ES-EKF)
The `KalmanFilter` maintains a highly optimized 5DOF state vector `[Latitude, Longitude, Velocity (vx), Yaw (psi), Gyro Bias (b_psi)]`. 
- **Prediction**: Runs continuously at 50Hz, integrating yaw rate and forward acceleration.
- **Measurement Update**: Corrects drift when GNSS fixes are available at 1Hz using a complementary gain architecture.
- **Non-Holonomic Constraints (NHC)**: During GNSS denial, lateral velocity is strictly constrained to 0, completely eliminating the infamous sideways drift common in dead reckoning.
- **Zero-Velocity Update (ZUPT)**: If the AI network predicts velocity < 0.2 m/s, the filter clamps the speed to 0.0 and aggressively halts all heading integration to prevent standstill rotation drift.

### 3. Offline Map Matching
To guarantee <10% drift during extended urban canyon/tunnel blackouts, `MapMatcher` ingests a raw GeoJSON file (`sample_road_network.json`) into memory.
- During outages, if the vehicle's heading is parallel to a known road segment (within 45 degrees), the estimated coordinates are strictly snapped onto the road polyline geometry.

---

## Phase 4: Scenario Replay & 200 Hz Edge Engine

### 1. Flutter Scenario Playback Engine
To facilitate interactive judging and demonstrations without driving the vehicle, SensePath includes a live scenario replay system (`ScenarioPlayer`).
- **Data Source**: Pre-packaged JSON datasets in `assets/scenarios/` (e.g., `tunnel_blackout_scenario.json`) simulate 6-axis IMU strings, GPS fixes, and GNSS-denial flags.
- **Execution**: Tapping "Load Preset Scenario" in the `HackathonControls` FAB streams this JSON payload into the `DeadReckoningEngine` isolate at 10Hz. 
- **Validation**: During the playback, a dual-line trajectory tracks both the Ground Truth GPS (Green Line) against the AI Dead Reckoning estimate (Orange Line). The `TelemetryHud` displays real-time `Drift` metrics in meters using Haversine distance, ensuring visually verifiable <10% cumulative drift constraints.

### 2. Standalone Edge Deployable Engine (FOG IMU)
To meet the ISRO constraints for high-precision, external edge node processing (such as a Raspberry Pi or Nvidia Jetson wired to a Fiber Optic Gyroscope), the system features a headless Python service inside `edge_engine/`.
- **FOG Streamer**: Simulates a high-rate 200 Hz external IMU feed.
- **Asynchronous ES-EKF Fusion**: A highly optimized version of the filter decodes the 200 Hz feed, performing state prediction at 200 Hz, while asynchronously decimating the input to 100Hz 1-second rolling windows to query the ONNX AI model natively via `CPUExecutionProvider`.
- **WebSocket Streaming**: Exposes a real-time `/ws/telemetry` WebSocket broadcasting 5-DOF Position-Velocity-Attitude (PVA) states.
- **Usage**:
  ```bash
  cd edge_engine
  ./run_edge.sh
  ```
  Check the performance via `curl http://localhost:8080/health`.

---

## Phase 5: Demonstration Suite, Edge Sync & ISRO Benchmark Verification

### 1. Flutter Dual-Source Telemetry Sync
The mobile application features a runtime toggle allowing judges to switch the active navigation telemetry source:
- **Mode A (Smartphone 10 Hz)**: Completely edge-independent, running inference on the local device SoC.
- **Mode B (Edge FOG 200 Hz)**: Bypasses the local sensor engine. Instead, a Dart `WebSocketChannel` connects to the Edge Engine (`ws://localhost:8080/ws/telemetry`) and consumes external PVA state data seamlessly plotting it onto the flutter UI Map.

### 2. Automated ISRO Benchmark Suite
The project evaluates IO-VNBD dataset compliance through `ml_pipeline/benchmark_suite.py`.
- Computes **Maximum & Average Drift** (< 5 m over 50m outage).
- Computes **Cumulative Drift Percentage** (< 10% over 1000m outage).
- Automatically generates publication-quality data plots (`isro_benchmark_comparison.png`) and validation JSON reports.

### 3. Live Web Dashboard
For headless edge systems, the python backend serves a live UI telemetry dashboard at `http://localhost:8080/dashboard`.
- Uses `Leaflet.js` mapped directly to the `WebSocket` broadcast.
- Provides a desktop-scale presentation layer perfect for the jury to monitor real-time AI dead reckoning logic alongside the mobile client!
