from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import logging
import json

from config import metrics_queue, attack_queue, connected_clients, reports_queue
from database import get_all_node_statuses

logger = logging.getLogger(__name__)

async def broadcaster():
    """Broadcasts metrics, attack alerts, and reports to all connected WebSocket clients."""
    while True:
        if not metrics_queue.empty():
            metrics = await metrics_queue.get()
            for client in list(connected_clients):
                try:
                    await client.send_json({"type": "metrics", "data": metrics})
                except Exception as e:
                    logger.debug(f"Error sending metrics to client: {e}")

        if not attack_queue.empty():
            attack_result = await attack_queue.get()
            logger.info(f"Broadcasting Attack Alert: {attack_result}")
            for client in list(connected_clients):
                try:
                    await client.send_json({"type": "attack_detection", "data": attack_result})
                except Exception as e:
                    logger.debug(f"Error sending attack result to client: {e}")

        if not reports_queue.empty():
            report = await reports_queue.get()
            report_dict = report.model_dump() if hasattr(report, "model_dump") else report
            logger.info(f"Broadcasting Network Report {report_dict.get('report_id')}")
            for client in list(connected_clients):
                try:
                    await client.send_json({"type": "network_report", "data": report_dict})
                except Exception as e:
                    logger.debug(f"Error sending report to client: {e}")
                    
        await asyncio.sleep(0.1)

async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket client connections for live metrics and natural language AI copilot."""
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info("WebSocket client connected")
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get('type')
            
            # Local Node Assistant
            if msg_type == 'chat':
                user_message = data.get('message', '')
                performance_agent = getattr(websocket.app.state, 'performance_agent', None)
                
                latest_metrics = None
                if performance_agent and getattr(performance_agent, 'sliding_window', None):
                    latest_metrics = performance_agent.sliding_window[-1]
                    metrics_str = (
                        f"- Bytes sent: {latest_metrics.get('bytes_sent', 0)}\n"
                        f"- Bytes received: {latest_metrics.get('bytes_recv', 0)}\n"
                        f"- Throughput sent: {latest_metrics.get('throughput_sent', 0):.2f} B/s\n"
                        f"- Throughput received: {latest_metrics.get('throughput_recv', 0):.2f} B/s\n"
                        f"- External latency: {latest_metrics.get('avg_latency', 'N/A')} ms\n"
                        f"- External packet loss: {latest_metrics.get('avg_loss', 'N/A')}%\n"
                        f"- Local latency: {latest_metrics.get('local_latency', 'N/A')} ms"
                    )
                else:
                    metrics_str = "No live metrics available yet (initial buffer collecting)."

                prompt = (
                    f"User Question: {user_message}\n\n"
                    f"Current Live Network Metrics:\n{metrics_str}\n\n"
                    f"Please provide an informative, concise cybersecurity/network answer based on these metrics."
                )

                try:
                    chat_agent = websocket.app.state.chat_agent
                    response = await chat_agent.run(
                        user_prompt=prompt,
                        context={
                            "type": "local",
                            "latest_metrics": latest_metrics,
                            "raw_message": user_message
                        }
                    )
                    await websocket.send_json({"type": "chat_response", "data": response.data})
                except Exception as e:
                    logger.error(f"Error generating chat response: {e}")
                    await websocket.send_json({"type": "chat_response", "data": "Mohon maaf, terjadi kendala saat memproses respons AI."})

            # Central Controller Global Assistant
            elif msg_type == 'global_chat':
                user_message = data.get('message', '')
                node_statuses = get_all_node_statuses()
                
                if not node_statuses:
                    node_statuses_str = "Saat ini belum ada endpoint/agen yang terhubung ke database Central SOC (0 node aktif)."
                else:
                    node_statuses_str = "\n".join([
                        f"- {ip}:\n"
                        f"  Status: {'Under Attack' if status.get('attack_detected') else 'Normal'}\n"
                        f"  Role: {status.get('role', 'N/A')}\n"
                        f"  Attack Type: {status.get('attack_type', 'None')}\n"
                        f"  Confidence: {status.get('confidence', 'N/A')}\n"
                        f"  Summary: {status.get('summary', 'No summary available')}"
                        for ip, status in node_statuses.items()
                    ])

                prompt = (
                    f"User Question: {user_message}\n\n"
                    f"System-Wide Node Statuses (from SQLite Database):\n{node_statuses_str}\n\n"
                    f"Please provide a clear situational awareness report answering the user's question."
                )

                try:
                    chat_agent = websocket.app.state.chat_agent
                    response = await chat_agent.run(
                        user_prompt=prompt,
                        context={
                            "type": "global",
                            "node_statuses": node_statuses,
                            "raw_message": user_message
                        }
                    )
                    await websocket.send_json({"type": "global_chat_response", "data": response.data})
                except Exception as e:
                    logger.error(f"Error generating global chat response: {e}")
                    await websocket.send_json({"type": "global_chat_response", "data": "Mohon maaf, terjadi kendala saat memproses respons AI global."})

    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)