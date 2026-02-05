from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime


class EventCreate(BaseModel):
    source: str = Field(..., max_length=50)
    title: str = Field(..., max_length=200)
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventOut(BaseModel):
    id: int
    source: str
    title: str
    payload: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemy objesinden map’lemek için
