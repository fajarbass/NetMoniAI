import asyncio
import json
import logging
from typing import Optional

from common_classes import MyDeps, ParameterResult
from services.llm_service import generate_llm_response

logger = logging.getLogger(__name__)

TUNING_SYS_PROMPT = """
You are a network parameter tuning agent. Based on current network conditions and historical metrics, 
set optimal packet capture duration (15 to 45 seconds) and monitoring cycle interval (2 to 20 seconds).
Respond with a JSON object in this format:
{
  "duration": 30,
  "interval": 5
}
Guidelines:
- If latency is high or attacks were detected: increase duration (30-40s) and decrease interval (2-5s) for closer inspection.
- If network is stable and normal: decrease duration (15-20s) and increase interval (10-20s) to save resources.
"""

class ParameterTuningAgent:
    def __init__(self, performance_to_tuning_queue: asyncio.Queue, tuning_to_performance_queue: asyncio.Queue):
        self.performance_to_tuning_queue = performance_to_tuning_queue
        self.tuning_to_performance_queue = tuning_to_performance_queue

    async def run(self) -> None:
        """Adjust monitoring parameters dynamically using active AI provider."""
        while True:
            data = await self.performance_to_tuning_queue.get()
            metrics = data.get("metrics", {})
            aggregates = metrics.get("aggregates", {})
            previous_attack_detected = data.get("previous_attack_detected", False)
            recent_history = data.get("recent_history", [])

            avg_lat = aggregates.get("avg_latency") or 0.0
            avg_loss = aggregates.get("avg_loss") or 0.0
            num_attacks = sum(1 for entry in recent_history if entry.get("attack_detected"))

            prompt = (
                f"Tune monitoring parameters:\n"
                f"- Current average latency: {avg_lat} ms\n"
                f"- Current packet loss: {avg_loss} %\n"
                f"- Previous cycle attack detected: {previous_attack_detected}\n"
                f"- Recent attacks in last 10 cycles: {num_attacks}\n"
                f"Determine optimal capture duration (seconds) and cycle interval (seconds)."
            )

            try:
                raw_json = await generate_llm_response(
                    prompt=prompt,
                    system_prompt=TUNING_SYS_PROMPT,
                    agent_name="tuning_agent",
                    json_mode=True
                )
                clean_str = raw_json.strip()
                if clean_str.startswith("```"):
                    clean_str = clean_str.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

                parsed = json.loads(clean_str)
                duration = int(parsed.get("duration", 25))
                interval = int(parsed.get("interval", 3))
                # Bound to safe ranges
                duration = max(10, min(60, duration))
                interval = max(1, min(30, interval))
            except Exception as e:
                logger.warning(f"Parameter tuning LLM call fallback: {e}")
                # Safe heuristic fallback
                if previous_attack_detected or avg_lat > 100:
                    duration, interval = 30, 2
                else:
                    duration, interval = 18, 5

            updated_deps = MyDeps(duration=duration, cycle_interval=interval)
            await self.tuning_to_performance_queue.put(updated_deps)