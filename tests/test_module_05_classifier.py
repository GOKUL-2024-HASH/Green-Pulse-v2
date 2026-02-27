"""
Tests for Module 06 — Tier Classifier.
"""
import pytest
from datetime import datetime, timezone, timedelta
from pipeline.classification.classifier import classify, classify_all_pollutants
from pipeline.streaming.pathway_engine import WindowResult


def _make_window_result(pollutant: str, hours: int, avg_value: float,
                         station_id: str = "DL001") -> WindowResult:
    now = datetime.now(timezone.utc)
    labels = {1: "1hr", 8: "8hr", 24: "24hr"}
    return WindowResult(
        station_id=station_id,
        pollutant=pollutant,
        window_hours=hours,
        window_label=labels.get(hours, f"{hours}hr"),
        average_value=avg_value,
        reading_count=hours * 6,  # ~10min intervals
        window_start=now - timedelta(hours=hours),
        window_end=now,
    )


class TestTier3Violation:
    def test_24hr_breach_triggers_violation(self):
        windows = [
            _make_window_result("pm25", 24, 70.0),  # Exceeds 60
            _make_window_result("pm25", 8, 65.0),
            _make_window_result("pm25", 1, 80.0),
        ]
        events = classify("DL001", "pm25", windows)
        violations = [e for e in events if e.tier == "VIOLATION"]
        assert len(violations) == 1
        assert violations[0].status == "PENDING_OFFICER_REVIEW"

    def test_24hr_within_limit_no_violation(self):
        windows = [
            _make_window_result("pm25", 24, 55.0),  # Under 60
            _make_window_result("pm25", 8, 55.0),
            _make_window_result("pm25", 1, 55.0),
        ]
        events = classify("DL001", "pm25", windows)
        violations = [e for e in events if e.tier == "VIOLATION"]
        assert len(violations) == 0


class TestTier2Flag:
    def test_8hr_breach_triggers_flag(self):
        windows = [
            _make_window_result("o3", 8, 110.0),   # O3 8hr limit=100
            _make_window_result("o3", 1, 110.0),
        ]
        events = classify("DL001", "o3", windows)
        flags = [e for e in events if e.tier == "FLAG"]
        assert len(flags) == 1
        assert flags[0].status == "FLAG"


class TestTier1Monitor:
    def test_1hr_breach_triggers_monitor(self):
        windows = [
            _make_window_result("o3", 1, 190.0),   # O3 1hr limit=180
        ]
        events = classify("DL001", "o3", windows)
        monitors = [e for e in events if e.tier == "MONITOR"]
        assert len(monitors) == 1
        assert monitors[0].status == "MONITOR"


class TestSimultaneousTiers:
    def test_all_three_tiers_trigger_simultaneously(self):
        """If 24hr, 8hr, AND 1hr are all in breach, all three tiers fire."""
        windows = [
            _make_window_result("pm25", 24, 75.0),  # VIOLATION (>60)
            _make_window_result("pm25", 8, 75.0),   # PM2.5 no 8hr limit (safe)
            _make_window_result("pm25", 1, 75.0),   # PM2.5 no 1hr limit (safe)
        ]
        events = classify("DL001", "pm25", windows)
        # Only VIOLATION should fire (PM2.5 only has 24hr and annual limits)
        assert any(e.tier == "VIOLATION" for e in events)

    def test_multi_pollutant_classification(self):
        all_windows = {
            "pm25": [_make_window_result("pm25", 24, 75.0)],
            "o3":   [
                _make_window_result("o3", 8, 110.0),
                _make_window_result("o3", 1, 190.0),
            ],
            "no2":  [_make_window_result("no2", 24, 30.0)],  # Under limit
        }
        result = classify_all_pollutants("DL001", all_windows)
        assert result.has_violation()   # PM2.5 24hr breach
        assert result.has_flag()        # O3 8hr breach
        assert any(e.pollutant == "no2" for e in result.events) is False  # No NO2 breach


class TestZoneAdjustment:
    def test_roadside_stricter_threshold(self):
        """Roadside zone factor 0.9 means limits are effectively 10% stricter."""
        # value=55, limit=60, adjusted limit effective = 60*0.9 = 54
        # So 55/0.9 = 61.1 > 60 → VIOLATION
        windows = [_make_window_result("pm25", 24, 55.0)]
        events = classify("DL001", "pm25", windows, zone="roadside")
        violations = [e for e in events if e.tier == "VIOLATION"]
        assert len(violations) == 1

    def test_residential_standard_threshold(self):
        windows = [_make_window_result("pm25", 24, 55.0)]
        events = classify("DL001", "pm25", windows, zone="residential")
        violations = [e for e in events if e.tier == "VIOLATION"]
        assert len(violations) == 0  # 55 < 60


class TestMetContext:
    def test_met_context_attached_to_event(self):
        met = {"temperature": 28.0, "humidity": 70.0}
        windows = [_make_window_result("pm25", 24, 75.0)]
        events = classify("DL001", "pm25", windows, met_context=met)
        assert events[0].met_context == met
