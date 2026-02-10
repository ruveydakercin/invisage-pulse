from __future__ import annotations

from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json
import base64
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from app import models


# -------------------------
# HTTP (stdlib) helper
# -------------------------
def _basic_auth_header(email: str, api_token: str) -> str:
    token = base64.b64encode(f"{email}:{api_token}".encode("utf-8")).decode("utf-8")
    return f"Basic {token}"


def _jira_request_json(
    method: str,
    url: str,
    email: str,
    api_token: str,
    params: Optional[dict] = None,
) -> Any:
    """
    Jira HTTP JSON request helper (requests yok).
    - params varsa querystring ekler
    - 4xx/5xx -> RuntimeError ile body'den kısa mesaj verir
    """
    if params:
        qs = urllib.parse.urlencode(params, doseq=True)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{qs}"

    req = urllib.request.Request(url, method=method.upper())
    req.add_header("Authorization", _basic_auth_header(email, api_token))
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "InvisagePulse/0.1")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            if raw.strip() == "":
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        msg = body[:500] if body else str(e)
        raise RuntimeError(f"Jira HTTP {e.code}: {msg}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Jira network error: {e}")


# -------------------------
# Batch
# -------------------------
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


# -------------------------
# Jira fetchers
# -------------------------
def fetch_issues(
    base_url: str,
    email: str,
    api_token: str,
    jql: str,
    max_issues: int = 50,
    start_at: int = 0,
) -> List[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/rest/api/3/search/jql"
    params = {
        "jql": jql,
        "startAt": start_at,
        "maxResults": max_issues,
        "fields": "summary,issuetype,status,assignee,created,updated",
        "expand": "names",
    }

    data = _jira_request_json("GET", url, email, api_token, params=params)
    if not isinstance(data, dict):
        return []

    issues = data.get("issues", [])
    return issues if isinstance(issues, list) else []


def fetch_worklogs_page(
    base_url: str,
    email: str,
    api_token: str,
    issue_key: str,
    start_at: int = 0,
    max_results: int = 100,
) -> Dict[str, Any]:
    """
    Jira issue worklog endpoint (paged).
    """
    url = f"{base_url.rstrip('/')}/rest/api/3/issue/{issue_key}/worklog"
    params = {"startAt": start_at, "maxResults": max_results}

    data = _jira_request_json("GET", url, email, api_token, params=params)
    return data if isinstance(data, dict) else {}


def fetch_all_worklogs(
    base_url: str,
    email: str,
    api_token: str,
    issue_key: str,
    page_size: int = 100,
) -> List[Dict[str, Any]]:
    """
    startAt/maxResults pagination ile tüm worklog'ları toplar.
    """
    all_logs: List[Dict[str, Any]] = []
    start_at = 0

    while True:
        data = fetch_worklogs_page(
            base_url=base_url,
            email=email,
            api_token=api_token,
            issue_key=issue_key,
            start_at=start_at,
            max_results=page_size,
        )

        worklogs = data.get("worklogs", [])
        if isinstance(worklogs, list) and worklogs:
            all_logs.extend(worklogs)

        total = int(data.get("total", 0) or 0)
        max_results = int(data.get("maxResults", page_size) or page_size)
        start_at = int(data.get("startAt", start_at) or start_at)

        if start_at + max_results >= total:
            break

        start_at += max_results

    return all_logs


# -------------------------
# Writer
# -------------------------
def write_jira_issues_as_raw_rows(
    db: Session,
    batch_id: int,
    project_key: str,
    base_url: str,
    email: str,
    api_token: str,
    jql: Optional[str],
    max_issues: int,
    include_worklogs: bool,
) -> int:
    """
    Jira’dan issue çeker, ImportRawRow’a yazar.
    include_worklogs=True ise her issue için worklog endpoint’inden worklog’ları da çeker ve yazar.

    DÖNÜŞ: kaç raw row INSERT edildi (issue + worklog).
    """
    effective_jql = jql or f"project = {project_key} ORDER BY created DESC"

    issues = fetch_issues(
        base_url=base_url,
        email=email,
        api_token=api_token,
        jql=effective_jql,
        max_issues=max_issues or 50,
    )

    # mevcut validate_row fonksiyonunu kullanıyoruz (imports router içinde)
    from app.routers.imports import validate_row  # local import: circular risk azaltır

    total_raw_rows_written = 0
    row_number = 1

    for issue in issues:
        issue_id = str(issue.get("id") or "")
        issue_key = str(issue.get("key") or "")

        # ---- Issue raw row ----
        row = {
            "source": "jira",
            "row_type": "jira_issue",
            "project_key": project_key,
            "issue_id": issue_id,
            "issue_key": issue_key,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "payload": issue,
            "include_worklogs": include_worklogs,
        }

        raw_row = models.ImportRawRow(
            batch_id=batch_id,
            row_number=row_number,
            raw_json=json.dumps(row, ensure_ascii=False),
            normalized_hint=None,
            row_status="PENDING",
        )
        db.add(raw_row)
        db.flush()
        total_raw_rows_written += 1

        required_fields = ["source", "row_type", "project_key", "issue_id", "issue_key"]
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
        else:
            raw_row.row_status = "VALID"

        row_number += 1  # issue row bitti

        # ---- Worklog raw rows ----
        if include_worklogs and issue_key:
            try:
                worklogs = fetch_all_worklogs(
                    base_url=base_url,
                    email=email,
                    api_token=api_token,
                    issue_key=issue_key,
                    page_size=100,
                )
            except Exception as e:
                # Worklog çekimi patlarsa import tamamen çökmesin; hata logla devam et.
                db.add(
                    models.ImportError(
                        batch_id=batch_id,
                        raw_row_id=raw_row.id,
                        severity="ERROR",
                        error_code="JIRA_WORKLOG_FETCH_FAILED",
                        message=f"{issue_key}: {e}",
                        field_name=None,
                        raw_value=None,
                    )
                )
                worklogs = []

            for wl in worklogs:
                worklog_id = str(wl.get("id") or "")
                wl_row = {
                    "source": "jira",
                    "row_type": "jira_worklog",
                    "project_key": project_key,
                    "issue_key": issue_key,
                    "worklog_id": worklog_id,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "payload": wl,
                }

                wl_raw = models.ImportRawRow(
                    batch_id=batch_id,
                    row_number=row_number,
                    raw_json=json.dumps(wl_row, ensure_ascii=False),
                    normalized_hint=None,
                    row_status="PENDING",
                )
                db.add(wl_raw)
                db.flush()
                total_raw_rows_written += 1

                wl_required = ["source", "row_type", "project_key", "issue_key", "worklog_id"]
                wl_errors = validate_row(wl_row, wl_required, mapping=None)

                if wl_errors:
                    wl_raw.row_status = "INVALID"
                    db.add(
                        models.ImportError(
                            batch_id=batch_id,
                            raw_row_id=wl_raw.id,
                            severity="ERROR",
                            error_code="JIRA_WORKLOG_ROW_INVALID",
                            message=str(wl_errors),
                            field_name=None,
                            raw_value=None,
                        )
                    )
                else:
                    wl_raw.row_status = "VALID"

                row_number += 1

    return total_raw_rows_written