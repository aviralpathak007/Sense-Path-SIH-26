import asyncio
import time
import math
import random

class FOGStreamer:
    """
    Simulates a high-precision Fiber Optic Gyroscope (FOG) IMU running at 200 Hz.
    In production, this would read from a serial port or UDP socket.
    """
    def __init__(self, frequency=200):
        self.frequency = frequency
        self.interval = 1.0 / frequency
        self.running = False

    async def stream_data(self, callback):
        self.running = True
        print(f"Started FOG IMU stream at {self.frequency} Hz")
        while self.running:
            # Simulate high-precision IMU data
            # Fiber optic gyros have incredibly low noise profiles
            ax = random.gauss(0, 0.001)
            ay = random.gauss(1.0, 0.005)  # slight forward accel
            az = random.gauss(9.81, 0.001)
            
            gx = random.gauss(0, 0.0001)
            gy = random.gauss(0, 0.0001)
            gz = random.gauss(0.01, 0.0001) # slight turn

            timestamp = time.time()
            data = {
                "timestamp": timestamp,
                "ax": ax, "ay": ay, "az": az,
                "gx": gx, "gy": gy, "gz": gz
            }
            
            await callback(data)
            await asyncio.sleep(self.interval)

    def stop(self):
        self.running = False
