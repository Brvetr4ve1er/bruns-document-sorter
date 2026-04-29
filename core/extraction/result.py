from pydantic import BaseModel, Field
from datetime import datetime
from typing import Dict, Any

class ExtractionResult(BaseModel):
    data: Dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    prompt_version: str
    model: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    raw_response: str
    doc_type: str
