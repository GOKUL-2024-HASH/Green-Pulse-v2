"""
Reports routes — generate HTML violation reports and retrieve stored reports.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models.db_models import ComplianceEvent, Station, ViolationReport, User
from reports.generator import generate_html

router = APIRouter()


@router.post("/generate/{event_id}", status_code=201)
def generate_report(
    event_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Generate an HTML violation report for a compliance event.
    Stores it in violation_reports table and returns the report HTML.
    """
    event = db.query(ComplianceEvent).filter(ComplianceEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail=f"Compliance event '{event_id}' not found")

    station = db.query(Station).filter(Station.id == event.station_id).first()
    station_dict = {
        "station_id": station.id if station else event.station_id,
        "name": station.name if station else event.station_id,
        "zone_type": station.zone if station else "residential",
    }

    event_dict = {
        "report_id": str(uuid.uuid4())[:8].upper(),
        "pollutant": event.pollutant,
        "tier": event.tier.value if hasattr(event.tier, 'value') else str(event.tier),
        "status": event.status.value if hasattr(event.status, 'value') else str(event.status),
        "observed_value": event.observed_value,
        "limit_value": event.limit_value,
        "exceedance_value": event.observed_value - event.limit_value,
        "exceedance_percent": event.exceedance_percent,
        "averaging_period": event.averaging_period,
        "window_start": event.window_start.isoformat() if event.window_start else "—",
        "window_end": event.window_end.isoformat() if event.window_end else "—",
    }

    rule_dict = {
        "rule_name": event.rule_name,
        "legal_reference": event.legal_reference or "CPCB NAAQS 2009",
        "rule_version": event.rule_version or "CPCB NAAQS 2009",
    }

    html = generate_html(
        compliance_event=event_dict,
        station=station_dict,
        rule_result=rule_dict,
        met_context=event.met_context,
    )

    # Persist to violation_reports
    report = ViolationReport(
        id=uuid.uuid4(),
        compliance_event_id=event.id,
        report_html=html,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "report_id": str(report.id),
        "compliance_event_id": str(event.id),
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "html_length": len(html),
    }


@router.get("/{report_id}/html")
def get_report_html(
    report_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return the stored HTML report as an HTML response."""
    report = db.query(ViolationReport).filter(ViolationReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found")
    return Response(content=report.report_html, media_type="text/html")


@router.get("/")
def list_reports(
    event_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List stored violation reports, optionally filtered by compliance_event_id."""
    query = db.query(ViolationReport)
    if event_id:
        query = query.filter(ViolationReport.compliance_event_id == event_id)
    total = query.count()
    reports = query.order_by(desc(ViolationReport.generated_at)).offset(skip).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": str(r.id),
                "compliance_event_id": str(r.compliance_event_id),
                "generated_at": r.generated_at.isoformat() if r.generated_at else None,
                "ledger_hash": r.ledger_hash,
            }
            for r in reports
        ],
    }
