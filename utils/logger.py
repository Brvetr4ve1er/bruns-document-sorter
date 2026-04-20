import json
import os
from datetime import datetime
from config import LOGS_DIR


def log_result(filename: str, extracted_json: dict | None, validation_ok: bool, db_action: str, error: str = None):
    os.makedirs(LOGS_DIR, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_name = os.path.splitext(os.path.basename(filename))[0]
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
