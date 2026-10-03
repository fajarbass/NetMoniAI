import os
import sys
import time
import subprocess
import httpx

SERVER_EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "NetMoniAI-Server", "NetMoniAI-Server.exe")
AGENT_EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "NetMoniAI-Agent", "NetMoniAI-Agent.exe")

SERVER_PORT = 8000
AGENT_PORT = 8001

def wait_for_service(url, name, timeout=25):
    print(f"Waiting for {name} to be ready at {url}...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(url)
                if res.status_code == 200:
                    print(f" [+] {name} is READY! (HTTP 200 in {time.time() - start:.1f}s)")
                    return True
        except Exception:
            pass
        time.sleep(1.0)
    print(f" [!] {name} failed to become ready within {timeout}s.")
    return False

def run_tests():
    print("=" * 70)
    print("      TESTING COMPILED STANDALONE BINARIES (SERVER & AGENT)      ")
    print("=" * 70)

    if not os.path.exists(SERVER_EXE):
        print(f"ERROR: Server binary not found at {SERVER_EXE}")
        return False
    if not os.path.exists(AGENT_EXE):
        print(f"ERROR: Agent binary not found at {AGENT_EXE}")
        return False

    print(f"Server Exe: {SERVER_EXE} ({os.path.getsize(SERVER_EXE) / 1024 / 1024:.2f} MB)")
    print(f"Agent Exe:  {AGENT_EXE} ({os.path.getsize(AGENT_EXE) / 1024 / 1024:.2f} MB)")

    # Launch Server
    env_server = os.environ.copy()
    env_server["APP_PORT"] = str(SERVER_PORT)
    env_server["APP_MODE"] = "server"
    server_dir = os.path.dirname(SERVER_EXE)
    print(f"\nLaunching Server process on port {SERVER_PORT}...")
    server_proc = subprocess.Popen([SERVER_EXE], cwd=server_dir, env=env_server)

    # Launch Agent
    env_agent = os.environ.copy()
    env_agent["APP_PORT"] = str(AGENT_PORT)
    env_agent["APP_MODE"] = "agent"
    agent_dir = os.path.dirname(AGENT_EXE)
    print(f"Launching Agent process on port {AGENT_PORT}...")
    agent_proc = subprocess.Popen([AGENT_EXE], cwd=agent_dir, env=env_agent)

    passed = 0
    total = 0

    try:
        # Wait for both services
        server_ready = wait_for_service(f"http://localhost:{SERVER_PORT}/api/settings", "NetMoniAI Server")
        agent_ready = wait_for_service(f"http://localhost:{AGENT_PORT}/api/settings", "NetMoniAI Agent")

        if not server_ready or not agent_ready:
            print("\n[FAIL] One or both services failed to start.")
            return False

        with httpx.Client(timeout=5.0) as client:
            # Test 1: Server Settings Endpoint
            total += 1
            res = client.get(f"http://localhost:{SERVER_PORT}/api/settings")
            if res.status_code == 200 and "ai" in res.json():
                print(" [PASS] Server /api/settings returned valid AppConfig JSON")
                passed += 1
            else:
                print(f" [FAIL] Server /api/settings failed: {res.status_code}")

            # Test 2: Server UI serving
            total += 1
            res = client.get(f"http://localhost:{SERVER_PORT}/gc")
            if res.status_code == 200 and ("html" in res.headers.get("content-type", "") or "<!DOCTYPE" in res.text or "<html" in res.text):
                print(" [PASS] Server /gc successfully serves React SPA UI")
                passed += 1
            else:
                print(f" [FAIL] Server /gc failed: {res.status_code}")

            # Test 3: Agent Settings Endpoint
            total += 1
            res = client.get(f"http://localhost:{AGENT_PORT}/api/settings")
            if res.status_code == 200 and "ai" in res.json():
                print(" [PASS] Agent /api/settings returned valid AppConfig JSON")
                passed += 1
            else:
                print(f" [FAIL] Agent /api/settings failed: {res.status_code}")

            # Test 4: Agent Hardware Interface Discovery
            total += 1
            res = client.get(f"http://localhost:{AGENT_PORT}/api/system/interfaces")
            if res.status_code == 200 and "interfaces" in res.json():
                ifaces = res.json()["interfaces"]
                print(f" [PASS] Agent /api/system/interfaces discovered {len(ifaces)} network interfaces")
                passed += 1
            else:
                print(f" [FAIL] Agent /api/system/interfaces failed: {res.status_code}")

            # Test 5: Agent UI serving
            total += 1
            res = client.get(f"http://localhost:{AGENT_PORT}/")
            if res.status_code == 200 and ("html" in res.headers.get("content-type", "") or "<!DOCTYPE" in res.text or "<html" in res.text):
                print(" [PASS] Agent / successfully serves React SPA UI")
                passed += 1
            else:
                print(f" [FAIL] Agent / failed: {res.status_code}")

            # Test 6: Report forwarding to Central Server
            total += 1
            test_report = {
                "node_ip": "192.168.1.105",
                "node_name": "Endpoint-Workstation-01",
                "attack_type": "SYN Flood Simulation",
                "severity": "High",
                "details": "Simulated test payload for Central Server SQLite persistence",
                "metrics": {"avg_latency": 45.2, "packet_loss": 2.1}
            }
            res = client.post(f"http://localhost:{SERVER_PORT}/gcreport", json=test_report)
            if res.status_code == 200:
                print(" [PASS] Report sent to Central Server /gcreport accepted")
                passed += 1
            else:
                print(f" [FAIL] Report submission failed: {res.status_code}")

            # Test 7: Verify Central Server Node Statuses in SQLite
            total += 1
            res = client.get(f"http://localhost:{SERVER_PORT}/gcstatuses")
            data = res.json()
            is_present = ("192.168.1.105" in data) if isinstance(data, dict) else any(s.get("node_ip") == "192.168.1.105" for s in data)
            if res.status_code == 200 and is_present:
                print(" [PASS] Central Server /gcstatuses verified test node status in SQLite DB")
                passed += 1
            else:
                print(f" [FAIL] Node status not found in Server: {res.text}")

            # Test 8: Agent Windows Startup Integration
            total += 1
            res = client.get(f"http://localhost:{AGENT_PORT}/api/system/startup")
            if res.status_code == 200 and "enabled" in res.json() and "platform_supported" in res.json():
                print(" [PASS] Agent /api/system/startup returns valid Windows startup configuration")
                passed += 1
            else:
                print(f" [FAIL] Agent /api/system/startup failed: {res.status_code}")

            # Test 9: Server Windows Startup Integration
            total += 1
            res = client.get(f"http://localhost:{SERVER_PORT}/api/system/startup")
            if res.status_code == 200 and "enabled" in res.json() and "platform_supported" in res.json():
                print(" [PASS] Server /api/system/startup returns valid Windows startup configuration")
                passed += 1
            else:
                print(f" [FAIL] Server /api/system/startup failed: {res.status_code}")

    finally:
        print("\nTerminating test processes...")
        if server_proc.poll() is None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=5)
            except Exception:
                server_proc.kill()
        if agent_proc.poll() is None:
            agent_proc.terminate()
            try:
                agent_proc.wait(timeout=5)
            except Exception:
                agent_proc.kill()
        print("Test processes terminated.")

    print("\n" + "=" * 70)
    print(f" TEST RESULTS: {passed}/{total} CHECKS PASSED ({(passed/total)*100:.1f}%)")
    print("=" * 70)
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
