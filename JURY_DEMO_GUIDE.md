# Sense-Path: Demo Guide

Say only what the benchmark measured. Numbers below come from `ml_pipeline/benchmark_report.json`
(held-out driver, simulated outages on IO-VNBD); regenerate with `python ml_pipeline/benchmark_suite.py`.

## What to show (5 minutes)

1. **Start the edge engine** (`cd edge_engine && ./run_edge.sh`, open `/dashboard`). Say it replays a real
   recorded drive, interpolated to 200 Hz, standing in for an external FOG IMU.
2. **App -> Judge Demo -> Load Preset Scenario -> "Held-out drive, 90 s GNSS outage (5x)".**
   * First ~40 s: blue path, GNSS strong, HUD says it is calibrating mount axes from GNSS.
   * At the outage: badge turns red ("Blackout - IDR Active"); orange dashed path = dead reckoning; green
     = reference path (known only to the demo, never given to the engine); HUD shows the error vs reference
     as metres and % of distance driven.
   * When GNSS returns the position snaps back to GNSS.
3. **Data Source Mode -> Edge engine (200Hz)** to show the same core running on the external IMU stream.

## What to claim (and not)

* Claim: the learned model cuts naive dead-reckoning drift by more than half on a driver it never saw, and
  the same code runs on phone and edge.
* Claim: mount orientation is not assumed; forward and yaw axes are learned from GNSS before the outage.
* Do **not** claim the 10 % target is met reliably or that this was tested in a car. Expect the demo error
  to be roughly 10-15 % of distance on this scenario (91 m / 651 m in our runs), and larger on other windows.
* Do **not** call the 200 Hz feed a FOG: it is a replay.

## Measured results (held-out Driver A)

| Outage | Naive DR (hold speed) | SensePath median drift | Within 10 % |
|---|---|---|---|
| 50 m | 8.4 % | 7.4 % | 60 % |
| 1 km | 24.8 % | 9.4 % | 53 % |

Position error with the gyro heading at 1 km outages is ~280 m median: heading is the known weak point
(next step: magnetometer / road-heading constraint / HMM map matching).
