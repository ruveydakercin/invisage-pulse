from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app import models


def create_import_batch(db: Session, source: str, mapping_json: dict | None = None) -> models.ImportBatch:
    """
    CSV hattıyla aynı mantık:
    - ImportBatch aç
    - status = processing
    - source = "jira"
    - mapping_json opsiyonel (Jira için genelde None olacak)
    """
    batch = models.ImportBatch(
        source=source,
        status="processing",
        mapping_json=mapping_json,
        created_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch

import json
from datetime import datetime, timezone


def write_one_mock_raw_row(db: Session, batch_id: int, project_key: str) -> int:
    """
    MVP kanıtı: Jira connector, CSV hattıyla aynı raw row tablosuna yazabiliyor mu?
    Şimdilik 1 adet jira_project raw row basıyoruz.
    """
    row = {
        "source": "jira",
        "row_type": "jira_project",
        "project_key": project_key,
        "project_name": f"{project_key} (mock)",
        "jira_project_id": "mock-1",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    raw_row = models.ImportRawRow(
        batch_id=batch_id,
        row_number=1,
        raw_json=json.dumps(row, ensure_ascii=False),
        normalized_hint=None,
        row_status="PENDING",
    )
    db.add(raw_row)
    db.flush()

    # Jira için required_fields + mapping şimdilik yok.
    # Burada Phase C'deki validate_row'u aynen kullanacağız.
    # Imports router'dan import ediyoruz: bu "şimdilik" kabul.
    from app.routers.imports import validate_row

    required_fields = ["source", "row_type", "project_key"]
    errors = validate_row(row, required_fields, mapping=None)

    if errors:
        raw_row.row_status = "INVALID"
        db.add(
            models.ImportError(
                batch_id=batch_id,
                raw_row_id=raw_row.id,
                severity="ERROR",
                error_code="JIRA_ROW_INVALID",
                message=str(errors),
                field_name=None,
                raw_value=None,
            )
        )
        return 0

    raw_row.row_status = "VALID"
    return 1