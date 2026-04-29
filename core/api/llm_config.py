"""LLM provider configuration.

Pure Python (no UI deps). Persists to data/.llm_config.json.

Public API:
    PROVIDERS                  : dict[str, Provider]
    DEFAULT_CONFIG             : dict
    load_config()  -> dict
    save_config(cfg)
    test_connection(cfg)       -> (ok, message, models)
    resolve_endpoints(cfg)     -> (generate_url, models_url, headers)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
_CFG_FILE = ROOT / "data" / ".llm_config.json"


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    icon: str
    default_base: str
    default_port: int
    models_endpoint: str
    generate_endpoint: str
    auth_header: str | None  # None for local providers


PROVIDERS: dict[str, Provider] = {
    "ollama": Provider(
        key="ollama", label="Ollama", icon="🦙",
        default_base="http://localhost", default_port=11434,
        models_endpoint="/api/tags",
        generate_endpoint="/api/generate",
        auth_header=None,
    ),
    "lmstudio": Provider(
        key="lmstudio", label="LM Studio", icon="🎬",
        default_base="http://localhost", default_port=1234,
        models_endpoint="/v1/models",
        generate_endpoint="/v1/chat/completions",
        auth_header=None,
    ),
    "openai": Provider(
        key="openai", label="OpenAI-compat", icon="✨",
        default_base="https://api.openai.com", default_port=443,
        models_endpoint="/v1/models",
        generate_endpoint="/v1/chat/completions",
        auth_header="Authorization",
    ),
    "anthropic": Provider(
        key="anthropic", label="Anthropic-compat", icon="🧠",
        default_base="https://api.anthropic.com", default_port=443,
        models_endpoint="/v1/models",
        generate_endpoint="/v1/messages",
        auth_header="x-api-key",
    ),
}

DEFAULT_CONFIG: dict[str, Any] = {
    "provider":    "ollama",
    "base_url":    "http://localhost",
    "port":        11434,
    "model":       "llama3",
    "api_key":     "",
    "temperature": 0.1,
    "timeout":     120,
}


def load_config() -> dict[str, Any]:
    try:
        if _CFG_FILE.exists():
            return {**DEFAULT_CONFIG, **json.loads(_CFG_FILE.read_text(encoding="utf-8"))}
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict[str, Any]) -> None:
    _CFG_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CFG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    tmp.replace(_CFG_FILE)


def _normalize_base(cfg: dict) -> str:
    base = (cfg.get("base_url") or "").rstrip("/")
    if not base.startswith("http"):
        base = f"http://{base}"
    port = cfg.get("port")
    if port and ":" not in base.split("//", 1)[1]:
        base = f"{base}:{port}"
    return base


def resolve_endpoints(cfg: dict) -> tuple[str, str, dict]:
    """Return (generate_url, models_url, headers) for the active config."""
    provider = PROVIDERS.get(cfg.get("provider", "ollama"), PROVIDERS["ollama"])
    base = _normalize_base(cfg)
    headers: dict[str, str] = {}
    if provider.auth_header and cfg.get("api_key"):
        if provider.auth_header == "Authorization":
            headers["Authorization"] = f"Bearer {cfg['api_key']}"
        else:
            headers[provider.auth_header] = cfg["api_key"]
        if provider.key == "anthropic":
            headers["anthropic-version"] = "2023-06-01"
    return (
        base + provider.generate_endpoint,
        base + provider.models_endpoint,
        headers,
    )


def test_connection(cfg: dict) -> tuple[bool, str, list[str]]:
    """Hit the provider's models endpoint. Returns (ok, message, models). Never raises."""
    provider = PROVIDERS.get(cfg.get("provider"))
    if not provider:
        return False, f"Unknown provider: {cfg.get('provider')!r}", []

    _, models_url, headers = resolve_endpoints(cfg)

    try:
        r = requests.get(models_url, headers=headers, timeout=5)
    except requests.ConnectionError:
        return False, f"Cannot reach {models_url} (connection refused)", []
    except requests.Timeout:
        return False, f"Timeout after 5s contacting {models_url}", []
    except Exception as e:
        return False, f"{type(e).__name__}: {e}", []

    if not r.ok:
        return False, f"HTTP {r.status_code} from {models_url}", []
    try:
        data = r.json()
    except Exception:
        return False, f"Non-JSON response from {models_url}", []

    if provider.key == "ollama":
        models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    else:
        models = [m.get("id", "") for m in data.get("data", []) if m.get("id")]

    return True, f"Connected — {len(models)} model(s) available", models
