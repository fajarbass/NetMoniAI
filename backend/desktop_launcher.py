import os
import sys
import time
import socket
import subprocess
import webbrowser
from typing import Optional

def _log(msg: str):
    if sys.stdout:
        try:
            print(msg, flush=True)
        except Exception:
            pass

def wait_for_port(port: int, host: str = "127.0.0.1", timeout: float = 12.0) -> bool:
    """Wait until the backend server is accepting connections."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except Exception:
            time.sleep(0.15)
    return False

def find_standalone_browser():
    """Find Google Chrome, Microsoft Edge, or Brave for native app-window mode."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c

    if sys.platform.startswith("win"):
        try:
            import winreg
            for name in ["chrome.exe", "msedge.exe", "brave.exe"]:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{name}") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val and os.path.exists(val):
                            return val
                except Exception:
                    pass
        except Exception:
            pass

    return None

_browser_proc = None

def is_browser_proc_alive() -> bool:
    global _browser_proc
    return _browser_proc is not None and _browser_proc.poll() is None

def get_browser_pid() -> Optional[int]:
    """Return PID of active standalone browser process, if running."""
    global _browser_proc
    if _browser_proc is not None and _browser_proc.poll() is None:
        return _browser_proc.pid
    return None

def open_browser_window(port: int, path: str, title: str):
    """Open or focus the standalone desktop browser window."""
    global _browser_proc

    # If browser process is already alive and running, focus its window
    if is_browser_proc_alive():
        try:
            from services.tray_service import get_app_window_hwnd
            hwnd = get_app_window_hwnd()
            if hwnd:
                import ctypes
                user32 = ctypes.windll.user32
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                return
        except Exception:
            pass

    # If no browser is running, launch a new window
    url = f"http://localhost:{port}{path}"
    browser_exe = find_standalone_browser() if sys.platform.startswith("win") else None
    
    if browser_exe:
        profile_dir = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "NetMoniAI", f"profile_{port}")
        os.makedirs(profile_dir, exist_ok=True)
        
        cmd = [
            browser_exe,
            f"--app={url}",
            f"--user-data-dir={profile_dir}",
            "--window-size=1400,900",
            f"--app-window-title={title}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-sync",
        ]
        print(f"[INFO] Opening Native Desktop Window via {os.path.basename(browser_exe)} for {url}...")
        try:
            _browser_proc = subprocess.Popen(cmd)
            _browser_proc.wait()
            _browser_proc = None
            
            # When closed, check if close/minimize to tray is enabled
            try:
                from settings_manager import settings_manager
                cfg = settings_manager.get_config()
                if cfg.system.close_to_tray or cfg.system.minimize_to_tray:
                    print("\n[INFO] Desktop window closed by user. Keeping NetMoniAI active in system tray...")
                    from services.tray_service import notify_tray
                    notify_tray(
                        "NetMoniAI Active",
                        "NetMoniAI continues running in the background. Access it anytime from the system tray."
                    )
                    return
            except Exception:
                pass

            print("\n[INFO] Desktop window closed by user. Shutting down NetMoniAI...")
            os._exit(0)
        except Exception as e:
            print(f"[ERROR] Native app mode failed: {e}, falling back to webview/browser.")
            _browser_proc = None

    # Fallback 1: pywebview
    try:
        import webview
        print("[INFO] Launching Native Window via pywebview...")
        webview.create_window(title=title, url=url, width=1400, height=900, min_size=(960, 640))
        webview.start()
        print("\n[INFO] Desktop window closed by user. Shutting down NetMoniAI...")
        os._exit(0)
    except Exception:
        pass

    # Fallback 2: Standard Browser
    try:
        webbrowser.open(url)
    except Exception:
        pass

def launch_desktop_app(port: int, path: str, title: str):
    """Launch the application in a dedicated standalone desktop window with system tray integration."""
    url = f"http://localhost:{port}{path}"
    print(f"\n[INFO] Starting NetMoniAI Desktop Window for {url}...")
    
    ready = wait_for_port(port)
    if not ready:
        print(f"[WARNING] Port {port} did not respond within timeout, attempting launch anyway.")

    # Initialize System Tray in background thread
    app_mode = os.getenv("APP_MODE", "agent")
    try:
        from services.tray_service import setup_tray_icon
        setup_tray_icon(
            app_mode=app_mode,
            port=port,
            dashboard_path=path,
            title=title,
            launcher_func=lambda: open_browser_window(port, path, title)
        )
    except Exception as e:
        print(f"[WARNING] System Tray could not be initialized: {e}")

    # If launched with --tray flag (e.g. from Windows boot startup), do not pop up window
    if "--tray" in sys.argv:
        print("[INFO] Started with --tray flag. Running silently in System Tray.")
        return

    open_browser_window(port, path, title)
