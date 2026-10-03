import os
import shutil
import platform
import socket
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

def get_network_interfaces() -> List[Dict[str, Any]]:
    """Enumerate network interfaces and their statuses across platforms."""
    interfaces = []

    try:
        import psutil
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        for iface_name, addr_list in addrs.items():
            is_up = stats[iface_name].isup if iface_name in stats else False
            speed = stats[iface_name].speed if iface_name in stats else 0
            
            ipv4_list = [a.address for a in addr_list if a.family == socket.AF_INET]
            mac_list = [a.address for a in addr_list if getattr(a, 'family', None) == getattr(psutil, 'AF_LINK', None)]

            is_loopback = iface_name.lower().startswith("lo") or (ipv4_list and ipv4_list[0].startswith("127."))
            
            interfaces.append({
                "name": iface_name,
                "is_up": is_up,
                "speed_mbps": speed,
                "ipv4": ipv4_list[0] if ipv4_list else None,
                "mac": mac_list[0] if mac_list else None,
                "is_loopback": is_loopback,
            })
    except ImportError:
        # Standard library fallback if psutil is not yet installed
        try:
            hostname = socket.gethostname()
            _, _, ip_list = socket.gethostbyname_ex(hostname)
            for ip in ip_list:
                interfaces.append({
                    "name": f"Interface ({ip})",
                    "is_up": True,
                    "speed_mbps": 1000,
                    "ipv4": ip,
                    "mac": None,
                    "is_loopback": ip.startswith("127."),
                })
        except Exception:
            interfaces.append({
                "name": "Default Interface",
                "is_up": True,
                "speed_mbps": 100,
                "ipv4": "127.0.0.1",
                "mac": None,
                "is_loopback": False,
            })

    interfaces.sort(key=lambda x: (not x["is_up"], x.get("is_loopback", False), x["name"]))
    return interfaces

def get_default_interface_name() -> str:
    """Find the best candidate interface for packet capture."""
    interfaces = get_network_interfaces()
    for iface in interfaces:
        if iface.get("is_up") and not iface.get("is_loopback") and iface.get("ipv4"):
            return iface["name"]
    return interfaces[0]["name"] if interfaces else "auto"

def get_tshark_path(custom_path: Optional[str] = None) -> Optional[str]:
    """Locate tshark binary with cross-platform fallback."""
    if custom_path and os.path.exists(custom_path):
        return custom_path

    path = shutil.which("tshark")
    if path:
        return path

    sys_name = platform.system()
    if sys_name == "Windows":
        win_candidates = [
            r"C:\Program Files\Wireshark\tshark.exe",
            r"C:\Program Files (x86)\Wireshark\tshark.exe",
        ]
        for c in win_candidates:
            if os.path.exists(c):
                return c
    elif sys_name == "Darwin":
        mac_candidates = [
            "/usr/local/bin/tshark",
            "/opt/homebrew/bin/tshark",
        ]
        for c in mac_candidates:
            if os.path.exists(c):
                return c
    elif sys_name == "Linux":
        linux_candidates = [
            "/usr/bin/tshark",
            "/usr/local/bin/tshark",
        ]
        for c in linux_candidates:
            if os.path.exists(c):
                return c

    return None

def get_default_gateway_ip() -> str:
    """Detect default router / gateway IP."""
    try:
        import netifaces
        gws = netifaces.gateways()
        default_gw = gws.get('default', {}).get(netifaces.AF_INET)
        if default_gw:
            return default_gw[0]
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
