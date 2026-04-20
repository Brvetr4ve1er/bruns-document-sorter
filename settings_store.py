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
    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def apply_to_config(settings: dict):
    """Push runtime settings into loaded config module."""
    import config
    config.OLLAMA_URL = settings["ollama_url"]
    config.OLLAMA_MODEL = settings["ollama_model"]
    config.OLLAMA_TIMEOUT = settings["ollama_timeout"]
    config.INPUT_DIR = settings["input_dir"]
    config.LOGS_DIR = settings["logs_dir"]
    config.DB_PATH = settings["db_path"]
