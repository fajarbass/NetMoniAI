import logging
import asyncio
from collections import deque
import uuid
import time
import json
from typing import Optional, Any

from common_classes import NetworkReport, MyDeps, AnalysisResult
from database import save_report
from services.llm_service import generate_llm_response

logger = logging.getLogger(__name__)

SYS_PROMPT = """
You are a network analysis reporting agent. Generate comprehensive incident reports on network anomalies 
and security events using attack detection data and packet traffic features.
You must respond with valid JSON matching the following structure:
{
  "report_id": "NR-xxx",
  "timestamp": "YYYY-MM-DD HH:MM:SS",
  "summary": "Executive summary of findings",
  "attack_detected": true/false,
  "attack_type": "DDoS/Port Scan/Normal/etc.",
  "confidence": 0.95,
  "metrics_summary": "Latency: ... Loss: ...",
  "anomalies_detected": "Detailed description of anomalies",
  "potential_causes": "Probable root cause",
  "recommended_actions": "Specific mitigation commands or steps",
  "further_investigation": "Suggested forensic steps"
}
"""

async def generate_network_report(
    analysis_result: Any,
    pcap_path: str,
    duration: int,
    cycle_interval: int,
    avg_latency: Optional[float] = None,
    avg_loss: Optional[float] = None
) -> NetworkReport:
    """Generate structured NetworkReport using active AI provider (Gemini, OpenAI, or OpenCode)."""
    raw_bert_output = analysis_result.get('raw_bert_output', {}) if isinstance(analysis_result, dict) else getattr(analysis_result, 'raw_bert_output', {})
    attack_detected = analysis_result['attack_detected'] if isinstance(analysis_result, dict) else getattr(analysis_result, 'attack_detected', False)
    details = analysis_result.get('details', '') if isinstance(analysis_result, dict) else getattr(analysis_result, 'details', '')
    
    prompt = (
        f"Generate an incident report for the following event:\n"
        f"- Attack detected flag: {attack_detected}\n"
        f"- Detection details: {details}\n"
        f"- Attack traffic counts: {raw_bert_output}\n"
        f"- Latency: {avg_latency} ms, Packet Loss: {avg_loss} %\n"
        f"- PCAP Path: {pcap_path}, Duration: {duration}s, Cycle: {cycle_interval}s\n"
        f"Ensure specific, actionable command recommendations are provided."
    )

    try:
        raw_json_str = await generate_llm_response(
            prompt=prompt,
            system_prompt=SYS_PROMPT,
            agent_name="reporting_agent",
            json_mode=True
        )
        
        # Clean markdown codeblocks if LLM returned ```json ... ```
        clean_str = raw_json_str.strip()
        if clean_str.startswith("```"):
            clean_str = clean_str.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        
        parsed = json.loads(clean_str)
        if not parsed.get("report_id"):
            parsed["report_id"] = f"NR-{uuid.uuid4().hex[:8]}-{int(time.time())}"
        if not parsed.get("timestamp"):
            parsed["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

        report = NetworkReport(**parsed)
    except Exception as e:
        logger.error(f"Error generating LLM report: {e}. Falling back to default report template.")
        report = NetworkReport(
            report_id=f"NR-FALLBACK-{uuid.uuid4().hex[:8]}",
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            summary=f"Automated incident analysis for {pcap_path}: {details or 'Elevated traffic anomaly detected'}",
            attack_detected=attack_detected,
            attack_type="Potential Network Attack" if attack_detected else "Benign Traffic Anomaly",
            confidence=0.85 if attack_detected else 0.5,
            metrics_summary=f"Avg Latency: {avg_latency or 0}ms, Loss: {avg_loss or 0}%",
            anomalies_detected="High latency or anomalous packet flow detected by monitoring agent",
            potential_causes="Traffic flood, port scanning, or bandwidth saturation",
            recommended_actions="1. Inspect destination IP flows with tcpdump\n2. Rate limit offending IP at firewall / iptables",
            further_investigation="Review firewall access logs and packet captures in lastCapture/"
        )

    # NOTE: Do NOT persist here — caller (analyze_nodes / agent) is responsible for saving
    # after injecting node_ip and metadata. This prevents NOT NULL constraint failures.
    logger.info(f"Report {report.report_id} generated (not yet persisted — awaiting node metadata injection).")

    # NOTE: Central Server forwarding is also handled by the caller (analyze_nodes.py)
    # after node metadata is injected. Do not forward here to avoid 400 Bad Request errors
    # caused by missing node_ip in the payload.

    return report


async def forward_report_to_central_server(server_url: str, report_data: dict, node_name: str):
    """Forward incident report to Central Server asynchronously."""
    try:
        import httpx
        url = f"{server_url.rstrip('/')}/gcreport"
        payload = dict(report_data)
        if node_name:
            payload["client_node_name"] = node_name
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info(f"Report successfully forwarded to Central Server at {url}")
    except Exception as e:
        logger.warning(f"Central Server at {server_url} is currently unreachable: {e}")

class ReportingAgent:
    def __init__(self, security_to_reporting_queue: asyncio.Queue, reports_queue: asyncio.Queue):
        self.security_to_reporting_queue = security_to_reporting_queue
        self.reports_queue = reports_queue
        self.metrics_history = deque(maxlen=50)

    async def generate_report(self, attack_data, metrics_data, pcap_path):
        """Generate report, persist to SQLite, and push to broadcast queue."""
        logger.info("Generating network analysis report via active AI provider...")
        try:
            report_result = await generate_network_report(
                analysis_result=attack_data,
                pcap_path=pcap_path,
                duration=metrics_data.get("duration", 5),
                cycle_interval=metrics_data.get("interval", 2),
                avg_latency=metrics_data.get("latency"),
                avg_loss=metrics_data.get("packet_loss")
            )
            await self.reports_queue.put(report_result)
            logger.info(f"Report generated and queued: {report_result.report_id}")
            return report_result
        except Exception as e:
            logger.error(f"Error in ReportingAgent.generate_report: {e}")
            return None

    async def update_metrics_history(self, metrics):
        self.metrics_history.append(metrics)

    async def run(self):
        """Process incoming security data and generate reports."""
        while True:
            data = await self.security_to_reporting_queue.get()
            attack_data = data["attack_data"]
            metrics_data = data["metrics_data"]
            pcap_path = data["pcap_path"]
            await self.generate_report(attack_data, metrics_data, pcap_path)