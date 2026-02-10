from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from app.connectors.jira.router import router as jira_router
from app.routers import reports
import json

from app.db import get_db
from app import models  # noqa: F401

from app.routers.projects import router as projects_router
from app.routers.work_items import router as work_items_router
from app.routers.resources import router as resources_router
from app.routers.time_entries import router as time_entries_router
from app.routers.cost_entries import router as cost_entries_router
from app.routers.imports import router as imports_router
from app.routers.reports import router as reports_router


app = FastAPI(title="Invisage Pulse API")

# --- Routers ---
app.include_router(projects_router)
app.include_router(work_items_router)
app.include_router(resources_router)
app.include_router(time_entries_router)
app.include_router(cost_entries_router)
app.include_router(imports_router)
app.include_router(reports_router)
app.include_router(jira_router)
app.include_router(reports.router)


# --- Health ---
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-health")
def db_health(db: Session = Depends(get_db)):
    version = db.execute(text("select version()")).fetchone()[0]
    return {"db": "ok", "version": version}


# --- (Opsiyonel) Event endpoint – şimdilik bırakıyoruz ama engine/create_all YOK ---
class EventIn(BaseModel):
    source: str
    title: str
    payload: Optional[Dict[str, Any]] = None


@app.post("/events", status_code=201)
def create_event(body: EventIn, db: Session = Depends(get_db)):
    created_at = datetime.now(timezone.utc)

    try:
        payload_str = (
            json.dumps(body.payload, ensure_ascii=False)
            if body.payload is not None
            else None
        )

        event = models.PulseEvent(
            source=body.source,
            title=body.title,
            payload=payload_str,
            created_at=created_at,
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        return {
            "id": event.id,
            "payload": body.payload,
            "created_at": created_at.isoformat(),
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))