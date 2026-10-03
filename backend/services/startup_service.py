import os
import sys
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

REG_SUBKEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def get_app_name(app_mode: str = None) -> str:
    mode = app_mode or os.getenv("APP_MODE", "agent")
    return f"NetMoniAI-{mode.capitalize()}"

def get_executable_command(app_mode: str = None) -> str:
    """Resolve the command line to launch on Windows startup with --tray argument."""
    mode = app_mode or os.getenv("APP_MODE", "agent")
    if getattr(sys, 'frozen', False):
        exe_path = sys.executable
        return f'"{exe_path}" --tray'
    else:
        python_exe = sys.executable
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        entry_file = os.path.join(base_dir, f"{mode}_entry.py")
        return f'"{python_exe}" "{entry_file}" --tray'

def is_startup_enabled(app_mode: str = None) -> bool:
    """Check if the app is registered in Windows Startup registry."""
    if not sys.platform.startswith("win"):
        return False
    try:
        import winreg
        app_name = get_app_name(app_mode)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_READ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, app_name)
                return bool(val)
            except FileNotFoundError:
                return False
    except Exception as e:
        logger.error(f"Error checking startup registry: {e}")
        return False

def set_startup_enabled(enabled: bool, app_mode: str = None) -> bool:
    """Enable or disable auto-start on Windows boot via Registry."""
    if not sys.platform.startswith("win"):
        logger.warning("Startup registry configuration is only supported on Windows.")
        return False
    try:
        import winreg
        app_name = get_app_name(app_mode)
        if enabled:
            cmd = get_executable_command(app_mode)
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, cmd)
                logger.info(f"Registered Windows startup for '{app_name}': {cmd}")
            return True
        else:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_SET_VALUE) as key:
                try:
                    winreg.DeleteValue(key, app_name)
                    logger.info(f"Removed Windows startup for '{app_name}'")
                except FileNotFoundError:
                    pass
            return True
    except Exception as e:
        logger.error(f"Error modifying startup registry: {e}")
        return False

def get_startup_status(app_mode: str = None) -> Dict[str, Any]:
    """Get full startup status details."""
    app_name = get_app_name(app_mode)
    enabled = is_startup_enabled(app_mode)
    cmd = get_executable_command(app_mode)
    return {
        "enabled": enabled,
        "app_name": app_name,
        "command": cmd,
        "platform_supported": sys.platform.startswith("win")
    }
