"""
GreenPulse 2.0 — Pipeline Main Entry Point (Pathway Edition)

Architecture: Two concurrent execution contexts
  Thread-1 — APScheduler (scheduler thread):
      Every POLL_INTERVAL seconds:
        1. Fetch live readings from WAQI API
        2. Persist raw readings to pollutant_readings table
        3. Call engine.push_reading() for each pollutant value
           → This inserts one row into the Pathway ConnectorSubject

  Thread-2 — Pathway streaming graph (daemon thread):
      pw.run() blocks here indefinitely.
      As readings arrive via push_reading(), Pathway:
        - Updates sliding windows (1hr, 8hr, 24hr) incrementally
        - Emits window averages to on_window_result() callback

  on_window_result() callback (called from Pathway thread):
      - Applies NAAQS classification tiers
      - Persists new compliance events to DB
      - Logs violations, flags, monitors to stdout

Pathway is NOT batch-called. It runs as a persistent streaming graph.
The scheduler job only calls engine.push_reading() — no window math.
"""

import json
import logging
import os
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [PIPELINE] %(levelname)s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("pipeline.main")

# ── Configuration ──────────────────────────────────────────────────────────────
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "300"))
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://greenpulse:greenpulse123@postgres:5432/greenpulse_db",
)
STATIONS_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "config", "stations.json"
)

# ── Graceful shutdown flag ─────────────────────────────────────────────────────
_running = True


def _shutdown(sig, frame):
    global _running
    logger.info("Shutdown signal (%s) — stopping scheduler.", sig)
    _running = False


