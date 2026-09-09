"""
Local LLM Integration Engine.
Connects optionally to Ollama (http://localhost:11434) or LM Studio (http://localhost:1234/v1).
Zero cloud API keys required.
Provides complete, instant fallback to built-in rule-based expert intelligence if no local LLM is running.
"""

import os
import requests
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto") # "ollama", "lmstudio", "none", "auto"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
LMSTUDIO_HOST = os.getenv("LMSTUDIO_HOST", "http://localhost:1234/v1")


def is_ollama_available() -> bool:
    """Checks if a local Ollama instance is reachable with low latency."""
    try:
        res = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=1.0)
        return res.status_code == 200
    except Exception:
        return False


def is_lmstudio_available() -> bool:
    """Checks if LM Studio OpenAI-compatible endpoint is reachable with low latency."""
    try:
        res = requests.get(f"{LMSTUDIO_HOST}/models", timeout=1.0)
        return res.status_code == 200
    except Exception:
        return False


def query_local_llm(prompt: str, system_prompt: str = "") -> Optional[str]:
    """
    Sends a query to Ollama or LM Studio if available.
    Returns generated text or None if unavailable/failed.
    """
    provider = LLM_PROVIDER.lower()

    # Determine available provider
    target = None
    if provider == "ollama" or (provider == "auto" and is_ollama_available()):
        target = "ollama"
    elif provider == "lmstudio" or (provider == "auto" and is_lmstudio_available()):
        target = "lmstudio"

    if not target:
        return None

    try:
        if target == "ollama":
            payload = {
                "model": "mistral",
                "prompt": f"{system_prompt}\n\n{prompt}",
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 350}
            }
            res = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=12.0)
            if res.status_code == 200:
                data = res.json()
                return data.get("response", "").strip()

        elif target == "lmstudio":
            headers = {"Content-Type": "application/json"}
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt or "You are an expert Indian stock market equity analyst."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 350
            }
            res = requests.post(f"{LMSTUDIO_HOST}/chat/completions", headers=headers, json=payload, timeout=12.0)
            if res.status_code == 200:
                data = res.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.debug(f"Local LLM call to {target} failed gracefully: {e}")

    return None
