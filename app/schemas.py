from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime
from decimal import Decimal

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
class ProjectCreate(BaseModel):
    key: str = Field(..., max_length=50)
    name: str = Field(..., max_length=200)


class ProjectOut(BaseModel):
    id: int
    key: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

class WorkItemCreate(BaseModel):
    project_id: int
    external_key: str = Field(..., max_length=100)
    title: str = Field(..., max_length=200)
    status: str = Field(default="open", max_length=50)


class WorkItemOut(BaseModel):
    id: int
    project_id: int
    external_key: str
    title: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ResourceCreate(BaseModel):
    source: str = Field(..., max_length=30)
    external_id: str = Field(..., max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=200)


class ResourceOut(BaseModel):
    id: int
    source: str
    external_id: str
    display_name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class TimeEntryCreate(BaseModel):
    work_item_id: int
    resource_id: int
    minutes: int = Field(..., ge=1)


class TimeEntryOut(BaseModel):
    id: int
    work_item_id: int
    resource_id: int
    minutes: int
    created_at: datetime

    class Config:
        from_attributes = True

class CostEntryCreate(BaseModel):
    work_item_id: int
    resource_id: int
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="TRY", max_length=10)


class CostEntryOut(BaseModel):
    id: int
    work_item_id: int
    resource_id: int
    amount: Decimal
    currency: str
    created_at: datetime

    class Config:
        from_attributes = True
