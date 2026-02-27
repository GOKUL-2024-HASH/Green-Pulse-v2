"""
Stations routes — list, get, and status management.
"""
import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.auth import get_current_user
from api.database import get_db
from api.models.db_models import Station, User

router = APIRouter()

STATIONS_CONFIG = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "stations.json"
)


def _load_stations_config():
    try:
        with open(STATIONS_CONFIG) as f:
            return json.load(f)
    except Exception:
        return []


@router.get("/")
def list_stations(
    zone: Optional[str] = Query(None, description="Filter by zone type"),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all monitoring stations with optional zone/status filters."""
    query = db.query(Station)
    if zone:
        query = query.filter(Station.zone == zone)
    if status_filter:
        query = query.filter(Station.status == status_filter)
    stations = query.order_by(Station.id).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "waqi_id": s.waqi_id,
            "zone": s.zone,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "status": s.status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in stations
    ]


@router.get("/config")
def stations_from_config(_: User = Depends(get_current_user)):
    """Return raw station config (from config/stations.json)."""
    return _load_stations_config()


@router.get("/{station_id}")
def get_station(
    station_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Get a single station by ID."""
    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail=f"Station '{station_id}' not found")
    return {
        "id": station.id,
        "name": station.name,
        "waqi_id": station.waqi_id,
        "zone": station.zone,
        "latitude": station.latitude,
        "longitude": station.longitude,
        "status": station.status,
        "created_at": station.created_at.isoformat() if station.created_at else None,
        "updated_at": station.updated_at.isoformat() if station.updated_at else None,
    }


@router.patch("/{station_id}/status")
def update_station_status(
    station_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update station operational status (officer/admin only)."""
    if current_user.role not in ("officer", "admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Insufficient role")

    station = db.query(Station).filter(Station.id == station_id).first()
    if not station:
        raise HTTPException(status_code=404, detail=f"Station '{station_id}' not found")

    new_status = body.get("status")
    if new_status not in ("online", "offline", "maintenance"):
        raise HTTPException(status_code=400, detail="status must be one of: online, offline, maintenance")

    station.status = new_status
    db.commit()
    db.refresh(station)
    return {"id": station.id, "status": station.status}
