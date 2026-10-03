import asyncio
import subprocess
import sys
import re
import socket

def get_subprocess_flags() -> dict:
    """Return creationflags and startupinfo to ensure child processes (like ping or tshark)
    run completely hidden in the background without opening or flashing console windows on Windows."""
    kwargs = {}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            kwargs["startupinfo"] = startupinfo
        except Exception:
            pass
    return kwargs

async def get_ping_metrics(host: str, count: int = 4, timeout: int = 2) -> dict:
    """Retrieve ping metrics asynchronously without spawning console windows."""
    cmd = ["ping", "-n" if sys.platform.startswith("win") else "-c", str(count),
           "-w" if sys.platform.startswith("win") else "-W", str(timeout * 1000 if sys.platform.startswith("win") else timeout), host]
    try:
        kwargs = {
            "stderr": subprocess.STDOUT,
            "universal_newlines": True,
            **get_subprocess_flags()
        }
        output = await asyncio.to_thread(subprocess.check_output, cmd, **kwargs)
        loss_match = re.search(r"(\d+)% (packet )?loss", output)
        packet_loss = float(loss_match.group(1)) if loss_match else None
        avg_match = re.search(r"Average = (\d+)ms|min/avg/max[^=]+ = [\d\.]+/([\d\.]+)/", output)
        avg_latency = float(avg_match.group(1) or avg_match.group(2)) if avg_match else None
        return {"packet_loss": packet_loss, "avg_latency": avg_latency}
    except (subprocess.CalledProcessError, Exception):
        return {"packet_loss": None, "avg_latency": None}

def get_default_gateway() -> str:
    """Retrieve the default gateway IP address with netifaces or socket fallback."""
    try:
        import netifaces
        gateways = netifaces.gateways()
        return gateways['default'][netifaces.AF_INET][0]
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        parts = local_ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.{parts[2]}.1"
    except Exception:
        pass

    return "192.168.1.1"