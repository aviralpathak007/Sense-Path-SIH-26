import asyncio
import json
from fastapi import FastAPI, WebSocket
from edge_fusion import EdgeFusionEngine
from fog_streamer import FOGStreamer

app = FastAPI()
fusion_engine = EdgeFusionEngine()
streamer = FOGStreamer(frequency=200)

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    
    # Callback to handle each 200 Hz IMU tick
    async def process_tick(imu_data):
        # 1. Run fusion
        state = fusion_engine.update(imu_data)
        
        # 2. Stream PVA state back to client
        payload = {
            "timestamp": imu_data["timestamp"],
            "state": state
        }
        await websocket.send_text(json.dumps(payload))
        
    try:
        await streamer.stream_data(process_tick)
    except Exception as e:
        print(f"Connection closed: {e}")
    finally:
        streamer.stop()

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "imu_frequency_hz": streamer.frequency,
        "avg_ai_latency_ms": round(fusion_engine.get_avg_inference_latency(), 2)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
