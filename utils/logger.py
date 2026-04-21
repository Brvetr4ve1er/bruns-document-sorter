import json
import os
import re
from datetime import datetime
from config import LOGS_DIR


def _sanitize_name(name: str) -> str:
    """Strip characters that are illegal in Windows filenames."""
    base = os.path.splitext(os.path.basename(name or "log"))[0]
    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base).strip(" .")
    return base[:80] or "log"


def log_result(filename: str, extracted_json: dict | None, validation_ok: bool,
               db_action: str, error: str = None):
    """Write a per-file JSON log. Never raises — log failures are swallowed."""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        safe_name = _sanitize_name(filename)
        log_path = os.path.join(LOGS_DIR, f"{safe_name}_{timestamp}.json")

        record = {
            "filename": filename,
            "timestamp": timestamp,
            "extracted_json": extracted_json,
            "validation_ok": validation_ok,
            "db_action": db_action,
            "error": error,
        }

        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, default=str)

        return log_path
    except Exception as e:
        # Last-resort: print to console; don't bubble up into the UI
        print(f"[logger] failed to write log for {filename}: {e}")
        return None
