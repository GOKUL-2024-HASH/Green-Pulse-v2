"""
Officer Actions routes — create and list actions on compliance events.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from api.auth import get_current_user, require_role
from api.database import get_db
from api.models.db_models import ComplianceEvent, OfficerAction, User

router = APIRouter()


class ActionCreate(BaseModel):
    compliance_event_id: str
    action_type: str          # ESCALATE | DISMISS | FLAG_FOR_MONITORING
    reason: Optional[str] = None
    notes: Optional[str] = None


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_action(
    body: ActionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("officer", "supervisor", "admin")),
):
    """
    Record an officer action on a compliance event.
    Allowed types: ESCALATE, DISMISS, FLAG_FOR_MONITORING
    Only officer/supervisor/admin roles can act.
    """
    valid_types = {"ESCALATE", "DISMISS", "FLAG_FOR_MONITORING"}
    if body.action_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"action_type must be one of: {', '.join(valid_types)}",
        )

    event = db.query(ComplianceEvent).filter(
        ComplianceEvent.id == body.compliance_event_id
    ).first()
    if not event:
        raise HTTPException(
            status_code=404,
            detail=f"Compliance event '{body.compliance_event_id}' not found",
        )

    action = OfficerAction(
        id=uuid.uuid4(),
        compliance_event_id=event.id,
        user_id=current_user.id,
        action_type=body.action_type,
        reason=body.reason,
        notes=body.notes,
    )
    db.add(action)

    # Update event status based on action type
    status_map = {
        "ESCALATE": "ESCALATED",
        "DISMISS": "DISMISSED",
        "FLAG_FOR_MONITORING": "FLAG",
    }
    event.status = status_map[body.action_type]
    db.commit()
    db.refresh(action)

    return {
        "id": str(action.id),
        "compliance_event_id": str(action.compliance_event_id),
        "action_type": action.action_type,
        "reason": action.reason,
        "notes": action.notes,
        "created_at": action.created_at.isoformat() if action.created_at else None,
        "event_status": event.status,
    }


@router.get("/")
def list_actions(
    event_id: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all officer actions, optionally filtered by compliance_event_id."""
    query = db.query(OfficerAction)
    if event_id:
        query = query.filter(OfficerAction.compliance_event_id == event_id)
    actions = query.order_by(desc(OfficerAction.created_at)).limit(200).all()

    return [
        {
            "id": str(a.id),
            "compliance_event_id": str(a.compliance_event_id),
            "user_id": str(a.user_id),
            "action_type": a.action_type,
            "reason": a.reason,
            "notes": a.notes,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in actions
    ]
