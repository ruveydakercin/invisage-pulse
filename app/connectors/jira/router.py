from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.config import settings
from app.connectors.jira.schemas import JiraImportRequest, JiraImportResponse
from app.connectors.jira import service

router = APIRouter(prefix="/connectors/jira", tags=["connectors-jira"])


@router.post("/import", response_model=JiraImportResponse)
def import_from_jira(
    req: JiraImportRequest,
    db: Session = Depends(get_db),
) -> JiraImportResponse:
    """
    MVP (REAL):
    - ImportBatch açar
    - Jira’dan issue çeker (JQL)
    - ImportRawRow yazar
    - batch.status = completed yapar (normalize çalışabilsin)
    """

    base_url = settings.jira_base_url
    email = settings.jira_email
    api_token = settings.jira_api_token

    if not base_url or not email or not api_token:
        raise HTTPException(
            status_code=500,
            detail="Jira credentials eksik. .env içine jira_base_url, jira_email, jira_api_token eklenmeli.",
        )

    if not base_url.startswith("http"):
        raise HTTPException(status_code=500, detail="jira_base_url http/https ile başlamalı")

    batch = service.create_import_batch(db=db, source="jira", mapping_json=None)

    try:
        written = service.write_jira_issues_as_raw_rows(
            db=db,
            batch_id=batch.id,
            project_key=req.project_key,
            base_url=base_url,
            email=email,
            api_token=api_token,
            jql=req.jql,
            max_issues=req.max_issues,
            include_worklogs=req.include_worklogs,
        )
    except Exception as e:
        batch.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"Jira import failed: {e}")

    batch.status = "completed"
    db.commit()
    db.refresh(batch)

    return JiraImportResponse(
        batch_id=batch.id,
        status=batch.status,
        raw_rows_written=written,
        errors_logged=0,
        message=f"Jira import tamamlandı. {written} raw row yazıldı. Normalize çağrılabilir.",
    )