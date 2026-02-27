"""
Confidence Scorer for PollutantReadings.

Computes a confidence score (0-100) for a reading by comparing it
against neighbor station readings. Readings below a threshold (60)
are quarantined and should not be used for compliance decisions.
"""

import logging
import math
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)

QUARANTINE_THRESHOLD = 60.0   # Readings below this score are quarantined
MAX_DEVIATION_FACTOR = 3.0    # Readings > 3x neighbor avg are suspicious
MIN_NEIGHBORS = 1             # Need at least 1 neighbor for cross-validation


@dataclass
class ConfidenceResult:
    """Confidence scoring result for a single reading."""
    station_id: str
    pollutant: str
    observed_value: float
    neighbor_average: Optional[float]
    deviation_ratio: Optional[float]
    score: float  # 0–100
    is_quarantined: bool
    reason: Optional[str] = None

    def __str__(self) -> str:
        status = "QUARANTINED" if self.is_quarantined else "OK"
        return (
            f"[{status}] station={self.station_id} pollutant={self.pollutant} "
            f"value={self.observed_value:.1f} neighbor_avg={self.neighbor_average} "
            f"score={self.score:.1f}"
        )


def _compute_score(observed: float, neighbors: List[float]) -> tuple[float, Optional[float], Optional[float]]:
    """
    Compute a confidence score based on deviation from neighbor average.

    Returns:
        (score 0-100, neighbor_avg, deviation_ratio)
    """
    if not neighbors:
        # No neighbors — cannot cross-validate, assign neutral score
        return 70.0, None, None

    neighbor_avg = sum(neighbors) / len(neighbors)

    if neighbor_avg == 0:
        if observed == 0:
            return 100.0, 0.0, 1.0
        # Neighbor avg is zero but observed is not — very suspicious
        return 20.0, 0.0, float("inf")

    deviation_ratio = observed / neighbor_avg

    # Score calculation:
    # Ratio 0.5 – 2.0 → score 100 (within expected range)
    # Ratio approaches 0 or > 3 → score drops toward 0
    if 0.5 <= deviation_ratio <= 2.0:
        score = 100.0
    elif deviation_ratio > 2.0:
        # Penalize linearly beyond 2x
        excess = deviation_ratio - 2.0
        score = max(0.0, 100.0 - (excess / MAX_DEVIATION_FACTOR) * 80.0)
    else:
        # Below 0.5 is suspicious (instrument reading too low)
        deficit = 0.5 - deviation_ratio
        score = max(0.0, 100.0 - (deficit / 0.5) * 60.0)

    return round(score, 2), round(neighbor_avg, 4), round(deviation_ratio, 4)


def score_reading(
    station_id: str,
    pollutant: str,
    observed_value: float,
    neighbor_values: List[float],
) -> ConfidenceResult:
    """
    Score the confidence of a single pollutant reading.

    Args:
        station_id: The station this reading is for.
        pollutant: Pollutant name (e.g. 'pm25').
        observed_value: The reading value at this station.
        neighbor_values: List of values for the same pollutant
                         from nearby stations in the same time window.

    Returns:
        ConfidenceResult with score (0-100) and quarantine flag.
    """
    if not isinstance(observed_value, (int, float)) or math.isnan(observed_value):
        return ConfidenceResult(
            station_id=station_id,
            pollutant=pollutant,
            observed_value=float(observed_value) if observed_value else 0.0,
            neighbor_average=None,
            deviation_ratio=None,
            score=0.0,
            is_quarantined=True,
            reason="observed_value is not a valid number",
        )

    # Filter out invalid neighbor values
    valid_neighbors = [
        v for v in neighbor_values
        if isinstance(v, (int, float)) and not math.isnan(v) and v >= 0
    ]

    score, neighbor_avg, deviation_ratio = _compute_score(observed_value, valid_neighbors)

    is_quarantined = score < QUARANTINE_THRESHOLD
    reason = None
    if is_quarantined:
        if len(valid_neighbors) < MIN_NEIGHBORS:
            reason = "Insufficient neighbors for cross-validation"
        else:
            reason = f"Deviation ratio {deviation_ratio} indicates anomalous reading"

    result = ConfidenceResult(
        station_id=station_id,
        pollutant=pollutant,
        observed_value=observed_value,
        neighbor_average=neighbor_avg,
        deviation_ratio=deviation_ratio,
        score=score,
        is_quarantined=is_quarantined,
        reason=reason,
    )

    if is_quarantined:
        logger.warning("Reading quarantined: %s", result)
    else:
        logger.debug("Reading confidence: %s", result)

    return result


def score_all_pollutants(
    station_id: str,
    reading,
    neighbor_readings: List,
) -> dict[str, ConfidenceResult]:
    """
    Score all pollutants in a reading against neighbors.

    Args:
        station_id: This station's ID.
        reading: PollutantReading for this station.
        neighbor_readings: List of PollutantReadings from neighbor stations.

    Returns:
        Dict mapping pollutant_name → ConfidenceResult.
    """
    pollutants = ["pm25", "pm10", "no2", "so2", "co", "o3"]
    results = {}

    for poll in pollutants:
        value = getattr(reading, poll, None)
        if value is None:
            continue

        neighbor_vals = [
            getattr(nr, poll)
            for nr in neighbor_readings
            if getattr(nr, poll, None) is not None
        ]

        results[poll] = score_reading(station_id, poll, value, neighbor_vals)

    return results
