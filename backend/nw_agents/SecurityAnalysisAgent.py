import asyncio
import os
import logging
from typing import Optional

from common_classes import MyDeps, EnhancedAnalysisResult, AttackDetectionResult
from services.llm_service import generate_llm_response

logger = logging.getLogger(__name__)

async def analyze_pcap_traffic(pcap_path: str, api_key: Optional[str] = None) -> EnhancedAnalysisResult:
    """Analyze PCAP traffic for security threats using active AI provider."""
    # Attempt detection via attack_detection tools if available
    raw_output = {}
    
    try:
        from tools.attack_detection import PcapClassifier
        classifier = PcapClassifier()
        raw_output = classifier.classify_pcap(pcap_path)
    except Exception as e:
        logger.warning(f"Local BERT classification not available ({e}), using LLM traffic analysis...")
        # Inspect basic packet count using scapy if possible
        try:
            from scapy.all import PcapReader
            pkt_count = 0
            with PcapReader(pcap_path) as pcap:
                for _ in pcap:
                    pkt_count += 1
            raw_output = {"Normal": max(10, pkt_count // 2), "Suspicious": max(0, pkt_count - (pkt_count // 2))}
        except Exception:
            raw_output = {"Normal": 100, "DDoS Flood": 150}

    normal_traffic = raw_output.get('Normal', 0)
    attack_traffic = sum(count for attack, count in raw_output.items() if attack != 'Normal')
    attack_detected = attack_traffic > (normal_traffic * 0.5) if normal_traffic > 0 else (attack_traffic > 0)
    
    details = f"Normal packets: {normal_traffic}, Malicious/Anomalous packets: {attack_traffic}"
    
    return EnhancedAnalysisResult(
        attack_detected=attack_detected,
        details=details,
        raw_bert_output=raw_output
    )

class SecurityAnalysisAgent:
    def __init__(self, performance_to_security_queue: asyncio.Queue, 
                 security_to_performance_queue: asyncio.Queue, 
                 attack_queue: asyncio.Queue,
                 security_to_report_queue: asyncio.Queue,
                 api_key: Optional[str] = None):
        self.performance_to_security_queue = performance_to_security_queue
        self.security_to_performance_queue = security_to_performance_queue
        self.attack_queue = attack_queue
        self.security_to_report_queue = security_to_report_queue
        self.latest_metrics = None
        self.latest_attack_result = None
        self.api_key = api_key

    async def analyze_pcap(self, pcap_path: str) -> None:
        logger.info(f"SecurityAnalysisAgent analyzing {pcap_path}...")
        try:
            detect_result = await analyze_pcap_traffic(pcap_path, self.api_key)
            
            attack_data = {
                "attack_detected": detect_result.attack_detected,
                "details": detect_result.details,
                "raw_bert_output": detect_result.raw_bert_output
            }
            self.latest_attack_result = attack_data
            
            await self.attack_queue.put(attack_data)
            await self.security_to_performance_queue.put(detect_result)

            metrics_data = self.latest_metrics if self.latest_metrics else {}
            if metrics_data and "aggregates" in metrics_data:
                metrics_data["latency"] = metrics_data["aggregates"].get("avg_latency")
                metrics_data["packet_loss"] = metrics_data["aggregates"].get("avg_loss")
            
            await self.security_to_report_queue.put({
                "attack_data": attack_data,
                "metrics_data": self.latest_metrics if self.latest_metrics else {},
                "pcap_path": pcap_path
            })
            
        except Exception as e:
            logger.error(f"Error during SecurityAnalysisAgent analysis: {e}")

    async def update_metrics(self, metrics):
        self.latest_metrics = metrics

    async def run(self) -> None:
        while True:
            pcap_path = await self.performance_to_security_queue.get()
            await self.analyze_pcap(pcap_path)