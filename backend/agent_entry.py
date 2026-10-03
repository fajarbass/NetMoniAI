import os
import sys
import threading
import time

# Ensure backend directory is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ["APP_MODE"] = "agent"

# In PyInstaller --noconsole mode, redirect stdout/stderr to a dedicated log file
if sys.stdout is None or sys.stderr is None:
    log_dir = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "NetMoniAI", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "agent.log")
    try:
        _log_fh = open(log_file, "a", buffering=1, encoding="utf-8")
        sys.stdout = _log_fh
        sys.stderr = _log_fh
    except Exception:
        pass

import uvicorn
from app import app
from desktop_launcher import launch_desktop_app

if __name__ == "__main__":
    port = int(os.getenv("APP_PORT", 8001))

    # Enforce single active instance on Windows
    from services.single_instance import SingleInstance
    _single_instance = SingleInstance(app_mode="agent", port=port)
    _single_instance.check_or_exit()
    print("=" * 60)
    print("       NetMoniAI - Endpoint Monitoring Desktop         ")
    print("=" * 60)
    print(f" [+] Mode:         ENDPOINT AGENT (CLIENT)")
    print(f" [+] Desktop UI:   http://localhost:{port}/")
    print(f" [+] Settings:     http://localhost:{port}/settings")
    print(f" [+] API Docs:     http://localhost:{port}/docs")
    print("=" * 60)

    # Launch dedicated desktop application window
    threading.Thread(
        target=launch_desktop_app,
        args=(port, "/", "NetMoniAI Endpoint Agent"),
        daemon=True
    ).start()

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
