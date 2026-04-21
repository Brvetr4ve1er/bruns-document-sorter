"""IMPROVEMENT 6: Document Type Auto-Categorization"""
from db.database import record_classification, get_classification
from enum import Enum
import re


class DocumentType(Enum):
    """Supported document types in shipment pipeline."""
    BOOKING = "BOOKING"
    DEPARTURE = "DEPARTURE"
    BILL_OF_LADING = "BILL_OF_LADING"
    CUSTOMS = "CUSTOMS"
    RECEIPT = "RECEIPT"
    UNKNOWN = "UNKNOWN"


# Patterns for document type detection
DOCUMENT_PATTERNS = {
    DocumentType.BOOKING: [
        r"booking\s*(?:confirmation|reference|number)",
        r"space\s*confirmation",
        r"booking\s*form",
        r"reservation\s*confirmation",
    ],
    DocumentType.DEPARTURE: [
        r"bill\s*of\s*lading",
        r"b\.l\.",
        r"bl\s*number",
        r"shipper\s*reference",
        r"departure\s*notice",
    ],
    DocumentType.BILL_OF_LADING: [
        r"bill\s*of\s*lading",
        r"b\.o\.l\.",
        r"bl\s*number",
        r"carrier.*receipt",
    ],
    DocumentType.CUSTOMS: [
        r"customs\s*declaration",
        r"invoice",
        r"commercial\s*invoice",
        r"customs\s*clearance",
        r"import.*permit",
    ],
    DocumentType.RECEIPT: [
        r"receipt",
        r"delivery\s*receipt",
        r"proof\s*of\s*delivery",
        r"pod",
    ],
}


def classify_document(text_content: str, confidence_threshold: float = 0.6) -> tuple[DocumentType, float]:
    """Classify document type based on content patterns. Returns (type, confidence)."""
    text_lower = text_content.lower() if text_content else ""

    if not text_lower:
        return DocumentType.UNKNOWN, 0.0

    type_scores = {}

    for doc_type, patterns in DOCUMENT_PATTERNS.items():
        matches = 0
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                matches += 1

        if matches > 0:
            # Confidence based on pattern matches (0.5-1.0)
            confidence = min(1.0, 0.5 + (matches / len(patterns)) * 0.5)
            type_scores[doc_type] = confidence

    if not type_scores:
        return DocumentType.UNKNOWN, 0.0

    # Return highest confidence type
    best_type = max(type_scores.items(), key=lambda x: x[1])

    if best_type[1] >= confidence_threshold:
        return best_type[0], best_type[1]
    else:
        return DocumentType.UNKNOWN, best_type[1]


def classify_extraction(shipment_data: dict, shipment_id: int = None) -> dict:
    """Classify extracted shipment data. Returns classification result."""
    text_content = " ".join([
        str(shipment_data.get("tan_number", "")),
        str(shipment_data.get("item_description", "")),
        str(shipment_data.get("vessel_name", "")),
    ])

    doc_type, confidence = classify_document(text_content)

    result = {
        "document_type": doc_type.value,
        "confidence": confidence,
        "predicted_category": doc_type.value,
    }

    if shipment_id:
        record_classification(
            shipment_id=shipment_id,
            doc_type=doc_type.value,
            predicted_category=doc_type.value,
            confidence=confidence
        )

    return result


def get_document_classification(shipment_id: int) -> dict:
    """Retrieve stored classification for a shipment."""
    return get_classification(shipment_id=shipment_id)
