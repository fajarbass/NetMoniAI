import sys
import os
import logging

logger = logging.getLogger(__name__)

ERROR_ALREADY_EXISTS = 183

class SingleInstance:
    """Enforce a single active instance of NetMoniAI per mode (Agent / Server) using Windows Named Mutex."""

    def __init__(self, app_mode: str, port: int):
        self.app_mode = app_mode.lower()
        self.port = port
        self.mutex = None

    def check_or_exit(self) -> bool:
        """Return True if this is the primary instance.
        If another instance is already running, notify it to restore its window and exit this process.
        """
        if not sys.platform.startswith("win"):
            return True

        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            mutex_name = f"Local\\NetMoniAI_{self.app_mode.upper()}_SingleInstance_Mutex"

            # Create or open named mutex
            self.mutex = kernel32.CreateMutexW(None, False, mutex_name)
            last_error = kernel32.GetLastError()

            if last_error == ERROR_ALREADY_EXISTS:
                print(f"[INFO] NetMoniAI ({self.app_mode.upper()}) is already running on this system.")
                print(f"[INFO] Requesting active instance at http://127.0.0.1:{self.port} to restore window...")
                
                # Signal existing instance to restore window
                try:
                    import httpx
                    with httpx.Client(timeout=2.5) as client:
                        client.post(f"http://127.0.0.1:{self.port}/api/system/tray/restore")
                except Exception as e:
                    logger.debug(f"Could not reach active instance via HTTP: {e}")

                print("[INFO] Duplicate instance exiting.")
                sys.exit(0)
                return False

            return True
        except Exception as e:
            logger.warning(f"SingleInstance check encountered an error: {e}")
            return True
