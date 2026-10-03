import subprocess

import sys

# INTERFACE = "Wi-Fi"  # Network interface for capture
INTERFACE = "en0"
OUTPUT_FILE = "lastCapture/capture.pcap"

def collect_data_func(duration):
    """Capture network data using tshark."""
    cmd = ["tshark", "-i", INTERFACE, "-a", f"duration:{duration}", "-w", OUTPUT_FILE]
    kwargs = {}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    subprocess.run(cmd, **kwargs)