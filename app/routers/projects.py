from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_db
from app import models
from app.schemas import ProjectCreate, ProjectOut
from sqlalchemy import select, func

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    existing = db.execute(
        select(models.Project).where(models.Project.key == payload.key)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Project with key '{payload.key}' already exists",
        )

    obj = models.Project(key=payload.key, name=payload.name)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    rows = db.execute(select(models.Project).order_by(models.Project.id.asc())).scalars().all()
    return rows
@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Project, project_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Project not found")
    return obj

@router.get("/{project_id}/summary")
def project_summary(project_id: int, db: Session = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    total_minutes = db.execute(
        select(func.coalesce(func.sum(models.TimeEntry.minutes), 0))
        .select_from(models.WorkItem)
        .join(models.TimeEntry, models.TimeEntry.work_item_id == models.WorkItem.id, isouter=True)
        .where(models.WorkItem.project_id == project_id)
    ).scalar_one()

    return {
        "project_id": project_id,
        "total_minutes": int(total_minutes),
    }