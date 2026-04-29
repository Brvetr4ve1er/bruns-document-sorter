import json
import requests
import config
from config import LLM_PROMPT_TEMPLATE


def _call_ollama(prompt: str) -> str:
    payload = {
        "model": config.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,   # deterministic extraction
            "num_ctx": 8192,
        },
    }
    r = requests.post(config.OLLAMA_URL, json=payload, timeout=config.OLLAMA_TIMEOUT)
    r.raise_for_status()
    return r.json().get("response", "")


def parse_document(text: str) -> tuple[str | None, str | None]:
    """Return (raw_response, error)."""
    # read live text limit from settings if present
    try:
        import settings_store
        limit = int(settings_store.load().get("text_char_limit", 6000))
    except Exception:
        limit = 6000

    prompt = LLM_PROMPT_TEMPLATE.format(text=text[:limit])

    for attempt in range(2):
        try:
            return _call_ollama(prompt), None
        except requests.exceptions.ConnectionError:
            return None, "Ollama not running — start with: ollama serve"
        except requests.exceptions.Timeout:
            if attempt == 0:
                continue
            return None, f"LLM timeout after retry ({config.OLLAMA_TIMEOUT}s)"
        except Exception as e:
            if attempt == 0:
                continue
            return None, f"LLM error: {e}"
    return None, "LLM failed after retry"


# ─── High-level class interface (used by the Processing page UI) ──────────────

class ParserAgent:
    """Wraps the parse_document function with a file-level interface."""

    def process_file(self, file_path: str) -> dict:
        """
        Process a single PDF file end-to-end.

        Returns:
            dict with keys:
                success   (bool)
                action    ("INSERT" | "UPDATE" | "SKIP")
                tan       (str | None)
                containers (int)
                error     (str | None)
        """
        try:
            from parsers.pdf_extractor import extract_text
            from database_logic.database import upsert_shipment
            from models.schema import ShipmentData
            import os

            text = extract_text(file_path)
            if not text or not text.strip():
                return {"success": False, "error": "No text extracted from PDF", "action": "—", "tan": None, "containers": 0}

            raw, err = parse_document(text)
            if err:
                return {"success": False, "error": err, "action": "—", "tan": None, "containers": 0}

            # Strip markdown fences if model added them
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
                clean = clean.strip()

            data = json.loads(clean)
            shipment = ShipmentData(**data)
            action, shipment_id = upsert_shipment(shipment, source_file=os.path.basename(file_path))

            return {
                "success": True,
                "action": action,
                "tan": shipment.tan_number or "—",
                "containers": len(shipment.containers),
                "error": None,
            }

        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON parse error: {e}", "action": "—", "tan": None, "containers": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "action": "—", "tan": None, "containers": 0}
