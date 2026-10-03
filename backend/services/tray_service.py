import os
import sys
import threading
import logging
from typing import Optional, Callable
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

_tray_instance = None
_window_launcher_callback = None

def create_tray_icon_image(size: int = 64) -> Image.Image:
    """Generate a crisp, high-resolution cyber sentinel shield icon."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Outer shield polygon points
    pts = [
        (size * 0.50, size * 0.08), 
        (size * 0.88, size * 0.22), 
        (size * 0.78, size * 0.74), 
        (size * 0.50, size * 0.94), 
        (size * 0.22, size * 0.74), 
        (size * 0.12, size * 0.22)
    ]
    # Dark modern background with cyan glowing border
    d.polygon(pts, fill=(11, 15, 25, 255), outline=(0, 212, 255, 255), width=3)
    # Inner accent polygon
    inner_pts = [
        (size * 0.50, size * 0.20),
        (size * 0.76, size * 0.30),
        (size * 0.68, size * 0.68),
        (size * 0.50, size * 0.82),
        (size * 0.32, size * 0.68),
        (size * 0.24, size * 0.30)
    ]
    d.polygon(inner_pts, outline=(0, 163, 255, 180), width=1)
    # Central emerald/cyan radar node
    d.ellipse([(size * 0.40, size * 0.40), (size * 0.60, size * 0.60)], fill=(0, 255, 180, 255))
    return img

EXCLUDED_CLASSES = {
    "cabinetwclass",
    "explorewclass",
    "workerw",
    "progman",
    "shell_traywnd",
    "consolewindowclass",
    "windows.ui.core.corewindow",
}

VALID_BROWSER_CLASSES = {
    "chrome_widgetwin_1",
    "webview2",
    "pywebviewwindow",
}

def get_app_window_hwnd() -> Optional[int]:
    """Find the NetMoniAI desktop application window handle strictly belonging to our browser process.
    Never matches File Explorer, VS Code, or other random windows with 'NetMoniAI' in their titles.
    """
    if not sys.platform.startswith("win"):
        return None

    try:
        from desktop_launcher import get_browser_pid, is_browser_proc_alive
        if not is_browser_proc_alive():
            # If our browser process is not alive, our window does not exist.
            # Return None so show_app_window can cleanly re-launch a fresh window.
            return None

        browser_pid = get_browser_pid()
        if not browser_pid:
            return None

        # Collect target PIDs (the browser process and all its child worker/GPU/renderer processes)
        target_pids = {browser_pid}
        try:
            import psutil
            parent_proc = psutil.Process(browser_pid)
            for child in parent_proc.children(recursive=True):
                target_pids.add(child.pid)
        except Exception:
            pass

        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        candidates = []

        def enum_windows_callback(hwnd, lparam):
            if user32.IsWindow(hwnd):
                # 1. Strictly verify the window belongs to our browser process tree!
                win_pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
                if win_pid.value not in target_pids:
                    return True  # Skip completely! (e.g. Explorer, VS Code, Notepad)

                # 2. Verify window class is not an excluded system class
                class_buff = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_buff, 256)
                cls_name = class_buff.value.lower()
                if cls_name in EXCLUDED_CLASSES:
                    return True

                # 3. Check window text length
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    if title.endswith("- visual studio code") or title.endswith("- notepad"):
                        return True

                is_visible = user32.IsWindowVisible(hwnd)
                candidates.append((hwnd, is_visible))
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)

        if candidates:
            # Sort: prefer visible window first, or top-level window
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
    except Exception as e:
        logger.debug(f"Error finding browser window handle: {e}")
    return None

def show_app_window() -> bool:
    """Restore and focus the NetMoniAI desktop window."""
    hwnd = get_app_window_hwnd()
    if hwnd:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            pass

    # If window handle not found, invoke launcher callback to open new window
    if _window_launcher_callback:
        threading.Thread(target=_window_launcher_callback, daemon=True).start()
        return True
    return False

def hide_app_window(notify: bool = True) -> bool:
    """Hide window to system tray."""
    hwnd = get_app_window_hwnd()
    if hwnd:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.ShowWindow(hwnd, 0)  # SW_HIDE
            if notify and _tray_instance:
                try:
                    _tray_instance.notify(
                        "NetMoniAI is running in background. Click this tray icon to open.",
                        "NetMoniAI Minimized"
                    )
                except Exception:
                    pass
            return True
        except Exception as e:
            logger.debug(f"Error hiding window: {e}")
    return False

def toggle_app_window():
    """Toggle between show and hide."""
    hwnd = get_app_window_hwnd()
    if hwnd:
        try:
            import ctypes
            user32 = ctypes.windll.user32
            if user32.IsWindowVisible(hwnd):
                hide_app_window(notify=True)
            else:
                show_app_window()
            return
        except Exception:
            pass
    show_app_window()

def notify_tray(title: str, message: str):
    """Send a native notification balloon via the tray icon."""
    if _tray_instance:
        try:
            _tray_instance.notify(message, title)
        except Exception:
            pass

def setup_tray_icon(
    app_mode: str,
    port: int,
    dashboard_path: str,
    title: str,
    launcher_func: Optional[Callable] = None
):
    """Initialize and run the System Tray icon in a background thread."""
    global _tray_instance, _window_launcher_callback
    _window_launcher_callback = launcher_func

    try:
        import pystray
        from pystray import MenuItem as item, Menu
        from services.startup_service import is_startup_enabled, set_startup_enabled

        def on_open(icon, item):
            show_app_window()

        def on_minimize(icon, item):
            hide_app_window(notify=True)

        def on_toggle_startup(icon, item):
            current = is_startup_enabled(app_mode)
            set_startup_enabled(not current, app_mode)

        def on_exit(icon, item):
            icon.stop()
            os._exit(0)

        mode_label = "Central Controller (Server)" if app_mode == "server" else "Endpoint Agent"
        icon_img = create_tray_icon_image(64)

        menu = Menu(
            item(f"NetMoniAI {mode_label}", None, enabled=False),
            Menu.SEPARATOR,
            item("Open Dashboard", on_open, default=True),
            item("Minimize to Tray", on_minimize),
            Menu.SEPARATOR,
            item(
                "Start with Windows",
                on_toggle_startup,
                checked=lambda it: is_startup_enabled(app_mode)
            ),
            Menu.SEPARATOR,
            item("Exit NetMoniAI", on_exit)
        )

        icon = pystray.Icon(
            name=f"NetMoniAI-{app_mode}",
            icon=icon_img,
            title=f"NetMoniAI - {mode_label}",
            menu=menu
        )

        _tray_instance = icon
        icon.run_detached()
        logger.info("NetMoniAI System Tray icon initialized successfully.")
        return icon
    except Exception as e:
        logger.error(f"Failed to initialize System Tray icon: {e}")
        return None
