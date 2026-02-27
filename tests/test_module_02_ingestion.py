"""
Tests for Module 03 — Data Ingestion Pipeline.
Tests WAQI connector, weather connector, validator, and confidence scorer.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# ============================================================
# WAQI Connector Tests
# ============================================================
from pipeline.ingestion.waqi_connector import (
    PollutantReading, fetch_reading, _safe_float, _parse_iaqi, _parse_timestamp
)


class TestSafeFloat:
    def test_valid_number(self):
        assert _safe_float(42.5) == 42.5

    def test_string_number(self):
        assert _safe_float("42.5") == 42.5

    def test_dash_returns_none(self):
        assert _safe_float("-") is None

    def test_empty_string_returns_none(self):
        assert _safe_float("") is None

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_invalid_string_returns_none(self):
        assert _safe_float("not-a-number") is None


class TestParseIaqi:
    def test_parses_pollutants(self):
        data = {
            "iaqi": {
                "pm25": {"v": 85.3},
                "pm10": {"v": 120.0},
                "no2": {"v": 45.5},
                "so2": {"v": 10.0},
                "co": {"v": 1.5},
                "o3": {"v": 55.0},
            }
        }
        result = _parse_iaqi(data)
        assert result["pm25"] == 85.3
        assert result["pm10"] == 120.0
        assert result["no2"] == 45.5
        assert result["so2"] == 10.0
        assert result["co"] == 1.5
        assert result["o3"] == 55.0

    def test_parses_meteorology(self):
        data = {
            "iaqi": {
                "t": {"v": 28.5},
                "h": {"v": 72.0},
                "w": {"v": 3.2},
                "p": {"v": 1010.0},
            }
        }
        result = _parse_iaqi(data)
        assert result["temperature"] == 28.5
        assert result["humidity"] == 72.0
        assert result["wind_speed"] == 3.2
        assert result["pressure"] == 1010.0

    def test_missing_iaqi_is_empty(self):
        assert _parse_iaqi({}) == {}

    def test_dash_value_is_none(self):
        data = {"iaqi": {"pm25": {"v": "-"}}}
        result = _parse_iaqi(data)
        assert result.get("pm25") is None


class TestParseTimestamp:
    def test_parses_iso_timestamp(self):
        block = {"iso": "2024-01-15T10:30:00+05:30"}
        dt = _parse_timestamp(block)
        assert isinstance(dt, datetime)
        assert dt.tzinfo is not None

    def test_fallback_on_empty(self):
        dt = _parse_timestamp({})
        assert isinstance(dt, datetime)


class TestFetchReading:
    def _make_mock_response(self, data: dict):
        mock = MagicMock()
        mock.json.return_value = data
        mock.raise_for_status = MagicMock()
        return mock

    def test_happy_path(self):
        payload = {
            "status": "ok",
            "data": {
                "idx": 7024,
                "aqi": 156,
                "time": {"iso": "2024-01-15T10:00:00+00:00"},
                "city": {"name": "RK Puram, Delhi"},
                "iaqi": {
                    "pm25": {"v": 85.3},
                    "pm10": {"v": 120.0},
                    "no2": {"v": 45.0},
                    "t": {"v": 22.0},
                    "h": {"v": 65.0},
                    "w": {"v": 2.1},
                }
            }
        }
        with patch("pipeline.ingestion.waqi_connector.httpx.get") as mock_get:
            with patch.dict("os.environ", {"WAQI_TOKEN": "test_token"}):
                mock_get.return_value = self._make_mock_response(payload)
                reading = fetch_reading("7024", "DL001")
        assert reading is not None
        assert reading.station_id == "DL001"
        assert reading.pm25 == 85.3
        assert reading.aqi == 156

    def test_missing_token_returns_none(self):
        with patch.dict("os.environ", {"WAQI_TOKEN": ""}, clear=False):
            import pipeline.ingestion.waqi_connector as waqimod
            waqimod.os.environ["WAQI_TOKEN"] = ""
            reading = fetch_reading("7024", "DL001")
        # Should return None since no token
        # (connector will log error and return None)

    def test_api_status_not_ok_returns_none(self):
        payload = {"status": "error", "data": "Invalid key"}
        with patch("pipeline.ingestion.waqi_connector.httpx.get") as mock_get:
            with patch.dict("os.environ", {"WAQI_TOKEN": "test_token"}):
                mock_get.return_value = self._make_mock_response(payload)
                reading = fetch_reading("7024", "DL001")
        assert reading is None

    def test_malformed_json_returns_none(self):
        import httpx
        with patch("pipeline.ingestion.waqi_connector.httpx.get") as mock_get:
            with patch.dict("os.environ", {"WAQI_TOKEN": "test_token"}):
                mock_resp = MagicMock()
                mock_resp.json.side_effect = ValueError("bad json")
                mock_resp.raise_for_status = MagicMock()
                mock_get.return_value = mock_resp
                reading = fetch_reading("7024", "DL001")
        assert reading is None

    def test_timeout_returns_none(self):
        import httpx
        with patch("pipeline.ingestion.waqi_connector.httpx.get") as mock_get:
            with patch.dict("os.environ", {"WAQI_TOKEN": "test_token"}):
                mock_get.side_effect = httpx.TimeoutException("Timeout")
                reading = fetch_reading("7024", "DL001")
        assert reading is None

    def test_missing_data_field_returns_none(self):
        payload = {"status": "ok"}  # 'data' key missing
        with patch("pipeline.ingestion.waqi_connector.httpx.get") as mock_get:
            with patch.dict("os.environ", {"WAQI_TOKEN": "test_token"}):
                mock_get.return_value = self._make_mock_response(payload)
                reading = fetch_reading("7024", "DL001")
        assert reading is None


# ============================================================
# Validator Tests
# ============================================================
from pipeline.ingestion.validator import validate_reading, ValidationResult


def _make_reading(**kwargs):
    """Helper to create a minimal valid reading-like object."""
    class FakeReading:
        station_id = "DL001"
        timestamp = datetime.now(timezone.utc) - timedelta(minutes=30)
        pm25 = 55.0
        pm10 = None
        no2 = None
        so2 = None
        co = None
        o3 = None
        temperature = 25.0
        humidity = 60.0
        wind_speed = 3.0
        wind_direction = 180.0
        pressure = 1010.0
        dew_point = None
    r = FakeReading()
    for k, v in kwargs.items():
        setattr(r, k, v)
    return r


class TestValidator:
    def test_valid_reading_passes(self):
        r = _make_reading()
        result = validate_reading(r)
        assert result.is_valid is True

    def test_missing_station_id_fails(self):
        r = _make_reading(station_id=None)
        result = validate_reading(r)
        assert result.is_valid is False
        assert any("station_id" in msg for msg in result.reasons)

    def test_no_pollutants_fails(self):
        r = _make_reading(pm25=None)
        result = validate_reading(r)
        assert result.is_valid is False
        assert any("No pollutant" in msg for msg in result.reasons)

    def test_pm25_negative_fails(self):
        r = _make_reading(pm25=-5.0)
        result = validate_reading(r)
        assert result.is_valid is False
        assert any("pm25" in msg for msg in result.reasons)

    def test_pm25_above_max_fails(self):
        r = _make_reading(pm25=9999.0)
        result = validate_reading(r)
        assert result.is_valid is False

    def test_stale_timestamp_fails(self):
        r = _make_reading(timestamp=datetime.now(timezone.utc) - timedelta(hours=5))
        result = validate_reading(r)
        assert result.is_valid is False
        assert any("old" in msg for msg in result.reasons)

    def test_future_timestamp_fails(self):
        r = _make_reading(timestamp=datetime.now(timezone.utc) + timedelta(hours=1))
        result = validate_reading(r)
        assert result.is_valid is False

    def test_boundary_values_pass(self):
        """Exact boundary values should be valid."""
        r = _make_reading(pm25=0.0)
        assert validate_reading(r).is_valid is True
        r = _make_reading(pm25=1000.0)
        assert validate_reading(r).is_valid is True

    def test_just_above_limit_fails(self):
        r = _make_reading(pm25=1000.1)
        result = validate_reading(r)
        assert result.is_valid is False


# ============================================================
# Confidence Scorer Tests
# ============================================================
from pipeline.confidence.scorer import score_reading, score_all_pollutants, QUARANTINE_THRESHOLD


class TestConfidenceScorer:
    def test_perfect_match_is_100(self):
        result = score_reading("DL001", "pm25", 80.0, [80.0, 80.0, 80.0])
        assert result.score == 100.0
        assert result.is_quarantined is False

    def test_within_range_not_quarantined(self):
        # 1.5x neighbor avg — should still score 100
        result = score_reading("DL001", "pm25", 120.0, [80.0, 80.0])
        assert result.score == 100.0

    def test_extreme_outlier_is_quarantined(self):
        # 10x neighbor avg — definitely suspicious
        result = score_reading("DL001", "pm25", 800.0, [80.0, 80.0])
        assert result.is_quarantined is True
        assert result.score < QUARANTINE_THRESHOLD

    def test_no_neighbors_gives_neutral_score(self):
        result = score_reading("DL001", "pm25", 80.0, [])
        assert result.score == 70.0
        assert result.is_quarantined is False  # 70 > 60

    def test_zero_value_with_zero_neighbors_is_100(self):
        result = score_reading("DL001", "pm25", 0.0, [0.0, 0.0])
        assert result.score == 100.0

    def test_nonzero_value_with_zero_neighbors_is_quarantined(self):
        result = score_reading("DL001", "pm25", 80.0, [0.0, 0.0])
        assert result.is_quarantined is True

    def test_score_all_pollutants(self):
        class FakeReading:
            station_id = "DL001"
            pm25 = 80.0
            pm10 = 120.0
            no2 = 40.0
            so2 = 20.0
            co = 1.0
            o3 = 55.0

        class NeighborReading:
            station_id = "DL002"
            pm25 = 75.0
            pm10 = 115.0
            no2 = 38.0
            so2 = 18.0
            co = 0.9
            o3 = 50.0

        results = score_all_pollutants("DL001", FakeReading(), [NeighborReading()])
        assert "pm25" in results
        assert results["pm25"].score >= 80.0  # Close to neighbor, high confidence


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call(["pytest", __file__, "-v"]))
