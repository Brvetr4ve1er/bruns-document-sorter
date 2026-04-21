"""IMPROVEMENT 3 & 9: Data Confidence Scores"""
from db.database import record_confidence_score, get_container_confidence
import re


FIELD_PATTERNS = {
    "container_number": r"^[A-Z]{3,4}\d{6,7}$",
    "tan_number": r"^TAN/\d{4}/\d{4}$",
    "vessel_name": r"[A-Z]{2,}",
    "etd": r"^\d{4}-\d{2}-\d{2}$",
    "eta": r"^\d{4}-\d{2}-\d{2}$",
}


def calculate_field_confidence(field_name: str, value: str) -> float:
    """Calculate confidence score (0.0-1.0) for extracted field."""
    if not value:
        return 0.0

    confidence = 0.7  # Base confidence for presence

    # Pattern matching
    if field_name in FIELD_PATTERNS:
        if re.match(FIELD_PATTERNS[field_name], str(value)):
            confidence += 0.2
        else:
            confidence -= 0.2

    # Length heuristics
    if field_name == "tan_number" and len(str(value)) >= 12:
        confidence += 0.1
    elif field_name == "container_number" and len(str(value)) == 11:
        confidence += 0.1

    return max(0.0, min(1.0, confidence))


def score_shipment_extraction(shipment_data: dict, container_id: int = None) -> dict:
    """Score all fields in a shipment extraction."""
    scores = {}

    fields_to_score = {
        "tan_number": shipment_data.get("tan_number"),
        "item_description": shipment_data.get("item_description"),
        "shipping_company": shipment_data.get("shipping_company"),
        "vessel_name": shipment_data.get("vessel_name"),
        "etd": shipment_data.get("etd"),
        "eta": shipment_data.get("eta"),
    }

    for field_name, value in fields_to_score.items():
        conf = calculate_field_confidence(field_name, value)
        scores[field_name] = conf

        if container_id:
            record_confidence_score(container_id, field_name, conf, str(value) if value else None)

    avg_confidence = sum(scores.values()) / len(scores) if scores else 0.0
    return {
        "average": avg_confidence,
        "fields": scores,
        "quality_level": "high" if avg_confidence >= 0.8 else "medium" if avg_confidence >= 0.6 else "low"
    }


def get_low_confidence_fields(container_id: int, threshold: float = 0.6) -> list:
    """Get all fields below confidence threshold."""
    confidence_data = get_container_confidence(container_id)
    low_conf = [
        {"field": field, "confidence": conf}
        for field, conf in confidence_data.get("fields", {}).items()
        if conf < threshold
    ]
    return sorted(low_conf, key=lambda x: x["confidence"])
