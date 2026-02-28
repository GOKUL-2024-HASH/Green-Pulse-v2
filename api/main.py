"""
GreenPulse 2.0 — FastAPI Application Entry Point
"""
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from alembic.config import Config
from alembic import command as alembic_command

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from passlib.context import CryptContext

from api.database import Base, engine, SessionLocal
from api.models.db_models import User, Station, ZoneType, StationStatus
from api.routes import auth, violations, actions, reports, stations

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def seed_admin() -> None:
    """Guarantee the admin user exists — called explicitly in lifespan."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "admin@greenpulse.in").first()
        if not existing:
            db.add(User(
                email="admin@greenpulse.in",
                full_name="System Administrator",
                hashed_password=_pwd_ctx.hash("admin123"),
                role="admin",
                is_active=True,
            ))
            db.commit()
            logger.info("Admin user seeded successfully: admin@greenpulse.in / admin123")
        else:
            logger.info("Admin user already exists — skipping")
    except Exception as e:
        db.rollback()
        logger.error("Admin seed failed: %s", e)
    finally:
        db.close()


def _seed_data():
    """Auto-seed stations on first startup."""
    db = SessionLocal()
    try:
        # Resolve stations.json from both Docker (/app/config) and Render (./config)
        cfg_path = Path("/app/config/stations.json")
        if not cfg_path.exists():
            cfg_path = Path(__file__).parent.parent / "config" / "stations.json"

        if cfg_path.exists():
            station_cfgs = json.loads(cfg_path.read_text())
            seeded = 0
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
                    seeded += 1
            db.commit()
            if seeded:
                logger.info("Seeded %d stations", seeded)
            else:
                logger.info("All stations already exist — skipping station seed")
        else:
            logger.warning("stations.json not found at either path — skipping station seed")
    except Exception as e:
        db.rollback()
        logger.error("Station seed failed: %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Step 0: Run database migrations ───────────────────────────────────────
    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option(
            "sqlalchemy.url",
            os.getenv("DATABASE_URL", "postgresql://greenpulse:greenpulse123@localhost:5432/greenpulse_db")
        )
        alembic_command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully")
    except Exception as e:
        logger.error("Migration failed: %s", e)
        raise

    # ── Step 1: Reset known passwords on every startup ────────────────────────
    try:
        _reset_db = SessionLocal()
        for email, raw_pw in [
            ("admin@greenpulse.in",   "admin123"),
            ("officer@greenpulse.in", "officer123"),
        ]:
            u = _reset_db.query(User).filter(User.email == email).first()
            if u:
                u.hashed_password = _pwd_ctx.hash(raw_pw)
                logger.info("Password reset for %s", email)
        _reset_db.commit()
    except Exception as e:
        _reset_db.rollback()
        logger.error("Password reset failed: %s", e)
    finally:
        _reset_db.close()

    # ── Step 2: Seed admin user (guaranteed, separate from station seed) ───────
    logger.info("GreenPulse API starting up — seeding admin user")
    seed_admin()

    # ── Step 3: Seed stations ──────────────────────────────────────────────────
    logger.info("Seeding stations")
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
