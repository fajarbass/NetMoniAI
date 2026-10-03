import os
import json
import time
import logging
from typing import List, Dict, Any, Optional
import httpx

from settings_manager import settings_manager

logger = logging.getLogger(__name__)

# Fallback model lists in case network is down or keys are uninitialized
FALLBACK_GEMINI_MODELS = [
    {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash (Latest, Fast & Agentic)"},
    {"id": "gemini-3.7-flash", "name": "Gemini 3.7 Flash (Hybrid Reasoning)"},
    {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite (High Throughput)"},
    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro (Deep Reasoning)"},
]

FALLBACK_OPENAI_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o (Omni Multimodal)"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini (Fast)"},
    {"id": "o3-mini", "name": "o3-mini (High Reasoning)"},
    {"id": "o1", "name": "o1 (Full Reasoning)"},
]

FALLBACK_OPENCODE_MODELS = [
    {"id": "opencode-deepseek-r1", "name": "DeepSeek R1 (OpenCode Reasoning)"},
    {"id": "opencode-qwen-2.5-coder", "name": "Qwen 2.5 Coder"},
    {"id": "llama-3.3-70b", "name": "Llama 3.3 70B Instruct"},
    {"id": "mistral-small", "name": "Mistral Small 3"},
]

def fetch_available_models(provider: str, api_key: str = "", base_url: str = "") -> List[Dict[str, Any]]:
    """Fetch live model catalog from the chosen provider."""
    provider = provider.lower()

    if provider == "gemini":
        key = api_key or settings_manager.get_config().ai.gemini.api_key
        if not key:
            return FALLBACK_GEMINI_MODELS
        try:
            from google import genai
            client = genai.Client(api_key=key)
            models = []
            for m in client.models.list():
                # Filter models that support generateContent
                methods = getattr(m, "supported_generation_methods", []) or []
                if "generateContent" in methods:
                    m_id = m.name.replace("models/", "")
                    # Omit legacy embedding-only or legacy 1.0 models from main dropdown
                    if "embedding" not in m_id:
                        models.append({
                            "id": m_id,
                            "name": getattr(m, "display_name", None) or m_id
                        })
            return models if models else FALLBACK_GEMINI_MODELS
        except Exception as e:
            logger.warning(f"Could not fetch live Gemini models, using fallback list: {e}")
            return FALLBACK_GEMINI_MODELS

    elif provider == "openai":
        key = api_key or settings_manager.get_config().ai.openai.api_key
        if not key:
            return FALLBACK_OPENAI_MODELS
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            models = []
            for m in client.models.list():
                if any(prefix in m.id for prefix in ["gpt-4", "gpt-3.5", "o1", "o3", "chatgpt"]):
                    models.append({"id": m.id, "name": m.id})
            models.sort(key=lambda x: x["id"])
            return models if models else FALLBACK_OPENAI_MODELS
        except Exception as e:
            logger.warning(f"Could not fetch live OpenAI models, using fallback list: {e}")
            return FALLBACK_OPENAI_MODELS

    elif provider == "opencode":
        b_url = base_url or settings_manager.get_config().ai.opencode.base_url
        key = api_key or settings_manager.get_config().ai.opencode.api_key
        if not b_url:
            return FALLBACK_OPENCODE_MODELS
        try:
            # Query standard OpenAI-compatible /v1/models endpoint
            endpoint = b_url.rstrip("/")
            if not endpoint.endswith("/models"):
                endpoint = f"{endpoint}/models"
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            with httpx.Client(timeout=4.0) as http_client:
                resp = http_client.get(endpoint, headers=headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    models = [{"id": item["id"], "name": item.get("name", item["id"])} for item in data]
                    if models:
                        return models
        except Exception as e:
            logger.warning(f"Could not fetch live OpenCode models from {b_url}: {e}")
        return FALLBACK_OPENCODE_MODELS

    return []

async def test_llm_connection(provider: str, api_key: str, base_url: str = "", model: str = "") -> Dict[str, Any]:
    """Test connectivity to the selected AI provider with a simple prompt."""
    provider = provider.lower()
    start_time = time.time()

    try:
        if provider == "gemini":
            from google import genai
            client = genai.Client(api_key=api_key)
            m_name = model or "gemini-3.8-flash"
            resp = client.models.generate_content(
                model=m_name,
                contents="Ping. Respond with one word: PONG."
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "ok",
                "message": f"Successfully connected to Gemini ({m_name})",
                "response_text": resp.text.strip(),
                "latency_ms": elapsed_ms
            }

        elif provider == "openai":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
            m_name = model or "gpt-4o-mini"
            resp = await client.chat.completions.create(
                model=m_name,
                messages=[{"role": "user", "content": "Ping. Respond with one word: PONG."}],
                max_tokens=10
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "ok",
                "message": f"Successfully connected to OpenAI ({m_name})",
                "response_text": resp.choices[0].message.content.strip(),
                "latency_ms": elapsed_ms
            }

        elif provider == "opencode":
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key or "opencode-token", base_url=base_url)
            m_name = model or "opencode-deepseek-r1"
            resp = await client.chat.completions.create(
                model=m_name,
                messages=[{"role": "user", "content": "Ping. Respond with one word: PONG."}],
                max_tokens=10
            )
            elapsed_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "ok",
                "message": f"Successfully connected to OpenCode endpoint ({m_name})",
                "response_text": resp.choices[0].message.content.strip(),
                "latency_ms": elapsed_ms
            }

    except Exception as e:
        elapsed_ms = int((time.time() - start_time) * 1000)
        return {
            "status": "error",
            "message": str(e),
            "latency_ms": elapsed_ms
        }

