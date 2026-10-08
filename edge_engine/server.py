import asyncio
import json
import time

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from edge_fusion import EdgeFusionEngine, IMU_HZ
from replay_streamer import ReplaySource

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

source = ReplaySource()
health = {"status": "idle", "achieved_hz": 0.0, "sessions": 0, "mode": None,
          "avg_ai_latency_ms": 0.0, "avg_tick_ms": 0.0, "max_tick_ms": 0.0}


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket, speed: int = 1):
    """One replay session per client. `speed` = replay time compression (IMU samples per 5 ms cycle)."""
    await websocket.accept()
    speed = max(1, min(speed, 20))
    health["sessions"] += 1
    try:
        while True:                                              # loop the replay
            engine = EdgeFusionEngine()
            i, sent, t_start = 0, 0, time.perf_counter()
            while i < source.n:
                state = None
                for _ in range(speed):
                    if i >= source.n:
                        break
                    s = source.tick(i)
                    state = engine.update(s) or state
                    i += 1
                if state is not None:
                    await websocket.send_text(json.dumps({"timestamp": time.time(), "state": state}))
                    sent += 1
                    health.update(mode=state["mode"], status="streaming", **engine.stats(),
                                  achieved_hz=round(sent / max(time.perf_counter() - t_start, 1e-6), 1))
                # fixed deadlines (not 'sleep the remainder') so scheduling overhead does not accumulate
                await asyncio.sleep(max(0.0, t_start + (sent) / IMU_HZ - time.perf_counter()))
            await asyncio.sleep(3)
    except Exception as e:  # client disconnected
        print(f"Connection closed: {e}")
    finally:
        health["sessions"] -= 1
        if health["sessions"] <= 0:
            health["status"] = "idle"


@app.get("/health")
async def get_health():
    return {**health, "imu_frequency_hz": IMU_HZ, "imu_source": "replay of held-out IO-VNBD drive, interpolated 10->200 Hz"}


@app.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard():
    with open("static/dashboard.html", "r") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
