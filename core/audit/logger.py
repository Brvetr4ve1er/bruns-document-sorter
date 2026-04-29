import sqlite3
import json
from datetime import datetime

def log_action(
    db_path: str,
    action: str,           # e.g., "MATCH", "EDIT", "DELETE", "OVERRIDE", "EXTRACT"
    actor: str,            # e.g., "system" or username
    entity_type: str,
    entity_id: int | str,
    before: dict | None,
    after: dict | None,
) -> None:
    """Log an action to the audit_log table."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            INSERT INTO audit_log 
            (action, actor, entity_type, entity_id, before_json, after_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                action, 
                actor, 
                entity_type, 
                str(entity_id), 
                json.dumps(before) if before else None,
                json.dumps(after) if after else None,
                datetime.utcnow().isoformat()
            )
        )
        conn.commit()
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            # If audit_log doesn't exist yet, we silently ignore or log to stdout
            print(f"Warning: could not write audit log, table missing in {db_path}")
        else:
            raise e
    finally:
        conn.close()
