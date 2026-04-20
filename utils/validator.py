import json
import re
from models.schema import ShipmentData
from pydantic import ValidationError


def clean_json_string(raw: str) -> str:
    """Strip markdown code fences and trim to outermost { }."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start : end + 1]
    return raw.strip()


def _sanitize_containers(data: dict) -> dict:
    """Drop containers with missing/empty container_number so shipment can still be saved."""
    if not isinstance(data.get("containers"), list):
        data["containers"] = []
        return data
    cleaned = []
    for c in data["containers"]:
        if not isinstance(c, dict):
            continue
        num = c.get("container_number")
        if num is None:
            continue
        if not isinstance(num, str):
            num = str(num)
        num = num.strip().upper().replace(" ", "")
        # Skip placeholders like "TBA" / "TBC" / "UNKNOWN" / empty
        if not num or num in {"TBA", "TBC", "UNKNOWN", "N/A", "NULL", "NONE", "-"}:
            continue
        c["container_number"] = num
        cleaned.append(c)
    data["containers"] = cleaned
    return data


def parse_and_validate(raw_text: str):
    """Return (ShipmentData|None, raw_dict|None, error|None)."""
    cleaned = clean_json_string(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        return None, None, f"JSON parse error: {e}"

    data = _sanitize_containers(data)

    try:
        model = ShipmentData(**data)
        return model, data, None
    except ValidationError as e:
        return None, data, f"Validation error: {e}"
