"""
Validator for PollutantReading data.

Validates:
- Required fields are present
- Values are numeric and within physical bounds
- Timestamp is recent (within 2 hours)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)

# Physical bounds for each pollutant (min, max)
POLLUTANT_BOUNDS = {
    "pm25":         (0.0,  1000.0),   # μg/m³
    "pm10":         (0.0,  2000.0),   # μg/m³
    "no2":          (0.0,  2000.0),   # μg/m³
    "so2":          (0.0,  2000.0),   # μg/m³
    "co":           (0.0,  100.0),    # mg/m³
    "o3":           (0.0,  1000.0),   # μg/m³
    "temperature":  (-50.0, 60.0),    # °C
    "humidity":     (0.0,  100.0),    # %
    "wind_speed":   (0.0,  100.0),    # m/s
    "pressure":     (800.0, 1100.0),  # hPa
}

# Maximum age of a reading before it is considered stale
MAX_AGE_HOURS = 2


@dataclass
class ValidationResult:
    """Result of validating a single PollutantReading."""
    is_valid: bool
    reasons: List[str] = field(default_factory=list)

    def add_error(self, msg: str):
        self.reasons.append(msg)
        self.is_valid = False

    def __str__(self) -> str:
        if self.is_valid:
            return "Valid"
        return "Invalid: " + "; ".join(self.reasons)


def validate_reading(reading) -> ValidationResult:
    """
    Validate a PollutantReading object.

    Args:
        reading: A PollutantReading (from waqi_connector) or any object
                 with the expected attributes.

    Returns:
        ValidationResult with is_valid flag and list of failure reasons.
    """
    result = ValidationResult(is_valid=True)

    # 1. Required fields must be present
    if not getattr(reading, "station_id", None):
        result.add_error("Missing required field: station_id")
    if not getattr(reading, "timestamp", None):
        result.add_error("Missing required field: timestamp")

    # At least one pollutant must be present
    pollutants = ["pm25", "pm10", "no2", "so2", "co", "o3"]
    present = [p for p in pollutants if getattr(reading, p, None) is not None]
    if not present:
        result.add_error("No pollutant values present in reading")

    # 2. Timestamp must be recent
    ts = getattr(reading, "timestamp", None)
    if ts is not None:
        now_utc = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = now_utc - ts
        if age > timedelta(hours=MAX_AGE_HOURS):
            result.add_error(
                f"Timestamp too old: {age} (max {MAX_AGE_HOURS}h)"
            )
        if age.total_seconds() < -300:  # 5 minute future tolerance
            result.add_error(f"Timestamp is in the future: {ts}")

    # 3. Validate numeric bounds for each field
    for field_name, (min_val, max_val) in POLLUTANT_BOUNDS.items():
        value = getattr(reading, field_name, None)
        if value is None:
            continue  # Optional field, skip
        if not isinstance(value, (int, float)):
            result.add_error(f"{field_name} must be numeric, got {type(value).__name__}")
            continue
        if value < min_val:
            result.add_error(
                f"{field_name}={value} below physical minimum {min_val}"
            )
        if value > max_val:
            result.add_error(
                f"{field_name}={value} exceeds physical maximum {max_val}"
            )

    if not result.is_valid:
        logger.warning(
            "Validation failed for station %s: %s",
            getattr(reading, "station_id", "unknown"),
            result.reasons,
        )
    return result
