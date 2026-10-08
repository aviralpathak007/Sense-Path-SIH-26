import onnxruntime as ort
import numpy as np
import time

class EdgeFusionEngine:
    def __init__(self, model_path='../assets/model.onnx'):
        # Initialize ONNX Runtime session for high-rate edge inference
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        
        # State vector
        self.lat = 0.0
        self.lon = 0.0
        self.vx = 0.0
        self.psi = 0.0
        
        # 1-second sliding window buffer for AI
        # Model expects 100Hz equivalent, so we decimate 200Hz to 100Hz
        self.buffer = []
        self.frame_count = 0
        
        self.last_time = time.time()
        self.process_times = []

    def update(self, imu_data):
        now = time.time()
        dt = now - self.last_time
        self.last_time = now

        # High-rate dead reckoning propagation (200 Hz)
        forward_accel = imu_data['ay']  # Simplified
        yaw_rate = imu_data['gz']       # Simplified
        
        self.psi += yaw_rate * dt
        self.vx += forward_accel * dt
        if self.vx < 0: self.vx = 0
        
        # Very simplified planar update
        R = 6371000.0
        dist = self.vx * dt
        dLat = dist * np.cos(self.psi) / R
        dLon = dist * np.sin(self.psi) / (R * np.cos(self.lat * np.pi / 180.0) if self.lat != 0 else 1)
        
        self.lat += dLat * 180.0 / np.pi
        self.lon += dLon * 180.0 / np.pi

        # AI Prediction (run at 10 Hz over 1-sec window)
        # Decimate 200Hz -> 100Hz
        if self.frame_count % 2 == 0:
            self.buffer.append([
                imu_data['ax'], imu_data['ay'], imu_data['az'],
                imu_data['gx'], imu_data['gy'], imu_data['gz']
            ])
            if len(self.buffer) > 100:
                self.buffer.pop(0)
                
            # Run inference every 20 frames (10 Hz)
            if len(self.buffer) == 100 and self.frame_count % 20 == 0:
                start_inf = time.perf_counter()
                
                # Shape [1, 6, 100]
                tensor = np.array(self.buffer, dtype=np.float32).T
                tensor = np.expand_dims(tensor, axis=0)
                
                result = self.session.run(None, {self.input_name: tensor})
                ai_velocity = float(result[0][0][0])
                
                end_inf = time.perf_counter()
                self.process_times.append((end_inf - start_inf) * 1000)
                if len(self.process_times) > 100:
                    self.process_times.pop(0)
                
                # Fusion (Trust AI)
                self.vx = self.vx * 0.1 + ai_velocity * 0.9

        self.frame_count += 1
        
        return {
            "lat": self.lat,
            "lon": self.lon,
            "speed": self.vx,
            "bearing": self.psi * 180.0 / np.pi
        }
    
    def get_avg_inference_latency(self):
        if not self.process_times: return 0.0
        return sum(self.process_times) / len(self.process_times)
