"""
Violations routes — list, filter, get, and tier breakdown.
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models.db_models import ComplianceEvent, OfficerAction, Station, User

router = APIRouter()


@router.get("/")
def list_violations(
    tier: Optional[str] = Query(None, description="MONITOR | FLAG | VIOLATION"),
    status: Optional[str] = Query(None),
    station_id: Optional[str] = Query(None),
    pollutant: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, description="ISO date string"),
    to_date: Optional[str] = Query(None, description="ISO date string"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List compliance events with flexible filters and pagination."""
    query = db.query(ComplianceEvent)

    if tier:
        query = query.filter(ComplianceEvent.tier == tier)
    if status:
        query = query.filter(ComplianceEvent.status == status)
    if station_id:
        query = query.filter(ComplianceEvent.station_id == station_id)
    if pollutant:
        query = query.filter(ComplianceEvent.pollutant == pollutant)
    if from_date:
        query = query.filter(ComplianceEvent.created_at >= from_date)
    if to_date:
        query = query.filter(ComplianceEvent.created_at <= to_date)

    total = query.count()
    events = query.order_by(desc(ComplianceEvent.created_at)).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [_serialize_event(e) for e in events],
    }


@router.get("/summary")
def violations_summary(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return counts by tier and status for dashboard KPIs."""
    from sqlalchemy import func
    tiers = (
        db.query(ComplianceEvent.tier, func.count(ComplianceEvent.id))
        .group_by(ComplianceEvent.tier)
        .all()
    )
    statuses = (
        db.query(ComplianceEvent.status, func.count(ComplianceEvent.id))
        .group_by(ComplianceEvent.status)
        .all()
    )
    return {
        "by_tier": {t: c for t, c in tiers},
        "by_status": {s: c for s, c in statuses},
        "total": db.query(ComplianceEvent).count(),
    }


@router.get("/{event_id}")
def get_violation(
    event_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get a single compliance event with its officer actions."""
    event = db.query(ComplianceEvent).filter(ComplianceEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Compliance event '{event_id}' not found")

    actions = (
        db.query(OfficerAction)
        .filter(OfficerAction.compliance_event_id == event.id)
        .order_by(desc(OfficerAction.created_at))
        .all()
    )

    result = _serialize_event(event)
    result["officer_actions"] = [
        {
            "id": str(a.id),
            "action_type": a.action_type,
            "reason": a.reason,
            "notes": a.notes,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in actions
    ]
    return result


def _serialize_event(e: ComplianceEvent) -> dict:
    return {
        "id": str(e.id),
        "station_id": e.station_id,
        "pollutant": e.pollutant,
        "tier": e.tier,
        "status": e.status,
        "observed_value": e.observed_value,
        "limit_value": e.limit_value,
        "exceedance_percent": e.exceedance_percent,
        "averaging_period": e.averaging_period,
        "rule_name": e.rule_name,
        "legal_reference": e.legal_reference,
        "met_context": e.met_context,
        "window_start": e.window_start.isoformat() if e.window_start else None,
        "window_end": e.window_end.isoformat() if e.window_end else None,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
