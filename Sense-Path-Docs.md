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
