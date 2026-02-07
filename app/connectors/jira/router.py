from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.connectors.jira.schemas import JiraImportRequest, JiraImportResponse
from app.connectors.jira import service

router = APIRouter(prefix="/connectors/jira", tags=["connectors-jira"])


@router.post("/import", response_model=JiraImportResponse)
def import_from_jira(
    req: JiraImportRequest,
    db: Session = Depends(get_db),
) -> JiraImportResponse:
    """
    MVP:
    - ImportBatch açar
    - 1 adet mock jira raw row yazar
    - batch.status = completed yapar (normalize çalışabilsin)
    """

    if not req.base_url.startswith("http"):
        raise HTTPException(status_code=400, detail="base_url http/https ile başlamalı")

    batch = service.create_import_batch(
        db=db,
        source="jira",
        mapping_json=None,
    )

    written = service.write_one_mock_raw_row(
        db=db,
        batch_id=batch.id,
        project_key=req.project_key,
    )

    batch.status = "completed"
    db.commit()
    db.refresh(batch)

    return JiraImportResponse(
        batch_id=batch.id,
        status=batch.status,
        raw_rows_written=written,
        errors_logged=0,
        message="Mock Jira raw row yazıldı ve batch completed. Normalize çağrılabilir.",
    )