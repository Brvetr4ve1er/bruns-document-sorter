from typing import List, Optional
from pydantic import BaseModel, field_validator
from .base import AuditMixin
from ..normalization.names import name_normalize
from ..normalization.dates import date_normalize

class Person(AuditMixin):
    id: Optional[int] = None
    family_id: Optional[int] = None
    full_name: str
    normalized_name: str
    dob: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    
    @field_validator("full_name")
    @classmethod
    def set_normalized(cls, v):
        # We don't auto-set normalized_name here because we need `values` to do that, 
        # but in Pydantic V2 we can just trust the caller to set it or compute it.
        return v
        
    @field_validator("dob", mode="before")
    @classmethod
    def norm_date(cls, v):
        return date_normalize(v)

class Family(AuditMixin):
    id: Optional[int] = None
    family_name: str
    head_person_id: Optional[int] = None
    case_reference: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    
    members: List[Person] = []