signal.signal(signal.SIGINT,  _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


# ── DB helpers (raw SQL — no ORM in pipeline thread) ─────────────────────────

def persist_reading(db, station_id: str, reading) -> None:
    """Insert raw pollutant reading into pollutant_readings."""
    from sqlalchemy import text
    db.execute(text("""
        INSERT INTO pollutant_readings (
            id, station_id, timestamp,
            pm25, pm10, no2, so2, co, o3,
            temperature, humidity, wind_speed, wind_direction,
            pressure, dew_point,
            confidence_score, is_valid, created_at
        ) VALUES (
            :id, :station_id, :timestamp,
            :pm25, :pm10, :no2, :so2, :co, :o3,
            :temperature, :humidity, :wind_speed, :wind_direction,
            :pressure, :dew_point,
            :confidence_score, true, NOW()
        )
        ON CONFLICT DO NOTHING
    """), {
        "id":              uuid.uuid4(),
        "station_id":      station_id,
        "timestamp":       reading.timestamp,
        "pm25":            reading.pm25,
        "pm10":            reading.pm10,
        "no2":             reading.no2,
        "so2":             reading.so2,
        "co":              reading.co,
        "o3":              reading.o3,
        "temperature":     reading.temperature,
        "humidity":        reading.humidity,
        "wind_speed":      reading.wind_speed,
        "wind_direction":  reading.wind_direction,
        "pressure":        reading.pressure,
        "dew_point":       reading.dew_point,
        "confidence_score": 1.0,
    })


def persist_compliance_event(db, event) -> Optional[uuid.UUID]:
    """
    Insert a compliance event. Deduplicates within 2-hour window to avoid
    flooding rows for the same ongoing breach.
    """
    from sqlalchemy import text

    row = db.execute(text("""
        SELECT id FROM compliance_events
        WHERE station_id = :station_id
          AND pollutant   = :pollutant
          AND tier        = :tier
          AND status NOT IN ('DISMISSED', 'RESOLVED')
          AND window_end >= NOW() - INTERVAL '2 hours'
        LIMIT 1
    """), {
        "station_id": event.station_id,
        "pollutant":  event.pollutant,
        "tier":       event.tier,
    }).fetchone()

    if row:
        logger.debug(
            "Skipping duplicate: station=%s pollutant=%s tier=%s",
            event.station_id, event.pollutant, event.tier,
        )
        return None

    event_id = uuid.uuid4()
    rule = event.rule_result
    db.execute(text("""
        INSERT INTO compliance_events (
            id, station_id, pollutant, tier, status,
            observed_value, limit_value, exceedance_percent,
            averaging_period, rule_name, legal_reference, rule_version,
            met_context, window_start, window_end, created_at
        ) VALUES (
            :id, :station_id, :pollutant, :tier, :status,
            :observed_value, :limit_value, :exceedance_percent,
            :averaging_period, :rule_name, :legal_reference, :rule_version,
            :met_context, :window_start, :window_end, NOW()
        )
    """), {
        "id":                 event_id,
        "station_id":         event.station_id,
        "pollutant":          event.pollutant,
        "tier":               event.tier,
        "status":             event.status,
        "observed_value":     rule.observed_value,
        "limit_value":        rule.limit_value,
        "exceedance_percent": rule.exceedance_percent,
        "averaging_period":   f"{event.window_hours}hr",
        "rule_name":          rule.rule_name,
        "legal_reference":    rule.legal_reference,
        "rule_version":       rule.rule_version,
        "met_context":        json.dumps(event.met_context) if event.met_context else None,
        "window_start":       event.window_start,
        "window_end":         event.window_end,
    })
    return event_id


# ── APScheduler job: fetch WAQI data, persist, classify via SQL windows ──────

WINDOW_CONFIGS = [
    (1,  "1hr"),
    (8,  "8hr"),
    (24, "24hr"),
]


def _compute_and_classify(station_id: str, zone: str, sql_engine, stations_by_id):
    """
    After a new reading is persisted, compute rolling window averages via SQL
    for each pollutant and run the classifier.  This runs entirely in the
    APScheduler thread — no Pathway thread dependency.
    """
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from pipeline.classification.classifier import classify
    from pipeline.streaming.pathway_engine import WindowResult

    pollutants = ["pm25", "pm10", "no2", "so2", "co", "o3"]

    with Session(sql_engine) as db:
        for pollutant in pollutants:
            window_results = []

            for hours, label in WINDOW_CONFIGS:
                row = db.execute(text(f"""
                    SELECT
                        AVG({pollutant})     AS avg_value,
                        COUNT(*)             AS reading_count,
                        MIN(timestamp)       AS window_start,
                        MAX(timestamp)       AS window_end,
                        AVG(temperature)     AS avg_temp,
                        AVG(humidity)        AS avg_humidity,
                        AVG(wind_speed)      AS avg_wind
                    FROM pollutant_readings
                    WHERE station_id = :sid
                      AND timestamp  > NOW() - INTERVAL '{hours} hours'
                      AND {pollutant} IS NOT NULL
                """), {"sid": station_id}).fetchone()

                if not row or row.avg_value is None or row.reading_count < 1:
                    continue

                wr = WindowResult(
                    station_id=station_id,
                    pollutant=pollutant,
                    window_hours=hours,
                    window_label=label,
                    average_value=round(float(row.avg_value), 4),
                    reading_count=int(row.reading_count),
                    window_start=row.window_start,
                    window_end=row.window_end,
                    met_context={
                        "temperature": row.avg_temp,
                        "humidity":    row.avg_humidity,
                        "wind_speed":  row.avg_wind,
                    },
                )
                window_results.append(wr)
                logger.info(
                    "SQL window: station=%s pollutant=%s hours=%d avg=%.2f n=%d",
                    station_id, pollutant, hours, wr.average_value, wr.reading_count,
                )

            if not window_results:
                continue

            try:
                events = classify(
                    station_id=station_id,
                    pollutant=pollutant,
                    window_results=window_results,
                    zone=zone,
                    db_session=None,
                    met_context=window_results[-1].met_context,
                )
            except Exception as exc:
                logger.error("Classifier error for %s/%s: %s", station_id, pollutant, exc)
                continue

            for event in (events or []):
                try:
                    eid = persist_compliance_event(db, event)
                    db.commit()
                    if eid:
                        tier = event.tier
                        if tier == "VIOLATION":
                            logger.warning(
                                "🚨 VIOLATION station=%s pollutant=%s window=%dhr "
                                "observed=%.1f limit=%.1f excess=%.1f%%",
                                event.station_id, event.pollutant, event.window_hours,
                                event.observed_value, event.limit_value,
                                event.exceedance_percent,
                            )
                        elif tier == "FLAG":
                            logger.warning(
                                "⚠  FLAG      station=%s pollutant=%s window=%dhr "
                                "observed=%.1f limit=%.1f",
                                event.station_id, event.pollutant, event.window_hours,
                                event.observed_value, event.limit_value,
                            )
                        else:
                            logger.info(
                                "ℹ  MONITOR   station=%s pollutant=%s window=%dhr "
                                "observed=%.1f",
                                event.station_id, event.pollutant, event.window_hours,
                                event.observed_value,
                            )
                except Exception as exc:
                    logger.error("Failed to persist compliance event: %s", exc)


def _poll_job(stations, engine, sql_engine):
    """
    APScheduler calls this every POLL_INTERVAL seconds.
    Responsibilities:
      1. Fetch live readings from WAQI API
      2. Persist raw readings to DB
      3. Compute rolling SQL window averages (1hr / 8hr / 24hr)
      4. Run classifier on window averages
      5. Persist compliance events to DB

    NOTE: Pathway push is still attempted for streaming graph continuity,
    but classification no longer depends on the Pathway thread being alive.
    """
    from pipeline.ingestion.waqi_connector import fetch_reading
    from sqlalchemy.orm import Session

    logger.info("── Poll cycle starting — %d stations ──", len(stations))

    for station in stations:
        station_id = station["station_id"]
        waqi_id    = station.get("waqi_id")
        zone       = station.get("zone", "residential")

        if not waqi_id:
            logger.warning("Station %s has no waqi_id — skipping", station_id)
            continue

        reading = fetch_reading(waqi_id, station_id)
        if reading is None:
            logger.warning("No reading for station %s", station_id)
            continue

        # 1. Persist raw reading to DB
        try:
            with Session(sql_engine) as db:
                persist_reading(db, station_id, reading)
                db.commit()
            logger.info("Persisted reading for station %s", station_id)
        except Exception as exc:
            logger.error("Failed to persist reading for %s: %s", station_id, exc)
            continue   # skip window computation if raw reading failed

        # 2. Compute SQL windows + classify + persist compliance events
        try:
            _compute_and_classify(station_id, zone, sql_engine, {s["station_id"]: s for s in stations})
        except Exception as exc:
            logger.error("Window/classify failed for %s: %s", station_id, exc)

        # 3. Also push into Pathway (best-effort — no longer blocking)
        try:
            met_ctx = {
                "temperature":    reading.temperature,
                "humidity":       reading.humidity,
                "wind_speed":     reading.wind_speed,
                "wind_direction": reading.wind_direction,
                "pressure":       reading.pressure,
                "dew_point":      reading.dew_point,
            }
            pollutants = {
                "pm25": reading.pm25,
                "pm10": reading.pm10,
                "no2":  reading.no2,
                "so2":  reading.so2,
                "co":   reading.co,
                "o3":   reading.o3,
            }
            for pollutant, value in pollutants.items():
                if value is not None:
                    engine.push_reading(
                        station_id=station_id,
                        pollutant=pollutant,
                        value=value,
                        timestamp=reading.timestamp,
                        confidence=1.0,
                        met_context=met_ctx,
                    )
        except Exception as exc:
            logger.debug("Pathway push failed (non-critical): %s", exc)

    logger.info("── Poll cycle complete ──")


# ── Pathway window result callback: classification → DB ──────────────────────

def make_result_handler(stations_by_id, sql_engine):
    """
    Returns the on_window_result callback that Pathway calls for each
    updated window average. This function runs in the Pathway thread.

    Strategy: Pathway emits one (station, pollutant, window_hours) result
    at a time. We buffer the latest result per (station_id, pollutant,
    window_hours) key, then call classify() with the full list of window
    results for that pollutant — which is what the classifier expects.
    """
    from pipeline.classification.classifier import classify
    from sqlalchemy.orm import Session
    from collections import defaultdict

    # Buffer: (station_id, pollutant, window_hours) → WindowResult
    _window_buffer: dict = {}

    def on_window_result(window_result):
        """
        Pathway calls this whenever a sliding window emits an updated avg.
        """
        sid = window_result.station_id
        pol = window_result.pollutant
        key = (sid, pol, window_result.window_hours)

        # Update the buffer with the latest result for this window
        _window_buffer[key] = window_result

        # Collect all windows currently known for this station+pollutant
        all_windows = [
            v for k, v in _window_buffer.items()
            if k[0] == sid and k[1] == pol
        ]

        logger.info(
            "Classifier received window result: station=%s pollutant=%s "
            "hours=%d avg=%.2f (total windows buffered: %d)",
            sid, pol, window_result.window_hours,
            window_result.average_value, len(all_windows),
        )

        station_cfg = stations_by_id.get(sid, {})
        zone = station_cfg.get("zone", "residential")

        try:
            events = classify(
                station_id=sid,
                pollutant=pol,
                window_results=all_windows,
                zone=zone,
                db_session=None,  # no consecutive-day check in streaming mode
                met_context=window_result.met_context,
            )
        except Exception as exc:
            logger.error("Classifier error for %s/%s: %s", sid, pol, exc)
            return

        for event in (events or []):
            try:
                with Session(sql_engine) as db:
                    eid = persist_compliance_event(db, event)
                    db.commit()
                if eid:
                    tier = event.tier
                    if tier == "VIOLATION":
                        logger.warning(
                            "🚨 VIOLATION  station=%-6s pollutant=%-4s "
                            "window=%dhr observed=%.1f limit=%.1f excess=%.1f%%",
                            event.station_id, event.pollutant, event.window_hours,
                            event.observed_value, event.limit_value,
                            event.exceedance_percent,
                        )
                    elif tier == "FLAG":
                        logger.warning(
                            "⚠  FLAG       station=%-6s pollutant=%-4s "
                            "window=%dhr observed=%.1f limit=%.1f",
                            event.station_id, event.pollutant, event.window_hours,
                            event.observed_value, event.limit_value,
                        )
                    else:
                        logger.info(
                            "ℹ  MONITOR    station=%-6s pollutant=%-4s "
                            "window=%dhr observed=%.1f",
                            event.station_id, event.pollutant, event.window_hours,
                            event.observed_value,
                        )
            except Exception as exc:
                logger.error("Failed to persist compliance event: %s", exc)

    return on_window_result


# ── Main entry point ──────────────────────────────────────────────────────────

def main() -> None:
    import pathway as pw
    from apscheduler.schedulers.background import BackgroundScheduler
    from sqlalchemy import create_engine
    from pipeline.streaming.pathway_engine import get_engine

    # Load station configs
    with open(STATIONS_CONFIG) as f:
        stations = json.load(f)
    stations_by_id = {s["station_id"]: s for s in stations}
    logger.info("Loaded %d stations from config.", len(stations))

    # SQLAlchemy engine (shared across scheduler + callback threads)
    sql_engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

    # ── 1. Initialise Pathway engine ─────────────────────────────────────────
    pathway_engine = get_engine()
    on_result = make_result_handler(stations_by_id, sql_engine)

    # ── 2. Start Pathway streaming graph in Thread-2 ─────────────────────────
    pathway_thread = pathway_engine.run_in_thread(on_result)
    logger.info("Pathway graph running in dedicated thread")

    # Give Pathway a moment to initialise before the first poll
    time.sleep(3)

    # ── 3. Start APScheduler (Thread-1) ──────────────────────────────────────
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        func=_poll_job,
        args=[stations, pathway_engine, sql_engine],
        trigger="interval",
        seconds=POLL_INTERVAL,
        next_run_time=datetime.now(timezone.utc),  # run immediately on start
        id="waqi_poll",
        name="WAQI Poll",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — polling every %ds",
        POLL_INTERVAL,
    )

    # ── 4. Block main thread — wait for SIGINT/SIGTERM ───────────────────────
    logger.info(
        "GreenPulse 2.0 Pipeline running. "
        "Press Ctrl+C or send SIGTERM to stop."
    )
    try:
        while _running:
            time.sleep(1)
    finally:
        logger.info("Stopping scheduler…")
        scheduler.shutdown(wait=False)
        sql_engine.dispose()
        logger.info("Pipeline stopped cleanly.")


if __name__ == "__main__":
    main()
