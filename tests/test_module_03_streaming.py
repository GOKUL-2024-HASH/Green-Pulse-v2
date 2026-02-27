"""
Tests for Module 04 - Pathway Streaming Engine (Rolling Windows).
"""
import pytest
from datetime import datetime, timezone, timedelta
from pipeline.streaming.pathway_engine import RollingWindowEngine, WindowResult


def _make_reading(pm25: float, timestamp: datetime, station_id: str = "DL001"):
    class FakeReading:
        pass
    r = FakeReading()
    r.pm25 = pm25
    r.pm10 = None
    r.no2 = None
    r.so2 = None
    r.co = None
    r.o3 = None
    r.temperature = 25.0
    r.humidity = 60.0
    r.wind_speed = 3.0
    r.wind_direction = 180.0
    r.pressure = 1010.0
    r.dew_point = None
    r.timestamp = timestamp
    return r


class TestRollingWindowEngine:
    def test_single_reading_produces_window_results(self):
        engine = RollingWindowEngine()
        now = datetime.now(timezone.utc)
        reading = _make_reading(80.0, now)
        results = engine.update("DL001", reading)
        assert "pm25" in results
        # With one reading, all windows should show that reading
        for wr in results["pm25"]:
            assert wr.average_value == 80.0
            assert wr.reading_count == 1

    def test_multiple_readings_average_correctly(self):
        engine = RollingWindowEngine()
        now = datetime.now(timezone.utc)
        values = [60.0, 80.0, 100.0]
        for i, val in enumerate(values):
            ts = now - timedelta(minutes=30 - i * 10)
            engine.update("DL001", _make_reading(val, ts))
        # Check 1hr window
        results = engine.get_current_averages("DL001", "pm25", now)
        one_hr_results = [r for r in results if r.window_hours == 1]
        assert len(one_hr_results) == 1
        assert abs(one_hr_results[0].average_value - 80.0) < 0.01  # mean of 60, 80, 100

    def test_readings_expire_from_window(self):
        engine = RollingWindowEngine()
        now = datetime.now(timezone.utc)
        # Add an old reading (2 hours ago — outside 1hr window)
        old_ts = now - timedelta(hours=2, minutes=1)
        engine.update("DL001", _make_reading(999.0, old_ts))
        # Add a fresh reading
        engine.update("DL001", _make_reading(50.0, now))
        results = engine.get_current_averages("DL001", "pm25", now)
        one_hr_results = [r for r in results if r.window_hours == 1]
        assert one_hr_results[0].average_value == 50.0  # Old reading expired

    def test_24hr_window_includes_all_day_readings(self):
        engine = RollingWindowEngine()
        now = datetime.now(timezone.utc)
        for i in range(24):
            ts = now - timedelta(hours=23 - i)
            engine.update("DL001", _make_reading(float(i + 1), ts))
        results = engine.get_current_averages("DL001", "pm25", now)
        day_results = [r for r in results if r.window_hours == 24]
        assert day_results[0].reading_count == 24

    def test_multiple_stations_independent(self):
        engine = RollingWindowEngine()
        now = datetime.now(timezone.utc)
        engine.update("DL001", _make_reading(100.0, now))
        engine.update("DL002", _make_reading(50.0, now))
        r1 = engine.get_current_averages("DL001", "pm25", now)
        r2 = engine.get_current_averages("DL002", "pm25", now)
        assert r1[0].average_value == 100.0
        assert r2[0].average_value == 50.0

    def test_offline_station_retains_buffer(self):
        engine = RollingWindowEngine()
        now = datetime.now(timezone.utc)
        engine.update("DL001", _make_reading(80.0, now))
        engine.mark_station_offline("DL001")
        results = engine.get_current_averages("DL001", "pm25", now)
        # Buffer should still have the reading
        assert len(results) > 0

    def test_partial_window_still_returns_result(self):
        engine = RollingWindowEngine()
        # Single reading - partial window is OK
        now = datetime.now(timezone.utc)
        engine.update("DL001", _make_reading(75.0, now))
        results = engine.get_current_averages("DL001", "pm25", now)
        assert all(r.reading_count >= 1 for r in results)
