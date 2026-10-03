import os
import sys
import shutil
import subprocess
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
FRONTEND_BUILD_DIR = os.path.join(BASE_DIR, "frontend", "build")
DIST_DIR = os.path.join(BASE_DIR, "dist")
BUILD_DIR = os.path.join(BASE_DIR, "build")

HIDDEN_IMPORTS = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "websockets",
    "websockets.legacy",
    "websockets.legacy.server",
    "sqlite3",
    "pydantic",
    "httpx",
    "psutil",
    "google.genai",
    "openai",
    "starlette",
    "fastapi",
    "app",
    "settings_manager",
    "services",
    "services.llm_service",
    "services.system_service",
    "services.startup_service",
    "services.tray_service",
    "services.single_instance",
    "pystray",
    "pystray._win32",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "winreg",
    "ctypes",
    "ctypes.wintypes",
    "database",
    "database.db",
    "nw_agents",
    "nw_agents.PerformanceMonitoringAgent",
    "nw_agents.ParameterTuningAgent",
    "nw_agents.SecurityAnalysisAgent",
    "nw_agents.ReportingAgent",
    "nw_agents.ChatAgent",
    "appWebsocket",
    "utils",
    "config",
    "common_classes",
    "desktop_launcher",
]

def build_target(name: str, entry_script: str):
    print(f"\n{'='*70}")
    print(f" [BUILDING] Compiling standalone package: {name}")
    print(f"{'='*70}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--clean",
        "--noconsole",
        "--name", name,
        "--paths", BACKEND_DIR,
        "--distpath", DIST_DIR,
        "--workpath", os.path.join(BUILD_DIR, name),
    ]

    for hi in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", hi])

    # If frontend build exists, bundle it directly
    if os.path.isdir(FRONTEND_BUILD_DIR):
        cmd.extend(["--add-data", f"{FRONTEND_BUILD_DIR}{os.pathsep}frontend_build"])

    cmd.append(os.path.join(BACKEND_DIR, entry_script))

    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller build failed for {name} with code {result.returncode}")

    target_dir = os.path.join(DIST_DIR, name)

    # Also copy frontend_build directly next to the executable if not already present
    dest_frontend = os.path.join(target_dir, "frontend_build")
    if os.path.isdir(FRONTEND_BUILD_DIR) and not os.path.isdir(dest_frontend):
        print(f"Copying frontend build directory to {dest_frontend}...")
        shutil.copytree(FRONTEND_BUILD_DIR, dest_frontend)

    # Copy .env.example
    env_example = os.path.join(BASE_DIR, ".env.example")
    if os.path.exists(env_example):
        shutil.copy(env_example, os.path.join(target_dir, ".env.example"))

    return target_dir

