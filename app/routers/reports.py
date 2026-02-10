from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app import models

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/projects/{project_id}/work-items")
def work_item_summary(project_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(
            models.WorkItem.id.label("work_item_id"),
            models.WorkItem.external_key,
            models.WorkItem.title,
            func.coalesce(func.sum(models.TimeEntry.minutes), 0).label("total_minutes"),
        )
        .outerjoin(models.TimeEntry)
        .filter(models.WorkItem.project_id == project_id)
        .group_by(
            models.WorkItem.id,
            models.WorkItem.external_key,
            models.WorkItem.title,
        )
        .all()
    )

    return [
        {
            "work_item_id": r.work_item_id,
            "external_key": r.external_key,
            "title": r.title,
            "total_minutes": int(r.total_minutes),
        }
        for r in rows
    ]

@router.get("/projects/{project_id}/resources")
def resource_summary(project_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(
            models.Resource.id.label("resource_id"),
            models.Resource.display_name,
            func.coalesce(func.sum(models.TimeEntry.minutes), 0).label("total_minutes"),
        )
        .join(models.TimeEntry, models.TimeEntry.resource_id == models.Resource.id, isouter=True)
        .join(models.WorkItem, models.WorkItem.id == models.TimeEntry.work_item_id, isouter=True)
        .filter(models.WorkItem.project_id == project_id)
        .group_by(models.Resource.id, models.Resource.display_name)
        .all()
    )

    return [
        {
            "resource_id": r.resource_id,
            "display_name": r.display_name,
            "total_minutes": int(r.total_minutes),
        }
        for r in rows
    ]

@router.get("/projects/{project_id}/cost-summary")
def cost_summary(project_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(
            func.coalesce(func.sum(models.CostEntry.amount), 0).label("total_cost"),
            models.CostEntry.currency,
        )
        .join(models.WorkItem, models.WorkItem.id == models.CostEntry.work_item_id)
        .filter(models.WorkItem.project_id == project_id)
        .group_by(models.CostEntry.currency)
        .all()
    )

    return [
        {
            "project_id": project_id,
            "currency": r.currency,
            "total_cost": float(r.total_cost),
        }
        for r in rows
    ]

@router.get("/summary")
def report_summary(db: Session = Depends(get_db)):
    # 1) Totals by source + grand total
    totals_by_source = (
        db.query(models.TimeEntry.source, func.coalesce(func.sum(models.TimeEntry.minutes), 0))
        .group_by(models.TimeEntry.source)
        .all()
    )
    totals = {(src if src is not None else "unknown"): int(total or 0) for src, total in totals_by_source}
    grand_total = int(sum(totals.values()))

    # 2) By project (TimeEntry -> WorkItem -> Project)
    by_project_rows = (
        db.query(
            models.Project.key,
            models.Project.name,
            models.TimeEntry.source,
            func.coalesce(func.sum(models.TimeEntry.minutes), 0).label("minutes"),
        )
        .join(models.WorkItem, models.WorkItem.project_id == models.Project.id)
        .join(models.TimeEntry, models.TimeEntry.work_item_id == models.WorkItem.id)
        .group_by(models.Project.key, models.Project.name, models.TimeEntry.source)
        .order_by(models.Project.key.asc())
        .all()
    )

    by_project = {}
    for pkey, pname, src, mins in by_project_rows:
        src_key = src if src is not None else "unknown"
        if pkey not in by_project:
            by_project[pkey] = {"project_key": pkey, "project_name": pname, "by_source": {}, "total_minutes": 0}
        by_project[pkey]["by_source"][src_key] = int(mins or 0)
        by_project[pkey]["total_minutes"] += int(mins or 0)

    # 3) By resource (TimeEntry -> Resource)
    by_resource_rows = (
        db.query(
            models.Resource.source.label("resource_source"),
            models.Resource.external_id,
            models.Resource.display_name,
            models.TimeEntry.source.label("time_source"),
            func.coalesce(func.sum(models.TimeEntry.minutes), 0).label("minutes"),
        )
        .join(models.TimeEntry, models.TimeEntry.resource_id == models.Resource.id)
        .group_by(
            models.Resource.source,
            models.Resource.external_id,
            models.Resource.display_name,
            models.TimeEntry.source,
        )
        .order_by(models.Resource.source.asc(), models.Resource.display_name.asc())
        .all()
    )

    by_resource = {}
    for rsrc, rid, rname, tsrc, mins in by_resource_rows:
        rkey = f"{rsrc}:{rid}"
        tsrc_key = tsrc if tsrc is not None else "unknown"
        if rkey not in by_resource:
            by_resource[rkey] = {
                "resource_key": rkey,
                "resource_source": rsrc,
                "external_id": rid,
                "display_name": rname,
                "by_source": {},
                "total_minutes": 0,
            }
        by_resource[rkey]["by_source"][tsrc_key] = int(mins or 0)
        by_resource[rkey]["total_minutes"] += int(mins or 0)

    # 4) Top work items (TimeEntry -> WorkItem -> Project)
    top_workitems_rows = (
        db.query(
            models.Project.key.label("project_key"),
            models.WorkItem.external_key.label("work_item_key"),
            models.WorkItem.title.label("title"),
            func.coalesce(func.sum(models.TimeEntry.minutes), 0).label("minutes"),
        )
        .join(models.WorkItem, models.WorkItem.project_id == models.Project.id)
        .join(models.TimeEntry, models.TimeEntry.work_item_id == models.WorkItem.id)
        .group_by(models.Project.key, models.WorkItem.external_key, models.WorkItem.title)
        .order_by(func.sum(models.TimeEntry.minutes).desc())
        .limit(20)
        .all()
    )

    top_workitems = [
        {"project_key": pk, "work_item_key": wik, "title": title, "minutes": int(mins or 0)}
        for pk, wik, title, mins in top_workitems_rows
    ]

    return {
        "totals": {
            "by_source_minutes": totals,
            "grand_total_minutes": grand_total,
        },
        "by_project": list(by_project.values()),
        "by_resource": list(by_resource.values()),
        "top_work_items": top_workitems,
    }