"""
Tier Classifier — GreenPulse 2.0

Classifies compliance events into three tiers based on window averages:
  TIER 3 (VIOLATION): 24hr average exceeds limit OR consecutive day breach
  TIER 2 (FLAG):      8hr average exceeds limit
  TIER 1 (MONITOR):   1hr average exceeds limit

All three tiers can trigger simultaneously for different pollutants at the
same station. Zone-adjusted thresholds from zones.json are applied for
roadside stations.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

from pipeline.rules.rule_engine import evaluate, RuleResult
from pipeline.streaming.pathway_engine import WindowResult

logger = logging.getLogger(__name__)

ZONES_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config", "zones.json"
)

_ZONES_CONFIG: Optional[dict] = None


def _load_zones() -> dict:
    global _ZONES_CONFIG
    if _ZONES_CONFIG is not None:
        return _ZONES_CONFIG
    if os.path.exists(ZONES_CONFIG_PATH):
        with open(ZONES_CONFIG_PATH, "r") as f:
            _ZONES_CONFIG = json.load(f)
    else:
        logger.warning("zones.json not found, using default thresholds")
        _ZONES_CONFIG = {}
    return _ZONES_CONFIG


def _get_zone_adjustment(zone: str) -> float:
    """Return threshold adjustment factor for the given zone (default 1.0)."""
    zones = _load_zones()
    return zones.get(zone, {}).get("threshold_adjustment", 1.0)


@dataclass
class ClassificationEvent:
    """A single tier classification result for one pollutant at one station."""
    station_id: str
    pollutant: str
    tier: str              # "MONITOR", "FLAG", "VIOLATION"
    status: str            # ViolationStatus value
    rule_result: RuleResult
    window_hours: int
    window_start: datetime
    window_end: datetime
    met_context: Optional[dict] = None
    is_consecutive_day_breach: bool = False

    @property
    def observed_value(self) -> float:
        return self.rule_result.observed_value

    @property
    def limit_value(self) -> float:
        return self.rule_result.limit_value

    @property
    def exceedance_percent(self) -> float:
        return self.rule_result.exceedance_percent


@dataclass
class ClassificationResult:
    """All classification events produced for one reading cycle at one station."""
    station_id: str
    events: List[ClassificationEvent] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def has_violation(self) -> bool:
        return any(e.tier == "VIOLATION" for e in self.events)

    def has_flag(self) -> bool:
        return any(e.tier == "FLAG" for e in self.events)


def _check_consecutive_day_breach(
    station_id: str,
    pollutant: str,
    db_session=None,
) -> bool:
    """
    Check if the same station+pollutant had a 24hr breach in the previous 24 hours.
    Queries audit_ledger for a TIER_3_VIOLATION event.

    When no DB session is provided (e.g. in tests), returns False.
    """
    if db_session is None:
        return False

    try:
        from sqlalchemy import text
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        result = db_session.execute(text("""
            SELECT COUNT(*) FROM compliance_events
            WHERE station_id = :station_id
              AND pollutant = :pollutant
              AND tier = 'VIOLATION'
              AND averaging_period = '24hr'
              AND created_at >= :cutoff
              AND created_at < NOW() - INTERVAL '1 hour'
        """), {
            "station_id": station_id,
            "pollutant": pollutant,
            "cutoff": cutoff,
        })
        count = result.scalar()
        return count > 0
    except Exception as e:
        logger.error("Error checking consecutive day breach: %s", e)
        return False


def classify(
    station_id: str,
    pollutant: str,
    window_results: List[WindowResult],
    zone: str = "residential",
    db_session=None,
    met_context: Optional[dict] = None,
) -> List[ClassificationEvent]:
    """
    Classify a set of window results for a single pollutant at one station.

    Args:
        station_id: Station identifier.
        pollutant: Pollutant name (e.g. 'pm25').
        window_results: List of WindowResults (1hr, 8hr, 24hr).
        zone: Station zone type (e.g. 'roadside', 'residential').
        db_session: SQLAlchemy session for consecutive day breach check.
        met_context: Meteorological context dict.

    Returns:
        List of ClassificationEvents (may be empty if no breach).
    """
    zone_factor = _get_zone_adjustment(zone)
    events: List[ClassificationEvent] = []

    # Build lookup: window_hours → WindowResult
    window_map: Dict[int, WindowResult] = {
        wr.window_hours: wr for wr in window_results
    }

    # TIER 3: Check 24hr window first (highest priority)
    wr_24 = window_map.get(24)
    if wr_24:
        adjusted_value = wr_24.average_value / zone_factor
        try:
            rule = evaluate(pollutant, "24hr", adjusted_value)
            if not rule.within_limit:
                is_consec = _check_consecutive_day_breach(station_id, pollutant, db_session)
                events.append(ClassificationEvent(
                    station_id=station_id,
                    pollutant=pollutant,
                    tier="VIOLATION",
                    status="PENDING_OFFICER_REVIEW",
                    rule_result=rule,
                    window_hours=24,
                    window_start=wr_24.window_start,
                    window_end=wr_24.window_end,
                    met_context=met_context or wr_24.met_context,
                    is_consecutive_day_breach=is_consec,
                ))
                logger.info(
                    "TIER 3 VIOLATION: station=%s pollutant=%s "
                    "observed=%.2f limit=%.2f excess=%.1f%%",
                    station_id, pollutant, rule.observed_value,
                    rule.limit_value, rule.exceedance_percent
                )
        except ValueError as e:
            logger.debug("No 24hr limit for %s/%s: %s", pollutant, "24hr", e)
    elif wr_24 is None:
        # Also check if consecutive day breach should escalate even
        # if we don't yet have a full 24hr window
        pass

    # TIER 2: Check 8hr window
    wr_8 = window_map.get(8)
    if wr_8:
        adjusted_value = wr_8.average_value / zone_factor
        try:
            rule = evaluate(pollutant, "8hr", adjusted_value)
            if not rule.within_limit:
                events.append(ClassificationEvent(
                    station_id=station_id,
                    pollutant=pollutant,
                    tier="FLAG",
                    status="FLAG",
                    rule_result=rule,
                    window_hours=8,
                    window_start=wr_8.window_start,
                    window_end=wr_8.window_end,
                    met_context=met_context or wr_8.met_context,
                ))
                logger.info(
                    "TIER 2 FLAG: station=%s pollutant=%s "
                    "observed=%.2f limit=%.2f excess=%.1f%%",
                    station_id, pollutant, rule.observed_value,
                    rule.limit_value, rule.exceedance_percent
                )
        except ValueError as e:
            logger.debug("No 8hr limit for %s/%s: %s", pollutant, "8hr", e)

    # TIER 1: Check 1hr window
    wr_1 = window_map.get(1)
    if wr_1:
        adjusted_value = wr_1.average_value / zone_factor
        try:
            rule = evaluate(pollutant, "1hr", adjusted_value)
            if not rule.within_limit:
                events.append(ClassificationEvent(
                    station_id=station_id,
                    pollutant=pollutant,
                    tier="MONITOR",
                    status="MONITOR",
                    rule_result=rule,
                    window_hours=1,
                    window_start=wr_1.window_start,
                    window_end=wr_1.window_end,
                    met_context=met_context or wr_1.met_context,
                ))
                logger.info(
                    "TIER 1 MONITOR: station=%s pollutant=%s "
                    "observed=%.2f limit=%.2f excess=%.1f%%",
                    station_id, pollutant, rule.observed_value,
                    rule.limit_value, rule.exceedance_percent
                )
        except ValueError as e:
            logger.debug("No 1hr limit for %s/%s: %s", pollutant, "1hr", e)

    return events


def classify_all_pollutants(
    station_id: str,
    all_window_results: Dict[str, List[WindowResult]],
    zone: str = "residential",
    db_session=None,
) -> ClassificationResult:
    """
    Classify all pollutants for a station in one call.

    Args:
        station_id: Station identifier.
        all_window_results: Dict mapping pollutant → [WindowResult].
        zone: Station zone type.
        db_session: Optional SQLAlchemy session.

    Returns:
        ClassificationResult with all triggered events.
    """
    result = ClassificationResult(station_id=station_id)

    for pollutant, window_results in all_window_results.items():
        met_ctx = window_results[0].met_context if window_results else None
        events = classify(
            station_id=station_id,
            pollutant=pollutant,
            window_results=window_results,
            zone=zone,
            db_session=db_session,
            met_context=met_ctx,
        )
        result.events.extend(events)

    if result.events:
        logger.info(
            "Classification complete for station=%s: %d events "
            "(VIOLATION=%d, FLAG=%d, MONITOR=%d)",
            station_id,
            len(result.events),
            sum(1 for e in result.events if e.tier == "VIOLATION"),
            sum(1 for e in result.events if e.tier == "FLAG"),
            sum(1 for e in result.events if e.tier == "MONITOR"),
        )

    return result
