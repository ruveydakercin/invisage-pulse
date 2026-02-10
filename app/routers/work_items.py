from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_db
from app import models
from app.schemas import WorkItemCreate, WorkItemOut

router = APIRouter(prefix="/work-items", tags=["work-items"])


@router.post("", response_model=WorkItemOut, status_code=status.HTTP_201_CREATED)
def create_work_item(payload: WorkItemCreate, db: Session = Depends(get_db)):
    project = db.get(models.Project, payload.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    obj = models.WorkItem(
        project_id=payload.project_id,
        external_key=payload.external_key,
        title=payload.title,
        status=payload.status,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("", response_model=list[WorkItemOut])
def list_work_items(project_id: int, db: Session = Depends(get_db)):
    rows = db.execute(
        select(models.WorkItem)
        .where(models.WorkItem.project_id == project_id)
        .order_by(models.WorkItem.id.asc())
    ).scalars().all()
    return rows