async def generate_llm_response(
    prompt: str,
    system_prompt: str = "",
    agent_name: str = "chat_agent",
    json_mode: bool = False
) -> str:
    """Unified generation function supporting Gemini (with Thinking), OpenAI, and OpenCode."""
    config = settings_manager.get_config()
    ai_settings = config.ai

    # Check for agent override
    override = ai_settings.agent_overrides.get(agent_name)
    provider = (override.provider if override else ai_settings.active_provider).lower()
    
    # 1. Google Gemini
    if provider == "gemini":
        from google import genai
        from google.genai import types

        gemini_cfg = ai_settings.gemini
        api_key = gemini_cfg.api_key
        if not api_key:
            raise ValueError("API key Gemini belum dikonfigurasi di Settings > AI Providers.")
        model_name = (override.model if override and override.model else gemini_cfg.default_model) or "gemini-3.8-flash"
        thinking_level = (override.thinking_level if override and override.thinking_level else gemini_cfg.thinking_level) or "medium"
        budget = gemini_cfg.thinking_budget if thinking_level != "off" else 0

        client = genai.Client(api_key=api_key)
        
        gen_config = types.GenerateContentConfig(
            temperature=gemini_cfg.temperature,
            system_instruction=system_prompt if system_prompt else None,
            response_mime_type="application/json" if json_mode else None,
            thinking_config=types.ThinkingConfig(thinking_budget=budget) if budget > 0 else None
        )

        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
            config=gen_config
        )
        return response.text or ""

    # 2. OpenAI
    elif provider == "openai":
        from openai import AsyncOpenAI
        openai_cfg = ai_settings.openai
        api_key = openai_cfg.api_key
        if not api_key:
            raise ValueError("API key OpenAI belum dikonfigurasi di Settings > AI Providers.")
        model_name = (override.model if override and override.model else openai_cfg.default_model) or "gpt-4o"

        client = AsyncOpenAI(api_key=api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": openai_cfg.temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if "o1" in model_name or "o3" in model_name:
            kwargs["reasoning_effort"] = openai_cfg.reasoning_effort
            kwargs.pop("temperature", None)

        resp = await client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    # 3. OpenCode Provider (OpenAI-compatible)
    elif provider == "opencode":
        from openai import AsyncOpenAI
        opencode_cfg = ai_settings.opencode
        client = AsyncOpenAI(
            api_key=opencode_cfg.api_key or "opencode-token",
            base_url=opencode_cfg.base_url
        )
        model_name = (override.model if override and override.model else opencode_cfg.default_model) or "opencode-deepseek-r1"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": opencode_cfg.temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        resp = await client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    raise ValueError(f"Unsupported AI provider: {provider}")
