from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app import models
from app.schemas import ResourceCreate, ResourceOut

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("", response_model=ResourceOut)
def create_resource(data: ResourceCreate, db: Session = Depends(get_db)):
    obj = models.Resource(
        source=data.source,
        external_id=data.external_id,
        display_name=data.display_name,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("", response_model=list[ResourceOut])
def list_resources(db: Session = Depends(get_db)):
    return db.query(models.Resource).all()