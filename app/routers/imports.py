from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app import models
import csv
import json
import io

router = APIRouter(prefix="/imports", tags=["imports"])


def normalize_row(row: dict) -> dict:
    clean = {}
    for k, v in row.items():
        key = (k or "").strip().lstrip("\ufeff")
        if isinstance(v, str):
            val = v.strip()
        else:
            val = v
        clean[key] = val
    return clean


def parse_mapping_json(mapping_json: str | None) -> dict | None:
    if mapping_json is None:
        return None

    try:
        m = json.loads(mapping_json)
    except Exception:
        raise HTTPException(status_code=400, detail="mapping_json is not valid JSON")

    if not isinstance(m, dict):
        raise HTTPException(status_code=400, detail="mapping_json must be a JSON object")

    cleaned = {}
    for k, v in m.items():
        if not isinstance(k, str) or k.strip() == "":
            raise HTTPException(status_code=400, detail="mapping_json keys must be non-empty strings")
        if not isinstance(v, str) or v.strip() == "":
            raise HTTPException(status_code=400, detail="mapping_json values must be non-empty strings")
        cleaned[k.strip().lstrip("\ufeff")] = v.strip()

    return cleaned


def validate_row(row: dict, required_fields: list[str], mapping: dict | None) -> list[dict]:
    errors: list[dict] = []

    for f in required_fields:
        v = row.get(f)
        if v is None or str(v).strip() == "":
            errors.append(
                {
                    "field_name": f,
                    "error_code": "MISSING_REQUIRED",
                    "message": "Required field is missing",
                    "raw_value": None if v is None else str(v),
                }
            )

    minutes_csv_cols: list[str] = []
    if mapping is None:
        minutes_csv_cols = ["minutes"]
    else:
        minutes_csv_cols = [csv_col for csv_col, target in mapping.items() if target == "minutes"]

    for col in minutes_csv_cols:
        m = row.get(col)
        if m is not None and str(m).strip() != "":
            try:
                int(str(m).strip())
            except Exception:
                errors.append(
                    {
                        "field_name": col,
                        "error_code": "INVALID_NUMBER",
                        "message": "minutes must be an integer",
                        "raw_value": str(m),
                    }
                )

    return errors


def extract_for_timeentry(row: dict, mapping: dict | None) -> tuple[str, str, int, str | None]:
    if mapping is None:
        ext_key = (row.get("work_item_external_key") or "").strip()
        res_ext = (row.get("resource_external_id") or "").strip()
        minutes_raw = (row.get("minutes") or "").strip()
        title = row.get("title")
        title = title.strip() if isinstance(title, str) and title.strip() != "" else None
    else:

        def pick(target_name: str) -> str:
            for csv_col, target in mapping.items():
                if target == target_name:
                    return (row.get(csv_col) or "").strip()
            return ""

        ext_key = pick("external_key")
        res_ext = pick("resource_external_id")
        minutes_raw = pick("minutes")
        title_val = pick("title")
        title = title_val if title_val != "" else None

    if ext_key == "" or res_ext == "" or minutes_raw == "":
        raise ValueError("Missing required fields for normalization")

    minutes_int = int(minutes_raw)
    return ext_key, res_ext, minutes_int, title

def extract_for_jira_issue(row: dict) -> tuple[str, str, str, dict]:
    """
    Jira raw row -> normalize için minimum alanlar:
    - project_key
    - issue_id
    - issue_key
    - payload (issue json)
    """
    project_key = (row.get("project_key") or "").strip()
    issue_id = (row.get("issue_id") or "").strip()
    issue_key = (row.get("issue_key") or "").strip()
    payload = row.get("payload") or {}

    if project_key == "" or issue_id == "" or issue_key == "":
        raise ValueError("Missing required fields for jira_issue normalization")

    if not isinstance(payload, dict):
        raise ValueError("payload is not an object")

    return project_key, issue_id, issue_key, payload

