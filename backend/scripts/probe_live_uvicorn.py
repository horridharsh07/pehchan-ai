"""
Start live uvicorn server in a subprocess, wait for port 8000 to listen,
send live HTTP requests over loopback TCP socket, verify responses,
and terminate the server cleanly.
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
PYTHON_EXE = BACKEND / ".venv" / "Scripts" / "python.exe"

def get_free_port(start_port=8000):
    for port in range(start_port, start_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start_port

port = get_free_port(8000)
print(f"Starting uvicorn server on port {port} with {PYTHON_EXE}...")
proc = subprocess.Popen(
    [str(PYTHON_EXE), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
    cwd=str(BACKEND),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

try:
    # Wait for server to bind port
    url_root = f"http://127.0.0.1:{port}/"
    url_health = f"http://127.0.0.1:{port}/api/health"
    headers = {"x-engine-key": "7Y1Y-HdSwmRgARcVhOAdqbfYytDbG9muc1ROVqMqXhF_FWy0SyyvXOmfzNawd8Af"}

    connected = False
    for attempt in range(15):
        time.sleep(0.5)
        try:
            req = urllib.request.Request(url_root)
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    print(f"\n[LIVE PROBE 1] Successfully reached live server on 127.0.0.1:{port}! Status: {resp.status}")
                    print(f"Response: {json.dumps(data, indent=2)}")
                    connected = True
                    break
        except Exception:
            pass

    if not connected:
        out, err = proc.communicate(timeout=2)
        print("Server stdout:", out)
        print("Server stderr:", err)
        raise RuntimeError("Failed to connect to live uvicorn server after 7.5s")

    # Probe /api/health with engine key
    req_health = urllib.request.Request(url_health, headers=headers)
    with urllib.request.urlopen(req_health, timeout=5) as resp:
        health_data = json.loads(resp.read().decode())
        print(f"\n[LIVE PROBE 2] GET /api/health Status: {resp.status}")
        print(f"Health Response: {json.dumps(health_data, indent=2)}")

    print("\nLive server verified successfully on TCP 127.0.0.1:8000!")

finally:
    print("Terminating live uvicorn process...")
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("Uvicorn process cleanly terminated.")