def create_server_helpers(server_dir: str):
    # Launcher bat (Silent launch of GUI app)
    launcher = os.path.join(server_dir, "Start-Server.bat")
    with open(launcher, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("start \"\" \"%~dp0NetMoniAI-Server.exe\"\n")
        f.write("exit\n")

    # Silent VBS launcher (Zero-terminal popup)
    vbs_launcher = os.path.join(server_dir, "Start-Server-Silent.vbs")
    with open(vbs_launcher, "w", encoding="utf-8") as f:
        f.write("Set WshShell = CreateObject(\"WScript.Shell\")\n")
        f.write("WshShell.CurrentDirectory = CreateObject(\"Scripting.FileSystemObject\").GetParentFolderName(WScript.ScriptFullName)\n")
        f.write("WshShell.Run \"\"\"\" & WshShell.CurrentDirectory & \"\\NetMoniAI-Server.exe\"\"\", 0, False\n")

    # Installer bat
    installer = os.path.join(server_dir, "Install-Server.bat")
    with open(installer, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("setlocal enabledelayedexpansion\n")
        f.write("title NetMoniAI Server Installer\n")
        f.write("echo ====================================================\n")
        f.write("echo      Installing NetMoniAI Central Controller Server   \n")
        f.write("echo ====================================================\n")
        f.write("set \"INSTALL_DIR=%LOCALAPPDATA%\\NetMoniAI\\Server\"\n")
        f.write("echo Installing to: %INSTALL_DIR%\n")
        f.write("mkdir \"%INSTALL_DIR%\" 2>nul\n")
        f.write("xcopy /E /I /Y /Q \"%~dp0*.*\" \"%INSTALL_DIR%\"\n")
        f.write("echo Creating Desktop Shortcut...\n")
        f.write("powershell -Command \"$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\\NetMoniAI Server.lnk'); $s.TargetPath = '%INSTALL_DIR%\\NetMoniAI-Server.exe'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Save()\"\n")
        f.write("echo.\n")
        f.write("echo [SUCCESS] NetMoniAI Server has been installed successfully!\n")
        f.write("echo You can now launch it directly from the Desktop shortcut 'NetMoniAI Server'.\n")
        f.write("echo It runs in pure native desktop mode without any terminal window.\n")
        f.write("echo ====================================================\n")
        f.write("pause\n")

def create_agent_helpers(agent_dir: str):
    # Launcher bat
    launcher = os.path.join(agent_dir, "Start-Agent.bat")
    with open(launcher, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("cd /d \"%~dp0\"\n")
        f.write("start \"\" \"%~dp0NetMoniAI-Agent.exe\"\n")
        f.write("exit\n")

    # Silent VBS launcher
    vbs_launcher = os.path.join(agent_dir, "Start-Agent-Silent.vbs")
    with open(vbs_launcher, "w", encoding="utf-8") as f:
        f.write("Set WshShell = CreateObject(\"WScript.Shell\")\n")
        f.write("WshShell.CurrentDirectory = CreateObject(\"Scripting.FileSystemObject\").GetParentFolderName(WScript.ScriptFullName)\n")
        f.write("WshShell.Run \"\"\"\" & WshShell.CurrentDirectory & \"\\NetMoniAI-Agent.exe\"\"\", 0, False\n")

    # Installer bat
    installer = os.path.join(agent_dir, "Install-Agent.bat")
    with open(installer, "w", encoding="utf-8") as f:
        f.write("@echo off\n")
        f.write("setlocal enabledelayedexpansion\n")
        f.write("title NetMoniAI Agent Installer\n")
        f.write("echo ====================================================\n")
        f.write("echo      Installing NetMoniAI Endpoint Monitoring Agent   \n")
        f.write("echo ====================================================\n")
        f.write("set \"INSTALL_DIR=%LOCALAPPDATA%\\NetMoniAI\\Agent\"\n")
        f.write("echo Installing to: %INSTALL_DIR%\n")
        f.write("mkdir \"%INSTALL_DIR%\" 2>nul\n")
        f.write("xcopy /E /I /Y /Q \"%~dp0*.*\" \"%INSTALL_DIR%\"\n")
        f.write("echo Creating Desktop Shortcut...\n")
        f.write("powershell -Command \"$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\\NetMoniAI Agent.lnk'); $s.TargetPath = '%INSTALL_DIR%\\NetMoniAI-Agent.exe'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Save()\"\n")
        f.write("echo.\n")
        f.write("echo [SUCCESS] NetMoniAI Agent has been installed successfully!\n")
        f.write("echo You can now launch it directly from the Desktop shortcut 'NetMoniAI Agent'.\n")
        f.write("echo It runs in pure native desktop mode without any terminal window.\n")
        f.write("echo ====================================================\n")
        f.write("pause\n")

def zip_package(folder_path: str, zip_path: str):
    print(f"Creating ZIP archive: {zip_path}...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, os.path.dirname(folder_path))
                zf.write(abs_path, rel_path)
    print(f"Archive created: {zip_path} ({os.path.getsize(zip_path) / 1024 / 1024:.2f} MB)")

def main():
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(BUILD_DIR, exist_ok=True)

    print("======================================================================")
    print("           NetMoniAI Installer & Distribution Builder                 ")
    print("======================================================================")

    # 1. Build Server
    server_dir = build_target("NetMoniAI-Server", "server_entry.py")
    create_server_helpers(server_dir)
    zip_package(server_dir, os.path.join(DIST_DIR, "NetMoniAI-Server-Installer.zip"))

    # 2. Build Agent
    agent_dir = build_target("NetMoniAI-Agent", "agent_entry.py")
    create_agent_helpers(agent_dir)
    zip_package(agent_dir, os.path.join(DIST_DIR, "NetMoniAI-Agent-Installer.zip"))

    print("\n" + "=" * 70)
    print(" [OK] BUILD COMPLETED SUCCESSFULLY!")
    print(f" Server Distribution:  {server_dir}")
    print(f" Server ZIP Archive:   {os.path.join(DIST_DIR, 'NetMoniAI-Server-Installer.zip')}")
    print(f" Agent Distribution:   {agent_dir}")
    print(f" Agent ZIP Archive:    {os.path.join(DIST_DIR, 'NetMoniAI-Agent-Installer.zip')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
