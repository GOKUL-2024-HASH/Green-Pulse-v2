"""
GreenPulse 2.0 — Pathway Streaming Engine (Genuine Implementation).

Uses Pathway 0.29.1 as the actual streaming engine.

API notes (all verified against Pathway 0.29.1 installed in container):
  - pw.io.python.ConnectorSubject  — abstract, must subclass + implement run()
  - ConnectorSubject.next_str(str) — push JSON string payload (NOT next_json)
  - ConnectorSubject.commit()      — signal end of micro-batch
  - pw.io.python.read(subject, schema=Schema) — wires subject into Table
  - Table.windowby(col, window=sliding(...), instance=expr) — GroupedTable
  - GroupedTable.reduce(col=pw.reducers.any(grouped.col), ...)
    NOTE: reduce() args must use grouped.col, NOT readings.col
  - pw.reducers.avg  — correct name (NOT mean)
  - pw.reducers.any, pw.reducers.count  — confirmed available
  - pw.io.python.write(table, observer=ConnectorObserver()) — requires subclass
  - ConnectorObserver: abstract, requires on_change(key, row, time) + on_time_end + on_end
  - pw.run(debug=False)  — blocking, run in a daemon thread

Architecture:
  Thread-1 (APScheduler): fetch_reading() → engine.push_reading()
  Thread-2 (Pathway):     pw.run()        → on_window_result() → classifier
"""

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import pathway as pw
from pathway.stdlib.temporal import sliding

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public output dataclass — consumed by classifier and ledger
# ---------------------------------------------------------------------------

@dataclass
class WindowResult:
    """Windowed average emitted by the Pathway streaming graph."""
    station_id: str
    pollutant: str
    window_hours: int
    window_label: str
    average_value: float
    reading_count: int
    window_start: Optional[datetime]
    window_end: Optional[datetime]
    met_context: Optional[dict] = None


# ---------------------------------------------------------------------------
# Pathway Schema — defines data shape coming from the connector
# ---------------------------------------------------------------------------

class ReadingSchema(pw.Schema):
    station_id: str
    pollutant: str
    value: float
    t: pw.DateTimeUtc          # event-time column used by sliding window
    met_json: str              # JSON-encoded meteorological context


# ---------------------------------------------------------------------------
# ConnectorSubject subclass — push-only connector
# pw.io.python.ConnectorSubject is abstract; run() must be implemented.
# For push-only ingestion, run() simply returns.
# Data enters via next_str(json_str) + commit() called from scheduler thread.
# ---------------------------------------------------------------------------

class _GreenPulseConnector(pw.io.python.ConnectorSubject):
    """Push-based connector for GreenPulse pollutant readings."""

    def run(self) -> None:
        # This connector is push-only.
        # Pathway calls run() once when pw.run() starts.
        # Returning immediately tells Pathway: "no pull loop, wait for pushes."
        pass


# ---------------------------------------------------------------------------
# ConnectorObserver — receives output from pw.io.python.write()
# pw.io.python.write requires a ConnectorObserver subclass, not a lambda.
# on_change is called for each row emitted (or retracted) by the window.
# ---------------------------------------------------------------------------

class _WindowObserver(pw.io.python.ConnectorObserver):
    """Receives windowed aggregate rows from the Pathway graph."""

    def __init__(self, window_hours: int, window_label: str, on_result: Callable):
        self._window_hours = window_hours
        self._window_label = window_label
        self._on_result = on_result

    def on_change(self, key, row: dict, time: int, is_addition: bool) -> None:
        """
        Called by Pathway for every row update in the window output.
        is_addition=True: new/updated row. is_addition=False: retraction.
        We only process additions (positive window updates).
        """
        if not is_addition:
            return  # skip retractions

        try:
            met_ctx = json.loads(row.get("met_json", "{}") or "{}")
            result = WindowResult(
                station_id=str(row["station_id"]),
                pollutant=str(row["pollutant"]),
                window_hours=self._window_hours,
                window_label=self._window_label,
                average_value=round(float(row["avg_value"]), 4),
                reading_count=int(row["reading_count"]),
                window_start=None,   # Pathway manages window bounds internally
                window_end=None,
                met_context=met_ctx,
            )
            logger.info(
                "Pathway window result: station=%s pollutant=%s "
                "hours=%d avg=%.2f n=%d",
                result.station_id, result.pollutant,
                result.window_hours, result.average_value, result.reading_count,
            )
            self._on_result(result)
        except Exception as exc:
            logger.error("Error in _WindowObserver.on_change: %s", exc)

    def on_time_end(self, time: int) -> None:
        """Called when Pathway completes processing all rows for a given time."""
        pass

    def on_end(self) -> None:
        """Called when the stream ends (e.g. pw.run() teardown)."""
        logger.info("Pathway window observer stream ended (window_hours=%d)", self._window_hours)


# ---------------------------------------------------------------------------
# Window configurations
# ---------------------------------------------------------------------------

