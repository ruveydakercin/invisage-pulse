from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_db
from app import models
from app.schemas import CostEntryCreate, CostEntryOut

router = APIRouter(prefix="/cost-entries", tags=["cost-entries"])


@router.post("", response_model=CostEntryOut, status_code=status.HTTP_201_CREATED)
def create_cost_entry(payload: CostEntryCreate, db: Session = Depends(get_db)):
    wi = db.get(models.WorkItem, payload.work_item_id)
    if not wi:
        raise HTTPException(status_code=404, detail="WorkItem not found")

    res = db.get(models.Resource, payload.resource_id)
    if not res:
        raise HTTPException(status_code=404, detail="Resource not found")

    obj = models.CostEntry(
        work_item_id=payload.work_item_id,
        resource_id=payload.resource_id,
        amount=payload.amount,
        currency=payload.currency,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("", response_model=list[CostEntryOut])
def list_cost_entries(work_item_id: int, db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.CostEntry)
        .where(models.CostEntry.work_item_id == work_item_id)
        .order_by(models.CostEntry.id.asc())
    ).scalars().all()
    return rows