def extract_for_jira_worklog(row: dict) -> tuple[str, str, str, int, str]:
    """
    Jira worklog raw row -> normalize için minimum alanlar:
    - project_key
    - issue_key
    - author_account_id (top-level ya da payload.author.accountId)
    - time_spent_seconds (top-level ya da payload.timeSpentSeconds)
    - worklog_id (top-level worklog_id ya da payload.id)
    """
    project_key = (row.get("project_key") or "").strip()
    issue_key = (row.get("issue_key") or "").strip()

    payload = row.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    # worklog id (top-level ya da payload.id)
    worklog_id = (row.get("worklog_id") or "").strip()
    if worklog_id == "":
        pid = payload.get("id")
        worklog_id = (str(pid).strip() if pid is not None else "")

    if worklog_id == "":
        raise ValueError("Missing worklog_id for jira_worklog normalization")

    # author accountId (prefer top-level, fallback payload)
    author_account_id = (row.get("author_account_id") or "").strip()
    if author_account_id == "":
        author = payload.get("author") or {}
        if isinstance(author, dict):
            author_account_id = (author.get("accountId") or "").strip()

    # time spent seconds (prefer top-level snake_case, then camelCase in payload)
    tss = row.get("time_spent_seconds")
    if tss is None or str(tss).strip() == "":
        tss = payload.get("timeSpentSeconds")

    if tss is None or str(tss).strip() == "":
        raise ValueError("Missing timeSpentSeconds for jira_worklog normalization")

    try:
        time_spent_seconds = int(str(tss).strip())
    except Exception:
        raise ValueError("timeSpentSeconds is not an integer")

    if project_key == "" or issue_key == "" or author_account_id == "":
        raise ValueError("Missing required fields for jira_worklog normalization")

    minutes = max(1, time_spent_seconds // 60) if time_spent_seconds > 0 else 0
    return project_key, issue_key, author_account_id, minutes, worklog_id
# TEMP: docker image missing python-multipart; disable CSV upload route to keep API up
# NOTE: normalization for existing CSV batches still works via /imports/{batch_id}/normalize
# @router.post("/csv")
# def import_csv(
#     file: UploadFile = File(...),
#     mapping_json: str | None = Form(None),
#     db: Session = Depends(get_db),
# ):
#     pass
    try:
        if mapping_json is not None and mapping_json.strip() == "":
            mapping_json = None

        mapping = parse_mapping_json(mapping_json)

        raw_bytes = file.file.read()
        try:
            content = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            content = raw_bytes.decode("utf-8", errors="replace")

        reader = csv.DictReader(io.StringIO(content))
        rows = [r for r in reader if any((v or "").strip() for v in r.values())]

        if len(rows) == 0:
            raise HTTPException(status_code=400, detail="CSV has no data rows (only header)")

        if mapping is None:
            required_fields = ["work_item_external_key", "resource_external_id", "minutes"]
        else:
            required_fields = list(mapping.keys())

        batch = models.ImportBatch(
            source="csv",
            status="processing",
            filename=file.filename,
            mapping_json=mapping_json,
            total_rows=len(rows),
            success_rows=0,
            error_rows=0,
        )
        db.add(batch)
        db.flush()

        for i, row in enumerate(rows, start=1):
            row = normalize_row(row)

            raw_row = models.ImportRawRow(
                batch_id=batch.id,
                row_number=i,
                raw_json=json.dumps(row, ensure_ascii=False),
                normalized_hint=None,
                row_status="PENDING",
            )
            db.add(raw_row)
            db.flush()

            errors = validate_row(row, required_fields, mapping)

            if errors:
                raw_row.row_status = "INVALID"
                batch.error_rows += 1

                for err in errors:
                    db.add(
                        models.ImportError(
                            batch_id=batch.id,
                            raw_row_id=raw_row.id,
                            severity="ERROR",
                            error_code=err["error_code"],
                            message=err["message"],
                            field_name=err["field_name"],
                            raw_value=err["raw_value"],
                        )
                    )
            else:
                raw_row.row_status = "VALID"
                batch.success_rows += 1

        batch.status = "completed" if batch.error_rows == 0 else "completed_err"
        db.commit()

        return {
            "batch_id": batch.id,
            "rows": len(rows),
            "success_rows": batch.success_rows,
            "error_rows": batch.error_rows,
            "status": batch.status,
            "required_fields": required_fields,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            file.file.close()
        except Exception:
            pass


@router.post("/{batch_id}/normalize")
def normalize_import_batch(
    batch_id: int,
    db: Session = Depends(get_db),
):
    batch = db.query(models.ImportBatch).filter(models.ImportBatch.id == batch_id).first()
    if batch is None:
        raise HTTPException(status_code=404, detail="ImportBatch not found")

    # MVP kuralı: Normalize sadece completed/completed_err batch'lerde çalışır
    if batch.status not in ("completed", "completed_err", "normalized", "normalized_err"):
        raise HTTPException(
            status_code=400,
            detail=f"Batch is not ready for normalization. Current status: {batch.status}",
        )

    # Idempotency (MVP): Bu batch daha önce normalize edildiyse tekrar çalıştırma
    if batch.status in ("normalized", "normalized_err"):
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "message": "Batch already normalized",
        }

    mapping = parse_mapping_json(batch.mapping_json)

    # Kaynağa göre project seçimi:
    # - csv: batch bazlı CSV-{id}
    # - jira: row'lardan gelen project_key (örn: SCRUM) ile upsert edilecek
    project_key = None
    project_name = None
    if batch.source == "csv":
        project_key = f"CSV-{batch.id}"
        project_name = f"CSV Import Batch {batch.id}"

    project = None
    if batch.source == "csv":
        project = db.query(models.Project).filter(models.Project.key == project_key).first()
        if project is None:
            project = models.Project(
                key=project_key,
                name=project_name,
            )
            db.add(project)
            db.flush()

    batch.status = "normalizing"
    db.commit()

    normalized_ok = 0
    normalized_err = 0

    raw_rows = (
        db.query(models.ImportRawRow)
        .filter(models.ImportRawRow.batch_id == batch.id)
        .filter(models.ImportRawRow.row_status == "VALID")
        .order_by(models.ImportRawRow.row_number.asc())
        .all()
    )

    if len(raw_rows) == 0:
        batch.status = "normalized"
        db.commit()
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "message": "No VALID rows to normalize",
            "valid_rows_input": 0,
            "normalized_ok": 0,
            "normalized_err": 0,
            "project_key": project_key,
        }

    for rr in raw_rows:
        try:
            worklog_id = None
            row_dict = json.loads(rr.raw_json)
            if not isinstance(row_dict, dict):
                raise ValueError("raw_json is not an object")
            row_dict = normalize_row(row_dict)

            row_type = (row_dict.get("row_type") or "").strip()

            # --- JIRA NORMALIZE (MVP): jira_issue -> Project + WorkItem upsert ---
            if batch.source == "jira" and row_type == "jira_issue":
                jira_project_key, issue_id, issue_key, payload = extract_for_jira_issue(row_dict)

                # Project upsert (örn: SCRUM)
                jira_project = db.query(models.Project).filter(models.Project.key == jira_project_key).first()
                if jira_project is None:
                    jira_project = models.Project(
                        key=jira_project_key,
                        name=jira_project_key,
                    )
                    db.add(jira_project)
                    db.flush()

                # WorkItem title: payload.fields.summary
                title = None
                fields = payload.get("fields") or {}
                if isinstance(fields, dict):
                    summary = fields.get("summary")
                    if isinstance(summary, str) and summary.strip() != "":
                        title = summary.strip()

                work_item = (
                    db.query(models.WorkItem)
                    .filter(models.WorkItem.project_id == jira_project.id)
                    .filter(models.WorkItem.external_key == issue_key)
                    .first()
                )
                if work_item is None:
                    work_item = models.WorkItem(
                        project_id=jira_project.id,
                        external_key=issue_key,
                        title=title or issue_key,
                        status=None,
                    )
                    db.add(work_item)
                    db.flush()
                else:
                    if title and work_item.title != title:
                        work_item.title = title

                # Jira MVP: TimeEntry yazmıyoruz
                rr.row_status = "IMPORTED"
                normalized_ok += 1
                continue

                        # --- JIRA NORMALIZE (MVP): jira_worklog -> Resource + TimeEntry ---
                        # --- JIRA NORMALIZE (MVP): jira_worklog -> Resource + TimeEntry (idempotent) ---
            if batch.source == "jira" and row_type == "jira_worklog":
                jira_project_key, issue_key, author_account_id, minutes_int, worklog_id = extract_for_jira_worklog(row_dict)

                # Project upsert (güvenli)
                jira_project = db.query(models.Project).filter(models.Project.key == jira_project_key).first()
                if jira_project is None:
                    jira_project = models.Project(
                        key=jira_project_key,
                        name=jira_project_key,
                    )
                    db.add(jira_project)
                    db.flush()

                # WorkItem: issue_key ile bulunmalı (jira_issue normalize yazmış olmalı)
                work_item = (
                    db.query(models.WorkItem)
                    .filter(models.WorkItem.project_id == jira_project.id)
                    .filter(models.WorkItem.external_key == issue_key)
                    .first()
                )
                if work_item is None:
                    raise ValueError(f"WorkItem not found for jira worklog issue_key={issue_key}")

                # Resource upsert (accountId bazlı)
                resource = (
                    db.query(models.Resource)
                    .filter(models.Resource.source == "jira")
                    .filter(models.Resource.external_id == author_account_id)
                    .first()
                )
                if resource is None:
                    resource = models.Resource(
                        source="jira",
                        external_id=author_account_id,
                        display_name=author_account_id,  # fallback
                    )
                    db.add(resource)
                    db.flush()

                # display_name enrichment (payload.author.displayName)
                payload = row_dict.get("payload") or {}
                if isinstance(payload, dict):
                    author = payload.get("author") or {}
                    if isinstance(author, dict):
                        dn = author.get("displayName")
                        if isinstance(dn, str) and dn.strip() != "":
                            new_name = dn.strip()
                            if resource.display_name != new_name:
                                resource.display_name = new_name

                # Idempotency: aynı worklog bir daha gelirse TimeEntry yazma
                existing_te = (
                    db.query(models.TimeEntry)
                    .filter(models.TimeEntry.source == "jira")
                    .filter(models.TimeEntry.external_id == worklog_id)
                    .first()
                )
                if existing_te is not None:
                    rr.row_status = "IMPORTED"
                    normalized_ok += 1
                    continue

                te = models.TimeEntry(
                    work_item_id=work_item.id,
                    resource_id=resource.id,
                    minutes=minutes_int,
                    source="jira",
                    external_id=worklog_id,
                )
                db.add(te)

                rr.row_status = "IMPORTED"
                normalized_ok += 1
                continue


            # --- CSV NORMALIZE (MVP): TimeEntry ---
            ext_key, res_ext, minutes_int, title = extract_for_timeentry(row_dict, mapping)

            resource = (
                db.query(models.Resource)
                .filter(models.Resource.source == "csv")
                .filter(models.Resource.external_id == res_ext)
                .first()
            )
            if resource is None:
                resource = models.Resource(
                    source="csv",
                    external_id=res_ext,
                    display_name=res_ext,
                )
                db.add(resource)
                db.flush()

            work_item = (
                db.query(models.WorkItem)
                .filter(models.WorkItem.project_id == project.id)
                .filter(models.WorkItem.external_key == ext_key)
                .first()
            )
            if work_item is None:
                work_item = models.WorkItem(
                    project_id=project.id,
                    external_key=ext_key,
                    title=title or ext_key,
                    status=None,
                )
                db.add(work_item)
                db.flush()

            te = models.TimeEntry(
                work_item_id=work_item.id,
                resource_id=resource.id,
                minutes=minutes_int,
                source="csv",
            )
            db.add(te)

            rr.row_status = "IMPORTED"
            normalized_ok += 1

        except Exception as e:
            rr.row_status = "NORM_ERR"
            normalized_err += 1

            db.add(
                models.ImportError(
                    batch_id=batch.id,
                    raw_row_id=rr.id,
                    severity="ERROR",
                    error_code="NORMALIZE_FAILED",
                    message=str(e),
                    field_name=None,
                    raw_value=None,
                )
            )

    batch.status = "normalized" if normalized_err == 0 else "normalized_err"
    db.commit()

    return {
        "batch_id": batch.id,
        "status": batch.status,
        "valid_rows_input": len(raw_rows),
        "normalized_ok": normalized_ok,
        "normalized_err": normalized_err,
        "project_key": project_key,
    }