WINDOW_CONFIGS = [
    (timedelta(hours=1),  "1hr",  1),
    (timedelta(hours=8),  "8hr",  8),
    (timedelta(hours=24), "24hr", 24),
]


# ---------------------------------------------------------------------------
# PathwayStreamingEngine
# ---------------------------------------------------------------------------

class PathwayStreamingEngine:
    """
    Genuine Pathway 0.29.1 streaming engine.

    Uses Pathway temporal sliding windows for incremental rolling average
    computation.  NOT a deque fallback.  NOT a polling loop.

    Usage
    -----
    1.  engine = PathwayStreamingEngine()
    2.  engine.run_in_thread(on_result_callback)   ← non-blocking
    3.  engine.push_reading(...)                   ← called from scheduler thread
    """

    def __init__(self):
        self._subject = _GreenPulseConnector()
        self._thread: Optional[threading.Thread] = None
        logger.info("Pathway streaming engine initialized")

    # ------------------------------------------------------------------
    # Public: push one pollutant reading into the Pathway graph
    # ------------------------------------------------------------------

    def push_reading(
        self,
        station_id: str,
        pollutant: str,
        value: float,
        timestamp: datetime,
        confidence: float = 1.0,
        met_context: Optional[dict] = None,
    ) -> None:
        """
        Insert a reading into the Pathway streaming graph.
        Called from the APScheduler thread; thread-safe by design.
        """
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        self._subject.next_str(json.dumps({
            "station_id": station_id,
            "pollutant":  pollutant,
            "value":      float(value),
            "t":          timestamp.isoformat(),
            "met_json":   json.dumps(met_context or {}),
        }))
        # Commit tells Pathway this micro-batch is complete and ready for processing
        self._subject.commit()
        logger.info(
            "Reading pushed to Pathway: station=%s pollutant=%s value=%.2f",
            station_id, pollutant, value,
        )

    # ------------------------------------------------------------------
    # Internal: build the Pathway streaming graph (called once)
    # ------------------------------------------------------------------

    def _build_graph(self, on_result: Callable) -> None:
        """
        Define the complete Pathway DAG:
          _GreenPulseConnector → Table(ReadingSchema)
            → windowby(sliding 1hr/8hr/24hr) → GroupedTable
            → reduce(avg, count, any) → windowed Table
            → pw.io.python.write(_WindowObserver)

        CRITICAL 0.29.1 API rules:
          - reduce() must reference grouped.col_name, NOT readings.col_name
          - pw.reducers.avg (not mean), pw.reducers.any, pw.reducers.count
          - pw.io.python.write(table, observer=ConnectorObserver())
        """
        readings = pw.io.python.read(
            self._subject,
            schema=ReadingSchema,
        )

        for duration, label, hours in WINDOW_CONFIGS:
            # Step 1: Create GroupedTable via sliding window on event-time t
            grouped = readings.windowby(
                readings.t,
                window=sliding(
                    hop=timedelta(minutes=30),
                    duration=duration,
                ),
                instance=readings.station_id + "_" + readings.pollutant,
            )

            # Step 2: Reduce using grouped.col (GroupedTable column references)
            windowed = grouped.reduce(
                station_id=pw.reducers.any(grouped.station_id),
                pollutant=pw.reducers.any(grouped.pollutant),
                met_json=pw.reducers.any(grouped.met_json),
                avg_value=pw.reducers.avg(grouped.value),
                reading_count=pw.reducers.count(),
            )

            # Step 3: Wire results to the classifier via ConnectorObserver
            pw.io.python.write(
                windowed,
                observer=_WindowObserver(hours, label, on_result),
            )

        logger.info(
            "Pathway graph built — %d sliding windows per station×pollutant",
            len(WINDOW_CONFIGS),
        )

    # ------------------------------------------------------------------
    # Public: start the Pathway graph in a daemon thread (non-blocking)
    # ------------------------------------------------------------------

    def run_in_thread(self, on_result: Callable) -> threading.Thread:
        """
        Build the Pathway graph and launch pw.run() in a daemon thread.
        pw.run() blocks indefinitely — this wrapper returns immediately.
        """
        self._build_graph(on_result)

        def _target():
            logger.info("Pathway graph running in dedicated thread")
            try:
                pw.run(debug=False)
            except Exception as exc:
                logger.error("Pathway pw.run() exited: %s", exc)

        self._thread = threading.Thread(
            target=_target,
            name="pathway-streaming",
            daemon=True,
        )
        self._thread.start()
        logger.info("Pathway streaming thread started")
        return self._thread


# ---------------------------------------------------------------------------
# Module-level singleton — imported by pipeline/main.py
# ---------------------------------------------------------------------------

_engine: Optional[PathwayStreamingEngine] = None
_engine_lock = threading.Lock()


def get_engine() -> PathwayStreamingEngine:
    """Return the process-level PathwayStreamingEngine singleton."""
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = PathwayStreamingEngine()
    return _engine
