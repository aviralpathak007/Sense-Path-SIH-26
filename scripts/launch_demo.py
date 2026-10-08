import os
import subprocess
import time
import webbrowser
import signal
import sys
import threading

GREEN = '\033[92m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

edge_process = None

def signal_handler(sig, frame):
    print(f"\n{RED}[!] SIGINT Received. Shutting down SensePath ISRO Demonstration...{RESET}")
    if edge_process:
        edge_process.terminate()
        edge_process.wait()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def print_banner():
    print(f"""{CYAN}
  ____                      ____       _   _     
 / ___|  ___ _ __ ___  ___|  _ \ __ _| |_| |__  
 \___ \ / _ \ '_ ` _ \/ __| |_) / _` | __| '_ \ 
  ___) |  __/ | | | | \__ \  __/ (_| | |_| | | |
 |____/ \___|_| |_| |_|___/_|   \__,_|\__|_| |_|
                                                
 ISRO Smart India Hackathon 2026
================================================={RESET}
    """)

def check_dependencies():
    print(f"{YELLOW}[*] Checking Dependencies...{RESET}")
    if not os.path.exists("edge_engine/venv/bin/python3") and not os.path.exists("edge_engine/venv/Scripts/python.exe"):
        print(f"{RED}[!] Edge Engine venv not found. Please run `./edge_engine/run_edge.sh` once first.{RESET}")
        sys.exit(1)
    print(f"{GREEN}[✓] Dependencies OK.{RESET}")

def start_edge_server():
    global edge_process
    print(f"{YELLOW}[*] Booting 200 Hz Edge Engine...{RESET}")
    
    python_path = "venv/bin/python3" if os.name != 'nt' else "venv/Scripts/python.exe"
    
    edge_process = subprocess.Popen(
        [python_path, "server.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd="edge_engine"
    )
    time.sleep(2) # Give FastAPI time to bind
    if edge_process.poll() is None:
        print(f"{GREEN}[✓] Edge Engine LIVE on http://localhost:8080{RESET}")
    else:
        print(f"{RED}[!] Edge Engine failed to start.{RESET}")
        sys.exit(1)

def launch_dashboard():
    print(f"{YELLOW}[*] Launching Jury Evaluation Dashboard...{RESET}")
    webbrowser.open("http://localhost:8080/dashboard")
    print(f"{GREEN}[✓] Dashboard active.{RESET}")

def print_status_board():
    print(f"\n{CYAN}============= SYSTEM STATUS ============={RESET}")
    print(f"{GREEN}● WebSocket Server:{RESET} ws://localhost:8080/ws/telemetry")
    print(f"{GREEN}● Inference Backend:{RESET} ONNX Runtime (CPUExecutionProvider)")
    print(f"{GREEN}● IMU Rate:{RESET} 200 Hz (replay of a held-out drive, interpolated from 10 Hz; not a real FOG)")
    print(f"{CYAN}========================================={RESET}")
    print(f"\n{YELLOW}Shortcuts:{RESET}")
    print(" - Press Ctrl+C to cleanly terminate the demo.")
    print(" - On the Flutter App, use the Judge Demo button to replay the held-out outage scenario.")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Move to project root
    print_banner()
    check_dependencies()
    start_edge_server()
    launch_dashboard()
    print_status_board()
    
    # Keep main thread alive to catch SIGINT
    while True:
        time.sleep(1)
