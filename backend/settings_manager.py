import os
import json
import logging
from typing import Dict, Any, Optional

from database import get_setting, save_setting

logger = logging.getLogger(__name__)

# --- Pydantic Configuration Models ---
from pydantic import BaseModel, Field

class GeminiConfig(BaseModel):
    api_key: str = ""
    default_model: str = "gemini-3.8-flash"
    thinking_level: str = "medium"
    thinking_budget: int = 2048
    temperature: float = 0.3

class OpenAIConfig(BaseModel):
    api_key: str = ""
    default_model: str = "gpt-4o"
    reasoning_effort: str = "medium"
    temperature: float = 0.3

class OpenCodeConfig(BaseModel):
    api_key: str = "opencode-token"
    base_url: str = "http://localhost:11434/v1"
    default_model: str = "opencode-deepseek-r1"
    temperature: float = 0.2

class AgentModelConfig(BaseModel):
    provider: str = "gemini"
    model: str = ""
    thinking_level: Optional[str] = None

class AISettings(BaseModel):
    active_provider: str = "gemini"
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    openai: OpenAIConfig = Field(default_factory=OpenAIConfig)
    opencode: OpenCodeConfig = Field(default_factory=OpenCodeConfig)
    agent_overrides: Dict[str, AgentModelConfig] = Field(
        default_factory=lambda: {
            "tuning_agent": AgentModelConfig(provider="gemini", model="gemini-3.5-flash-lite", thinking_level="off"),
            "security_agent": AgentModelConfig(provider="gemini", model="gemini-3.8-flash", thinking_level="high"),
            "reporting_agent": AgentModelConfig(provider="gemini", model="gemini-3.8-flash", thinking_level="medium"),
            "chat_agent": AgentModelConfig(provider="gemini", model="gemini-3.8-flash", thinking_level="low"),
        }
    )

class NetworkThresholds(BaseModel):
    avg_latency_ms: float = 75.0
    max_latency_ms: float = 100.0
    avg_packet_loss_pct: float = 5.0
    max_packet_loss_pct: float = 10.0

class NetworkSettings(BaseModel):
    interface: str = "auto"
    ping_target_external: str = "8.8.8.8"
    ping_target_local: str = "192.168.1.1"
    thresholds: NetworkThresholds = Field(default_factory=NetworkThresholds)
    sliding_window_size: int = 15

class CaptureSettings(BaseModel):
    default_duration_sec: int = 18
    cycle_interval_sec: int = 1
    tshark_custom_path: str = ""

class QuotaSettings(BaseModel):
    mode: str = "free"
    requests_per_minute: int = 15
    daily_request_cap: int = 1500

class CentralServerSettings(BaseModel):
    enabled: bool = True
    server_url: str = "http://localhost:8000"
    client_node_name: str = "My-Endpoint-PC"

class SystemIntegrationSettings(BaseModel):
    start_on_boot: bool = False
    minimize_to_tray: bool = True
    close_to_tray: bool = True
    notifications_enabled: bool = True

class AppConfig(BaseModel):
    ai: AISettings = Field(default_factory=AISettings)
    network: NetworkSettings = Field(default_factory=NetworkSettings)
    capture: CaptureSettings = Field(default_factory=CaptureSettings)
    quota_limits: QuotaSettings = Field(default_factory=QuotaSettings)
    central_server: CentralServerSettings = Field(default_factory=CentralServerSettings)
    system: SystemIntegrationSettings = Field(default_factory=SystemIntegrationSettings)

# --- Settings Manager Singleton ---

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "data", "settings.json")

class SettingsManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance._config = None
            cls._instance._subscribers = []
            cls._instance.load()
        return cls._instance

    def load(self) -> AppConfig:
        """Load settings from SQLite database, with fallback to settings.json and env vars."""
        saved_dict = get_setting("app_config")
        
        if not saved_dict and os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    saved_dict = json.load(f)
            except Exception as e:
                logger.warning(f"Could not read {SETTINGS_FILE}: {e}")

        if saved_dict:
            try:
                self._config = AppConfig.model_validate(saved_dict)
            except Exception as e:
                logger.warning(f"Failed to validate stored settings, using default: {e}")
                self._config = AppConfig()
        else:
            self._config = AppConfig()

        # Seed from environment variables if keys are empty
        if not self._config.ai.gemini.api_key:
            env_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
            if env_key:
                self._config.ai.gemini.api_key = env_key

        if not self._config.ai.openai.api_key:
            env_key = os.getenv("OPENAI_API_KEY", "")
            if env_key:
                self._config.ai.openai.api_key = env_key

        if not self._config.ai.opencode.api_key or self._config.ai.opencode.api_key == "opencode-token":
            env_key = os.getenv("OPENCODE_API_KEY", "")
            if env_key:
                self._config.ai.opencode.api_key = env_key

        return self._config

    def get_config(self) -> AppConfig:
        if self._config is None:
            return self.load()
        return self._config

    def update_config(self, new_data: Dict[str, Any]) -> AppConfig:
        """Update configuration, save to database and JSON file, and notify subscribers."""
        current_dict = self._config.model_dump()
        
        def deep_merge(target, src):
            for k, v in src.items():
                if isinstance(v, dict) and k in target and isinstance(target[k], dict):
                    deep_merge(target[k], v)
                else:
                    target[k] = v

        deep_merge(current_dict, new_data)
        updated_config = AppConfig.model_validate(current_dict)
        self._config = updated_config

        # Save to SQLite
        save_setting("app_config", self._config.model_dump())

        # Save to JSON file backup
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self._config.model_dump(), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write backup {SETTINGS_FILE}: {e}")

        for callback in self._subscribers:
            try:
                callback(self._config)
            except Exception as e:
                logger.error(f"Error in settings update subscriber: {e}")

        return self._config

    def subscribe(self, callback):
        self._subscribers.append(callback)

settings_manager = SettingsManager()
