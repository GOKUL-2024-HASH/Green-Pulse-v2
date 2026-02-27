"""
CPCB NAAQS Rule Engine.

Loads cpcb_naaqs.json at startup. Evaluates pollutant readings against
standardized limits. Stateless — no side effects.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config", "cpcb_naaqs.json"
)

_NAAQS_CONFIG: Optional[dict] = None

# Mapping from averaging period labels to config keys
PERIOD_KEY_MAP = {
    "1hr":   "1hr",
    "8hr":   "8hr",
    "24hr":  "24hr",
    "annual": "annual",
}

# Pollutant-to-unit mapping (for rule naming)
POLLUTANT_UNITS = {
    "pm25": "μg/m³",
    "pm10": "μg/m³",
    "no2":  "μg/m³",
    "so2":  "μg/m³",
    "o3":   "μg/m³",
    "co":   "mg/m³",
}


@dataclass
class RuleResult:
    """Result of evaluating a single pollutant reading against NAAQS limits."""
    pollutant: str
    averaging_period: str
    observed_value: float
    limit_value: float
    within_limit: bool
    exceedance_value: float        # observed - limit (0 if within)
    exceedance_percent: float      # (observed / limit - 1) * 100 (0 if within)
    rule_name: str
    legal_reference: str
    rule_version: str = "CPCB NAAQS 2009"

    def __str__(self) -> str:
        status = "OK" if self.within_limit else "EXCEEDED"
        return (
            f"[{status}] {self.pollutant} {self.averaging_period}: "
            f"{self.observed_value} / {self.limit_value} {POLLUTANT_UNITS.get(self.pollutant, '')}"
        )


def _load_naaqs() -> dict:
    """Load NAAQS config from disk. Fail fast if missing."""
    global _NAAQS_CONFIG
    if _NAAQS_CONFIG is not None:
        return _NAAQS_CONFIG

    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(
            f"CRITICAL: cpcb_naaqs.json not found at {CONFIG_PATH}. "
            "Cannot start rule engine."
        )

    with open(CONFIG_PATH, "r") as f:
        _NAAQS_CONFIG = json.load(f)

    logger.info("NAAQS config loaded from %s", CONFIG_PATH)
    return _NAAQS_CONFIG


def get_limit(pollutant: str, averaging_period: str) -> Optional[float]:
    """
    Retrieve the NAAQS limit for a given pollutant and averaging period.

    Args:
        pollutant: e.g. 'pm25', 'no2', 'o3'  (case-insensitive)
        averaging_period: e.g. '24hr', '8hr', '1hr', 'annual'

    Returns:
        Limit value or None if not found.
    """
    config = _load_naaqs()
    pollutant_upper = pollutant.upper()

    # Map our internal lowercase keys to the JSON keys
    poll_map = {
        "pm25": "PM2.5",
        "pm10": "PM10",
        "no2":  "NO2",
        "so2":  "SO2",
        "o3":   "O3",
        "co":   "CO",
    }
    json_key = poll_map.get(pollutant.lower())
    if not json_key:
        logger.warning("Unknown pollutant: %s", pollutant)
        return None

    pollutant_config = config.get(json_key, {})
    period_key = PERIOD_KEY_MAP.get(averaging_period.lower())
    if not period_key:
        logger.warning("Unknown averaging period: %s", averaging_period)
        return None

    limit = pollutant_config.get(period_key)
    return float(limit) if limit is not None else None


def evaluate(
    pollutant: str,
    averaging_period: str,
    observed_value: float,
) -> RuleResult:
    """
    Evaluate a pollutant reading against the NAAQS limit.

    Args:
        pollutant: e.g. 'pm25'
        averaging_period: e.g. '24hr', '8hr', '1hr'
        observed_value: The measured average value.

    Returns:
        RuleResult with compliance determination.

    Raises:
        ValueError: If no limit is defined for the pollutant+period combination.
    """
    config = _load_naaqs()
    legal_ref = config.get("legal_ref", "CPCB NAAQS 2009")

    limit = get_limit(pollutant, averaging_period)
    if limit is None:
        raise ValueError(
            f"No NAAQS limit defined for pollutant={pollutant} "
            f"averaging_period={averaging_period}"
        )

    unit = POLLUTANT_UNITS.get(pollutant.lower(), "")
    rule_name = (
        f"NAAQS {pollutant.upper()} {averaging_period} limit "
        f"({limit} {unit})"
    )

    within_limit = observed_value <= limit
    exceedance_value = max(0.0, round(observed_value - limit, 4))
    exceedance_percent = 0.0
    if not within_limit and limit > 0:
        exceedance_percent = round(((observed_value / limit) - 1.0) * 100.0, 2)

    result = RuleResult(
        pollutant=pollutant.lower(),
        averaging_period=averaging_period,
        observed_value=observed_value,
        limit_value=limit,
        within_limit=within_limit,
        exceedance_value=exceedance_value,
        exceedance_percent=exceedance_percent,
        rule_name=rule_name,
        legal_reference=legal_ref,
    )

    logger.debug("Rule evaluated: %s", result)
    return result
