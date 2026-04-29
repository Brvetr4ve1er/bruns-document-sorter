from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime

class ExtractedField(BaseModel):
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    source: str         # "llm", "mrz", "manual", "regex"
    method: str         # "prompt_v1", "passporteye", "user_input"

class AuditMixin(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    modified_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "system"
    modified_by: str = "system"
