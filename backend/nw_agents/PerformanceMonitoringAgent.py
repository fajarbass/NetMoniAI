import asyncio
from collections import deque
import subprocess
import psutil
import time
import os
import logging
from typing import Optional

from utils import get_ping_metrics, get_default_gateway, get_subprocess_flags
from common_classes import MyDeps
from database import save_metric
from settings_manager import settings_manager
from services.system_service import get_tshark_path, get_default_interface_name

logger = logging.getLogger(__name__)

class PerformanceMonitoringAgent:
    def __init__(self, metrics_queue: asyncio.Queue, performance_to_tuning_queue: asyncio.Queue,
                 tuning_to_performance_queue: asyncio.Queue, performance_to_security_queue: asyncio.Queue,
                 security_to_performance_queue: asyncio.Queue):
        self.metrics_queue = metrics_queue
        self.performance_to_tuning_queue = performance_to_tuning_queue
        self.tuning_to_performance_queue = tuning_to_performance_queue
        self.performance_to_security_queue = performance_to_security_queue
        self.security_to_performance_queue = security_to_performance_queue
        
        cfg = settings_manager.get_config()
        self.sliding_window = deque(maxlen=cfg.network.sliding_window_size)
        self.deps = MyDeps(
            pathToFile="lastCapture/capture.pcap",
            duration=cfg.capture.default_duration_sec,
            cycle_interval=cfg.capture.cycle_interval_sec
        )
        self.previous_attack_detected = False
        self.last_check_time = time.time()
        self.recent_history = []

    def get_active_interface(self) -> str:
        """Resolve interface from settings or auto-detection."""
        configured = settings_manager.get_config().network.interface
        if configured and configured.lower() != "auto":
            return configured
        return get_default_interface_name()

    async def collect_metrics(self) -> None:
        """Collect network metrics, persist in SQLite, and update sliding window."""
        cfg = settings_manager.get_config()
        io_old = psutil.net_io_counters()
        router_ip = cfg.network.ping_target_local or get_default_gateway() or "192.168.1.1"
        external_ip = cfg.network.ping_target_external or "8.8.8.8"
        
        await asyncio.sleep(0.1)
        io_new = psutil.net_io_counters()
        bytes_sent = io_new.bytes_sent - io_old.bytes_sent
        bytes_recv = io_new.bytes_recv - io_old.bytes_recv
        throughput_sent = bytes_sent / 0.1
        throughput_recv = bytes_recv / 0.1

        external_ping = await get_ping_metrics(external_ip)
        local_ping = await get_ping_metrics(router_ip)

        data_point = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "bytes_sent": bytes_sent,
            "bytes_recv": bytes_recv,
            "throughput_sent": throughput_sent,
            "throughput_recv": throughput_recv,
            "external_ping": external_ping,
            "local_ping": local_ping,
            "avg_latency": external_ping.get("avg_latency"),
            "avg_loss": external_ping.get("packet_loss"),
            "local_latency": local_ping.get("avg_latency")
        }
        self.sliding_window.append(data_point)

        if self.sliding_window:
            latencies = [dp["external_ping"]["avg_latency"] for dp in self.sliding_window if dp["external_ping"]["avg_latency"] is not None]
            losses = [dp["external_ping"]["packet_loss"] for dp in self.sliding_window if dp["external_ping"]["packet_loss"] is not None]
            aggregates = {
                "avg_latency": sum(latencies) / len(latencies) if latencies else None,
                "avg_loss": sum(losses) / len(losses) if losses else None,
                "max_latency": max(latencies) if latencies else None,
                "max_loss": max(losses) if losses else None
            }
            data_point["aggregates"] = aggregates

        # Save to SQLite database
        save_metric(data_point)
        await self.metrics_queue.put(data_point)

    def _should_capture(self) -> bool:
        """Determine if an anomaly requires PCAP capture using dynamic thresholds."""
        if not self.sliding_window:
            return False
        
        latencies = [dp["external_ping"]["avg_latency"] for dp in self.sliding_window if dp["external_ping"]["avg_latency"] is not None]
        losses = [dp["external_ping"]["packet_loss"] for dp in self.sliding_window if dp["external_ping"]["packet_loss"] is not None]
        if not latencies or not losses:
            return False

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        avg_loss = sum(losses) / len(losses)
        max_loss = max(losses)

        # Dynamic thresholds from settings_manager
        t = settings_manager.get_config().network.thresholds
        return (avg_latency > t.avg_latency_ms) or (max_latency > t.max_latency_ms) or (avg_loss > t.avg_packet_loss_pct) or (max_loss > t.max_packet_loss_pct)

    async def capture_pcap(self) -> None:
        """Capture network traffic using auto-detected or custom tshark binary."""
        cfg = settings_manager.get_config()
        tshark_bin = get_tshark_path(cfg.capture.tshark_custom_path)
        if not tshark_bin:
            logger.warning("tshark binary not found! Skipping physical PCAP capture.")
            return

        iface = self.get_active_interface()
        os.makedirs(os.path.dirname(self.deps.pathToFile) or ".", exist_ok=True)
        logger.info(f"Capturing data on interface '{iface}' for {self.deps.duration}s using {tshark_bin}...")
        
        try:
            cmd = [tshark_bin, "-i", iface, "-a", f"duration:{self.deps.duration}", "-w", self.deps.pathToFile]
            run_kwargs = {
                "capture_output": True,
                "text": True,
                **get_subprocess_flags()
            }
            capture_result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                **run_kwargs
            )
            if capture_result.returncode != 0:
                logger.error(f"Capture warning/failed: {capture_result.stderr}")
        except Exception as e:
            logger.error(f"Error during capture: {e}")

    async def metric_collection_loop(self) -> None:
        """Periodically collect network metrics."""
        while True:
            await self.collect_metrics()
            await asyncio.sleep(2)

    async def anomaly_checking_loop(self) -> None:
        """Monitor for anomalies based on cycle interval."""
        while True:
            current_time = time.time()
            if current_time - self.last_check_time >= self.deps.cycle_interval:
                self.last_check_time = current_time
                
                if hasattr(self, 'security_agent') and self.sliding_window:
                    await self.security_agent.update_metrics(self.sliding_window[-1])
                    
                if self.sliding_window:
                    latest_metrics = self.sliding_window[-1]
                    aggregates = latest_metrics.get("aggregates", {})
                    anomaly_detected = self._should_capture()
                    
                    if anomaly_detected:
                        logger.info("Anomaly detected by dynamic thresholds, coordinating with agent team.")
                        await self.performance_to_tuning_queue.put({
                            "metrics": latest_metrics,
                            "previous_attack_detected": self.previous_attack_detected,
                            "recent_history": self.recent_history[-10:]
                        })
                        updated_deps = await self.tuning_to_performance_queue.get()
                        self.deps.duration = updated_deps.duration
                        self.deps.cycle_interval = updated_deps.cycle_interval
                        
                        await self.capture_pcap()
                        await self.performance_to_security_queue.put(self.deps.pathToFile)
                        analysis_result = await self.security_to_performance_queue.get()
                        self.previous_attack_detected = getattr(analysis_result, "attack_detected", False)
                        attack_detected = self.previous_attack_detected
                    else:
                        attack_detected = None
                    
                    history_entry = {
                        "timestamp": latest_metrics["timestamp"],
                        "avg_latency": aggregates.get("avg_latency"),
                        "avg_loss": aggregates.get("avg_loss"),
                        "anomaly_detected": anomaly_detected,
                        "attack_detected": attack_detected
                    }
                    self.recent_history.append(history_entry)
                    if len(self.recent_history) > 200:
                        self.recent_history.pop(0)

                    self.sliding_window.clear()
            await asyncio.sleep(1)

    async def run(self) -> None:
        """Execute metric collection and anomaly checking concurrently."""
        await asyncio.gather(
            self.metric_collection_loop(),
            self.anomaly_checking_loop()
        )