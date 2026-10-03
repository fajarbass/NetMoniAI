import os
import sys
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from contextlib import asynccontextmanager
import asyncio
import logging
from typing import Optional, Dict, Any

from database import (
    init_db,
    save_report,
    get_reports,
    upsert_node_status,
    get_all_node_statuses,
    clear_simulation_data,
    get_recent_metrics,
)
from settings_manager import settings_manager
from services import (
    get_network_interfaces,
    fetch_available_models,
    test_llm_connection,
    generate_llm_response,
    is_startup_enabled,
    set_startup_enabled,
    get_startup_status,
    show_app_window,
    hide_app_window,
    notify_tray,
)

from nw_agents.ParameterTuningAgent import ParameterTuningAgent
from nw_agents.ReportingAgent import ReportingAgent
from nw_agents.PerformanceMonitoringAgent import PerformanceMonitoringAgent
from nw_agents.SecurityAnalysisAgent import SecurityAnalysisAgent
from nw_agents.ChatAgent import ChatAgent
from appWebsocket import broadcaster, websocket_endpoint
from config import metrics_queue, attack_queue, reports_queue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def central_server_sync_worker(performance_agent, security_agent):
    """Periodically sends real-time heartbeat telemetry from this Endpoint Agent to Central Controller."""
    import httpx
    import socket
    import platform

    def get_agent_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    await asyncio.sleep(2.0)
    logger.info("Central Server Telemetry Sync Worker started.")

    while True:
        try:
            cfg = settings_manager.get_config().central_server
            if cfg.enabled and cfg.server_url:
                target_url = f"{cfg.server_url.rstrip('/')}/gcreport"
                node_ip = get_agent_ip()
                node_name = cfg.client_node_name or platform.node() or "Endpoint-Agent"

                # Check security threat status
                threat_detected = False
                attack_type = "None"
                if hasattr(security_agent, "latest_attack_result") and security_agent.latest_attack_result:
                    threat_detected = bool(security_agent.latest_attack_result.get("attack_detected", False))
                    attack_type = str(security_agent.latest_attack_result.get("details", "Threat Detected") if threat_detected else "None")

                # Extract time series metrics from recent sliding window
                time_series = []
                if hasattr(performance_agent, "sliding_window") and performance_agent.sliding_window:
                    for dp in list(performance_agent.sliding_window)[-12:]:
                        total_b = int(dp.get("bytes_sent", 0) + dp.get("bytes_recv", 0))
                        time_series.append({
                            "time": time.time(),
                            "packets": max(1, int(total_b / 500)),
                            "bytes": total_b
                        })

                payload = {
                    "node_ip": node_ip,
                    "node_name": node_name,
                    "role": "Endpoint Agent",
                    "attack_detected": threat_detected,
                    "attack_type": attack_type,
                    "confidence": 0.98 if threat_detected else 0.99,
                    "summary": f"Agent {node_name} live telemetry streaming nominal" if not threat_detected else f"Threat {attack_type} detected on {node_name}",
                    "anomalies_detected": "Anomalous traffic volume" if threat_detected else "None",
                    "time_series_metrics": time_series,
                }

                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.post(target_url, json=payload)
                    if resp.status_code == 200:
                        logger.debug(f"Telemetry synced to Central Server at {target_url} for node {node_ip}")
        except Exception as e:
            logger.debug(f"Telemetry sync to Central Server: {e}")

        await asyncio.sleep(5.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing NetMoniAI application and SQLite database...")
    init_db()

    performance_to_tuning_queue = asyncio.Queue()
    tuning_to_performance_queue = asyncio.Queue()
    performance_to_security_queue = asyncio.Queue()
    security_to_performance_queue = asyncio.Queue()
    security_to_report_queue = asyncio.Queue()

    app.state.performance_to_tuning_queue = performance_to_tuning_queue

    performance_agent = PerformanceMonitoringAgent(
        metrics_queue, performance_to_tuning_queue, tuning_to_performance_queue,
        performance_to_security_queue, security_to_performance_queue
    )

    tuning_agent = ParameterTuningAgent(performance_to_tuning_queue, tuning_to_performance_queue)

    security_agent = SecurityAnalysisAgent(
        performance_to_security_queue, security_to_performance_queue, 
        attack_queue, security_to_report_queue
    )

    reporting_agent = ReportingAgent(security_to_report_queue, reports_queue)

    app.state.performance_agent = performance_agent
    app.state.chat_agent = ChatAgent

    APP_MODE = os.getenv("APP_MODE", "all").lower()
    app.state.mode = APP_MODE
    logger.info(f"Starting NetMoniAI in '{APP_MODE.upper()}' mode...")

    # Tasks for Agent Mode or All-in-One Mode
    if APP_MODE in ["agent", "all"]:
        logger.info("Spawning Local Monitoring Micro-Agents (Performance, Tuning, Security, Reporting, Sync)...")
        asyncio.create_task(performance_agent.run())
        asyncio.create_task(tuning_agent.run())
        asyncio.create_task(security_agent.run())
        asyncio.create_task(reporting_agent.run())
        asyncio.create_task(central_server_sync_worker(performance_agent, security_agent))

    # Spawn WebSocket Broadcaster in all modes so clients receive metrics, alerts, and reports
    logger.info("Spawning Real-time WebSocket Broadcaster...")
    asyncio.create_task(broadcaster())
    
    yield
    logger.info("Shutting down NetMoniAI application...")

app = FastAPI(
    title="NetMoniAI Core API",
    description="Agentic AI Framework for Network Security & Monitoring with Dynamic Multi-Provider and SQLite Persistence",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket endpoint
app.websocket("/ws")(websocket_endpoint)

# --- Mode & System Role Endpoint ---

@app.get("/api/mode")
async def get_app_mode():
    """Return active running mode (agent, server, all)."""
    mode = getattr(app.state, "mode", os.getenv("APP_MODE", "all")).lower()
    return {
        "mode": mode,
        "title": "Endpoint Agent" if mode == "agent" else ("Central Server" if mode == "server" else "All-in-One Controller"),
        "is_agent": mode == "agent",
        "is_server": mode == "server",
        "port": 8001 if mode == "agent" else 8000,
    }

# --- Central Controller Endpoints (Backed by SQLite) ---

@app.post("/gcreport")
async def receive_report(report: dict):
    """Receive node report, persist in SQLite, and update node status."""
    logger.info(f"Received report: {report}")
    node_ip = report.get("node_ip")
    if not node_ip:
        raise HTTPException(status_code=400, detail="node_ip is required")
    
    # Persist in SQLite
    save_report(report)
    upsert_node_status(node_ip, report)
    
    return {"message": f"Report for {node_ip} received and persisted"}

@app.delete("/gcreset")
async def reset_simulation():
    """Clear all node statuses and reports from the database for simulation reset."""
    result = clear_simulation_data()
    logger.info(f"Simulation reset triggered: {result}")
    return {
        "message": "SOC database reset successfully. Ready for new simulation.",
        "deleted_statuses": result["deleted_statuses"],
        "deleted_reports": result["deleted_reports"],
    }

@app.get("/gcstatuses")
async def get_statuses():
    """Retrieve all node statuses from SQLite database."""
    return get_all_node_statuses()

# --- Dynamic Settings & Configuration Endpoints ---

@app.get("/api/settings")
async def get_settings():
    """Get current active system settings."""
    return settings_manager.get_config().model_dump()

@app.put("/api/settings")
async def update_settings(payload: Dict[str, Any]):
    """Update system settings dynamically without server restart."""
    try:
        updated = settings_manager.update_config(payload)
        return {"status": "ok", "message": "Settings updated successfully", "settings": updated.model_dump()}
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# --- System & Hardware Discovery Endpoints ---

@app.get("/api/system/interfaces")
async def list_interfaces():
    """Enumerate physical and virtual network interfaces."""
    return {"interfaces": get_network_interfaces()}

@app.get("/api/system/startup")
async def get_system_startup():
    """Get Windows startup status."""
    return get_startup_status()

@app.post("/api/system/startup")
async def set_system_startup(payload: Dict[str, Any]):
    """Toggle Windows startup registration."""
    enabled = bool(payload.get("enabled", False))
    success = set_startup_enabled(enabled)
    try:
        cfg = settings_manager.get_config()
        cfg.system.start_on_boot = enabled
        settings_manager.update_config(cfg.model_dump())
    except Exception as e:
        logger.warning(f"Could not update system settings cache: {e}")
    return {"status": "ok" if success else "error", "enabled": enabled}

@app.post("/api/system/tray/minimize")
async def minimize_to_tray_action():
    """Minimize desktop window to system tray."""
    hidden = hide_app_window(notify=True)
    return {"status": "ok", "minimized": hidden}

@app.post("/api/system/tray/restore")
async def restore_from_tray_action():
    """Restore desktop window from system tray."""
    shown = show_app_window()
    return {"status": "ok", "restored": shown}

# --- AI Provider & Model Discovery Endpoints ---

class ModelQuery(dict):
    pass

@app.post("/api/ai/models")
async def get_provider_models(query: Dict[str, Any]):
    """Fetch live model catalog from Gemini, OpenAI, or OpenCode."""
    provider = query.get("provider", "gemini")
    api_key = query.get("api_key", "")
    base_url = query.get("base_url", "")
    models = fetch_available_models(provider=provider, api_key=api_key, base_url=base_url)
    return {"provider": provider, "models": models}

@app.post("/api/ai/test")
async def test_ai_connection(payload: Dict[str, Any]):
    """Test API connection to chosen provider."""
    provider = payload.get("provider", "gemini")
    api_key = payload.get("api_key", "")
    base_url = payload.get("base_url", "")
    model = payload.get("model", "")
    result = await test_llm_connection(provider=provider, api_key=api_key, base_url=base_url, model=model)
    return result

@app.post("/api/central-server/ping")
async def ping_central_server(payload: Dict[str, Any]):
    """Test connectivity from this monitoring agent to the Central Server and register node."""
    server_url = payload.get("server_url", "")
    if not server_url:
        raise HTTPException(status_code=400, detail="server_url is required")
    import time
    start = time.time()
    try:
        import httpx
        import socket
        import platform

        def get_agent_ip():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except Exception:
                return "127.0.0.1"

        node_ip = get_agent_ip()
        node_name = payload.get("client_node_name") or platform.node() or "Endpoint-Agent"

        report_payload = {
            "node_ip": node_ip,
            "node_name": node_name,
            "role": "Endpoint Agent",
            "attack_detected": False,
            "attack_type": "None",
            "confidence": 0.99,
            "summary": f"Agent {node_name} connected and verified via Ping.",
            "anomalies_detected": "None",
        }

        url = f"{server_url.rstrip('/')}/gcreport"
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(url, json=report_payload)
            elapsed_ms = int((time.time() - start) * 1000)
            if resp.status_code == 200:
                return {"status": "ok", "message": f"Connected & registered to Central Server at {server_url} (Node IP: {node_ip})", "latency_ms": elapsed_ms}
            else:
                return {"status": "error", "message": f"Server replied with HTTP {resp.status_code}", "latency_ms": elapsed_ms}
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        return {"status": "error", "message": f"Connection failed: {str(e)}", "latency_ms": elapsed_ms}

# --- Historical Reports & Metrics Audit Endpoints ---

@app.get("/api/reports")
async def list_reports(
    limit: int = Query(50, ge=1, le=500),
    node_ip: Optional[str] = None,
    attack_type: Optional[str] = None
):
    """Retrieve incident reports from SQLite database."""
    reports = get_reports(limit=limit, node_ip=node_ip, attack_type=attack_type)
    return {"total": len(reports), "reports": reports}

@app.get("/api/metrics")
async def list_metrics(limit: int = Query(100, ge=1, le=1000)):
    """Retrieve time-series network metrics from SQLite."""
    return {"metrics": get_recent_metrics(limit=limit)}

# --- Static Web UI & SPA Routing ---

def get_frontend_build_dir() -> Optional[str]:
    # Check PyInstaller frozen bundle
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        for candidate in [
            os.path.join(base_path, "frontend_build"),
            os.path.join(base_path, "build"),
            os.path.join(os.path.dirname(sys.executable), "frontend_build"),
            os.path.join(os.path.dirname(sys.executable), "build"),
        ]:
            if os.path.isdir(candidate):
                return candidate

    # Check local development structure
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.abspath(os.path.join(curr_dir, "..", "frontend", "build")),
        os.path.abspath(os.path.join(curr_dir, "frontend_build")),
        os.path.abspath(os.path.join(curr_dir, "build")),
    ]:
        if os.path.isdir(candidate):
            return candidate
    return None

frontend_dir = get_frontend_build_dir()
if frontend_dir:
    static_dir = os.path.join(frontend_dir, "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Exclude internal / API paths
        if (
            full_path.startswith("api/")
            or full_path.startswith("docs")
            or full_path.startswith("openapi")
            or full_path in ["ws", "gcreport", "gcstatuses"]
        ):
            raise HTTPException(status_code=404, detail="Not Found")

        requested = os.path.join(frontend_dir, full_path)
        if full_path and os.path.isfile(requested):
            return FileResponse(requested)

        index_html = os.path.join(frontend_dir, "index.html")
        if os.path.isfile(index_html):
            return FileResponse(index_html)
        raise HTTPException(status_code=404, detail="SPA index.html not found")
else:
    @app.get("/")
    @app.get("/gc")
    @app.get("/settings")
    async def serve_fallback_ui():
        mode = os.getenv("APP_MODE", "all").upper()
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>NetMoniAI Core - {mode}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    background: #0b0f19;
                    color: #f1f5f9;
                    margin: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                }}
                .card {{
                    background: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 12px;
                    padding: 32px;
                    max-width: 600px;
                    width: 90%;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
                }}
                h1 {{ margin-top: 0; color: #38bdf8; font-size: 24px; }}
                .badge {{ display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; background: #0284c7; color: white; margin-bottom: 16px; }}
                p {{ color: #94a3b8; line-height: 1.5; }}
                .links {{ margin-top: 24px; display: flex; flex-direction: column; gap: 10px; }}
                .btn {{
                    display: block;
                    text-align: center;
                    background: #0f172a;
                    border: 1px solid #3b82f6;
                    color: #38bdf8;
                    padding: 12px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: 500;
                    transition: all 0.2s;
                }}
                .btn:hover {{ background: #3b82f6; color: white; }}
            </style>
        </head>
        <body>
            <div class="card">
                <span class="badge">MODE: {mode}</span>
                <h1>🛡️ NetMoniAI Engine Active</h1>
                <p>NetMoniAI backend service is running successfully with dynamic AI providers and SQLite persistence.</p>
                <div class="links">
                    <a class="btn" href="/docs" target="_blank">📖 Interactive Swagger API Docs</a>
                    <a class="btn" href="/api/settings" target="_blank">⚙️ Current System Configuration (JSON)</a>
                    <a class="btn" href="/api/system/interfaces" target="_blank">🌐 Network Interfaces Detected</a>
                    <a class="btn" href="/gcstatuses" target="_blank">📊 Live Node Statuses</a>
                </div>
            </div>
        </body>
        </html>
        """)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)