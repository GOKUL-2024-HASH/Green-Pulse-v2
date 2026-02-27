"""
GreenPulse 2.0 — FastAPI Application Entry Point
"""
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext

from api.database import Base, engine, SessionLocal
from api.models.db_models import User, Station, ZoneType, StationStatus
from api.routes import auth, violations, actions, reports, stations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _seed_data():
    """Auto-seed admin user and stations on first startup."""
    db = SessionLocal()
    try:
        # --- Admin User ---
        admin = db.query(User).filter(User.email == "admin@greenpulse.in").first()
        if not admin:
            db.add(User(
                email="admin@greenpulse.in",
                full_name="System Administrator",
                hashed_password=_pwd_ctx.hash("admin123"),
                role="admin",
                is_active=True,
            ))
            logger.info("Seeded admin user: admin@greenpulse.in / admin123")
        else:
            logger.info("Admin user already exists — skipping seed")

        # --- Stations ---
        cfg_path = Path("/app/config/stations.json")
        if cfg_path.exists():
            station_cfgs = json.loads(cfg_path.read_text())
            for s in station_cfgs:
                exists = db.query(Station).filter(Station.id == s["station_id"]).first()
                if not exists:
                    zone_raw = s.get("zone", "residential")
                    zone = ZoneType(zone_raw) if zone_raw in ZoneType._value2member_map_ else ZoneType.residential
                    db.add(Station(
                        id=s["station_id"],
                        name=s["name"],
                        waqi_id=s.get("waqi_id"),
                        latitude=s.get("latitude", 0.0),
                        longitude=s.get("longitude", 0.0),
                        zone=zone,
                        status=StationStatus.online,
                    ))
                    logger.info("Seeded station: %s", s["station_id"])
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Seed failed: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("GreenPulse API starting up — running seed")
    _seed_data()
    yield
    logger.info("GreenPulse API shutting down")


app = FastAPI(
    title="GreenPulse 2.0 API",
    description="Environmental Compliance Monitoring Platform",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router,       prefix="/api/auth",       tags=["Auth"])
app.include_router(violations.router, prefix="/api/violations", tags=["Violations"])
app.include_router(actions.router,    prefix="/api/actions",    tags=["Officer Actions"])
app.include_router(reports.router,    prefix="/api/reports",    tags=["Reports"])
app.include_router(stations.router,   prefix="/api/stations",   tags=["Stations"])


@app.get("/api/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "greenpulse-api", "version": "2.0.0"}
