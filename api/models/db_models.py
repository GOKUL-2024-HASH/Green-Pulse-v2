"""
SQLAlchemy ORM models for GreenPulse 2.0.
Tables: stations, pollutant_readings, rolling_averages, compliance_events,
        violation_reports, officer_actions, audit_ledger, users
"""

import uuid
import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Enum, Index, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum


Base = declarative_base()


class ZoneType(str, enum.Enum):
    industrial = "industrial"
    residential = "residential"
    roadside = "roadside"
    ecologically_sensitive = "ecologically_sensitive"


class StationStatus(str, enum.Enum):
    online = "online"
    offline = "offline"
    maintenance = "maintenance"


class TierLevel(str, enum.Enum):
    MONITOR = "MONITOR"
    FLAG = "FLAG"
    VIOLATION = "VIOLATION"


class ViolationStatus(str, enum.Enum):
    MONITOR = "MONITOR"
    FLAG = "FLAG"
    PENDING_OFFICER_REVIEW = "PENDING_OFFICER_REVIEW"
    ESCALATED = "ESCALATED"
    DISMISSED = "DISMISSED"
    RESOLVED = "RESOLVED"


class OfficerActionType(str, enum.Enum):
    ESCALATE = "ESCALATE"
    DISMISS = "DISMISS"
    FLAG_FOR_MONITORING = "FLAG_FOR_MONITORING"


class UserRole(str, enum.Enum):
    officer = "officer"
    supervisor = "supervisor"
    admin = "admin"


class Station(Base):
    __tablename__ = "stations"

    id = Column(String(20), primary_key=True)
    name = Column(String(200), nullable=False)
    waqi_id = Column(String(50), nullable=True)
    zone = Column(Enum(ZoneType), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    status = Column(Enum(StationStatus), default=StationStatus.online, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    pollutant_readings = relationship("PollutantReading", back_populates="station")
    rolling_averages = relationship("RollingAverage", back_populates="station")
    compliance_events = relationship("ComplianceEvent", back_populates="station")

    __table_args__ = (
        Index("ix_stations_status", "status"),
        Index("ix_stations_zone", "zone"),
    )


class PollutantReading(Base):
    __tablename__ = "pollutant_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(String(20), ForeignKey("stations.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    pm25 = Column(Float, nullable=True)
    pm10 = Column(Float, nullable=True)
    no2 = Column(Float, nullable=True)
    so2 = Column(Float, nullable=True)
    co = Column(Float, nullable=True)
    o3 = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    wind_speed = Column(Float, nullable=True)
    wind_direction = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    dew_point = Column(Float, nullable=True)
    confidence_score = Column(Float, nullable=True)
    is_valid = Column(Boolean, default=True)
    validation_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    station = relationship("Station", back_populates="pollutant_readings")

    __table_args__ = (
        Index("ix_pollutant_readings_station_timestamp", "station_id", "timestamp"),
        Index("ix_pollutant_readings_timestamp", "timestamp"),
    )


class RollingAverage(Base):
    __tablename__ = "rolling_averages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(String(20), ForeignKey("stations.id"), nullable=False)
    pollutant = Column(String(10), nullable=False)
    window_hours = Column(Integer, nullable=False)  # 1, 8, or 24
    average_value = Column(Float, nullable=False)
    reading_count = Column(Integer, nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    station = relationship("Station", back_populates="rolling_averages")

    __table_args__ = (
        Index("ix_rolling_averages_station_pollutant", "station_id", "pollutant"),
        Index("ix_rolling_averages_window", "window_start", "window_end"),
    )


class ComplianceEvent(Base):
    __tablename__ = "compliance_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(String(20), ForeignKey("stations.id"), nullable=False)
    pollutant = Column(String(10), nullable=False)
    tier = Column(Enum(TierLevel), nullable=False)
    status = Column(Enum(ViolationStatus), nullable=False)
    observed_value = Column(Float, nullable=False)
    limit_value = Column(Float, nullable=False)
    exceedance_percent = Column(Float, nullable=False)
    averaging_period = Column(String(10), nullable=False)  # 1hr, 8hr, 24hr
    rule_name = Column(String(200), nullable=False)
    legal_reference = Column(String(500), nullable=True)
    rule_version = Column(String(50), nullable=True)
    met_context = Column(JSON, nullable=True)
    window_start = Column(DateTime(timezone=True), nullable=True)
    window_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    station = relationship("Station", back_populates="compliance_events")
    violation_reports = relationship("ViolationReport", back_populates="compliance_event")
    officer_actions = relationship("OfficerAction", back_populates="compliance_event")

    __table_args__ = (
        Index("ix_compliance_events_station_pollutant", "station_id", "pollutant"),
        Index("ix_compliance_events_status", "status"),
        Index("ix_compliance_events_tier", "tier"),
        Index("ix_compliance_events_created_at", "created_at"),
    )


class ViolationReport(Base):
    __tablename__ = "violation_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    compliance_event_id = Column(UUID(as_uuid=True), ForeignKey("compliance_events.id"), nullable=False)
    report_html = Column(Text, nullable=True)
    report_pdf_path = Column(String(500), nullable=True)
    ledger_hash = Column(String(64), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())

    compliance_event = relationship("ComplianceEvent", back_populates="violation_reports")

    __table_args__ = (
        Index("ix_violation_reports_event_id", "compliance_event_id"),
    )


class OfficerAction(Base):
    __tablename__ = "officer_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    compliance_event_id = Column(UUID(as_uuid=True), ForeignKey("compliance_events.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action_type = Column(Enum(OfficerActionType), nullable=False)
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    compliance_event = relationship("ComplianceEvent", back_populates="officer_actions")
    user = relationship("User", back_populates="officer_actions")

    __table_args__ = (
        Index("ix_officer_actions_event_id", "compliance_event_id"),
        Index("ix_officer_actions_user_id", "user_id"),
    )


class AuditLedger(Base):
    __tablename__ = "audit_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sequence_number = Column(Integer, nullable=False, unique=True)
    event_type = Column(String(100), nullable=False)
    event_id = Column(String(200), nullable=False)
    event_data = Column(JSON, nullable=False)
    prev_hash = Column(String(64), nullable=False)
    entry_hash = Column(String(64), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_audit_ledger_sequence", "sequence_number"),
        Index("ix_audit_ledger_event_type", "event_type"),
        Index("ix_audit_ledger_created_at", "created_at"),
    )


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(200), nullable=False, unique=True)
    hashed_password = Column(String(200), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.officer)
    jurisdiction = Column(String(200), nullable=True)  # e.g. "Delhi", "Mumbai"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    officer_actions = relationship("OfficerAction", back_populates="user")

    __table_args__ = (
        Index("ix_users_email", "email"),
        Index("ix_users_role", "role"),
    )
