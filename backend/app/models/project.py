from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class StepState(BaseModel):
    step: str
    status: str  # PENDING, RUNNING, COMPLETED, FAILED, STRANDED
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None  # Step execution result


class Project(BaseModel):
    id: str
    user_email: str
    title: str
    created_at: datetime
    book_text_path: str
    book_text: Optional[str] = None  # Included in GET response for display
    overall_status: str = "CREATED"  # CREATED, STYLE_SET, CHARACTERS_GENERATED, PORTRAITS_GENERATED, CHAPTERS_GENERATED, DONE
    current_step: int = 0
    step_states: Dict[str, StepState] = {}  # All step states with results


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    book_text: Optional[str] = Field(None, min_length=10)
    # For file upload, book_text will be read from the uploaded file


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    user_email: str
    title: str
    created_at: datetime
    overall_status: str
    current_step: int