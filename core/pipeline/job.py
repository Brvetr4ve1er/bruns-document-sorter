import uuid
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class JobStatus(str):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # e.g., "DOCUMENT_EXTRACTION"
    status: str = JobStatus.PENDING
    input_data: Dict[str, Any] = Field(default_factory=dict)
    result_data: Optional[Dict[str, Any]] = None
    logs: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    retries: int = 0
    error_message: Optional[str] = None
    
    def log(self, message: str):
        self.logs.append(f"[{datetime.utcnow().isoformat()}] {message}")

    def complete(self, result: Dict[str, Any]):
        self.status = JobStatus.COMPLETED
        self.result_data = result
        self.completed_at = datetime.utcnow()
        
    def fail(self, error: str):
        self.status = JobStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.utcnow()
