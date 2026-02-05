from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
import json

from app.db import Base, engine, get_db
from app import models  # noqa: F401 (model import needed for metadata)
from app.models import PulseEvent

app = FastAPI(title="Invisage Pulse API")

# ilk etapta otomatik tablo yaratma (migration'a geçince bunu kaldıracağız)
Base.metadata.create_all(bind=engine)


class EventIn(BaseModel):
    source: str
    title: str
    payload: Optional[Dict[str, Any]] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/db-health")
def db_health(db: Session = Depends(get_db)):
    version = db.execute(text("select version()")).fetchone()[0]
    return {"db": "ok", "version": version}


@app.post("/events", status_code=201)
def create_event(body: EventIn, db: Session = Depends(get_db)):
    created_at = datetime.now(timezone.utc)

    try:
        # DB kolonun varchar/text olduğu için dict'i JSON string'e çeviriyoruz
        payload_str = (
            json.dumps(body.payload, ensure_ascii=False) if body.payload is not None else None
        )

        event = PulseEvent(
            source=body.source,
            title=body.title,
            payload=payload_str,
            created_at=created_at,
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        # Response: id + payload + created_at
        return {
            "id": event.id,
            "payload": body.payload,
            "created_at": created_at.isoformat(),
        }

    except Exception as e:
        db.rollback()
        # Swagger'da da görünsün diye hatayı detail içinde dönüyoruz
        raise HTTPException(status_code=500, detail=str(e))
