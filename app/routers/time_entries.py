from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_db
from app import models
from app.schemas import TimeEntryCreate, TimeEntryOut

router = APIRouter(prefix="/time-entries", tags=["time-entries"])


@router.post("", response_model=TimeEntryOut, status_code=status.HTTP_201_CREATED)
def create_time_entry(payload: TimeEntryCreate, db: Session = Depends(get_db)):
    wi = db.get(models.WorkItem, payload.work_item_id)
    if not wi:
        raise HTTPException(status_code=404, detail="WorkItem not found")

    res = db.get(models.Resource, payload.resource_id)
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found")

    obj = models.TimeEntry(
        work_item_id=payload.work_item_id,
        resource_id=payload.resource_id,
        minutes=payload.minutes,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("", response_model=list[TimeEntryOut])
def list_time_entries(work_item_id: int, db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.TimeEntry)
        .where(models.TimeEntry.work_item_id == work_item_id)
        .order_by(models.TimeEntry.id.asc())
    ).scalars().all()
    return rows