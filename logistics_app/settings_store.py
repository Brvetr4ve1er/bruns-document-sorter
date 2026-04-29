"""Persistent settings layer — reads/writes data/settings.json."""
import json
import os

_SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "data", "settings.json")

DEFAULTS = {
    "ollama_url": "http://localhost:11434/api/generate",
    "ollama_model": "llama3",
    "ollama_timeout": 120,
    "input_dir": os.path.join(os.path.dirname(__file__), "data", "input"),
    "logs_dir": os.path.join(os.path.dirname(__file__), "data", "logs"),
    "db_path": os.path.join(os.path.dirname(__file__), "data", "logistics.db"),
    "text_char_limit": 6000,
}


def load() -> dict:
    if os.path.exists(_SETTINGS_PATH):
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
                stored = json.load(f)
            return {**DEFAULTS, **stored}
        except Exception:
            pass
    return dict(DEFAULTS)


def save(settings: dict):
    """Atomic write: write to a temp file then rename, so a crash mid-write
    can never leave settings.json corrupted."""
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    tmp = _SETTINGS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, _SETTINGS_PATH)


def apply_to_config(settings: dict):
    """Push runtime settings into the loaded config module. Missing keys fall
    back to the defaults so partially-written settings files still work."""
    import config
    merged = {**DEFAULTS, **(settings or {})}
    # Normalise Ollama URL — user may have given base URL without /api/generate
    url = (merged["ollama_url"] or "").rstrip("/")
    if url and not url.endswith("/api/generate"):
        url = url + "/api/generate"
    config.OLLAMA_URL = url or DEFAULTS["ollama_url"]
    config.OLLAMA_MODEL = merged["ollama_model"]
    config.OLLAMA_TIMEOUT = merged["ollama_timeout"]
    config.INPUT_DIR = merged["input_dir"]
    config.LOGS_DIR = merged["logs_dir"]
    config.DB_PATH = merged["db_path"]
