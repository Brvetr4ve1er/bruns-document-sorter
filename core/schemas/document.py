from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from .base import AuditMixin

class DocumentType(str, Enum):
    # Logistics
    BOOKING = "BOOKING"
    DEPARTURE = "DEPARTURE"
    BILL_OF_LADING = "BILL_OF_LADING"
    
    # Travel
    PASSPORT = "PASSPORT"
    ID_CARD = "ID_CARD"
    VISA = "VISA"
    BIRTH_CERTIFICATE = "BIRTH_CERTIFICATE"
    BANK_STATEMENT = "BANK_STATEMENT"
    COMMERCIAL_REGISTRY = "COMMERCIAL_REGISTRY"
    
    UNKNOWN = "UNKNOWN"

class Document(AuditMixin):
    id: Optional[int] = None
    type: DocumentType = DocumentType.UNKNOWN
    raw_text: Optional[str] = None
    extracted_json: Optional[dict] = None
    confidence: float = 0.0
    source_file: Optional[str] = None
    module: str  # "logistics" or "travel"
