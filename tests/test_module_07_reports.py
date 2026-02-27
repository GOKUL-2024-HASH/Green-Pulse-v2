"""
Tests for Module 08 — Report Generator.
Tests HTML rendering, template context building, and safe defaults.
"""
import pytest
import os
from reports.generator import generate_html, _build_context


MINIMAL_EVENT = {
    "pollutant": "pm25",
    "tier": "VIOLATION",
    "status": "PENDING_OFFICER_REVIEW",
    "observed_value": 85.0,
    "limit_value": 60.0,
    "exceedance_value": 25.0,
    "exceedance_percent": 41.67,
    "averaging_period": "24hr",
    "window_start": "2024-01-15 06:00 UTC",
    "window_end": "2024-01-16 06:00 UTC",
    "report_id": "TEST-001",
}

MINIMAL_STATION = {
    "station_id": "DL001",
    "name": "RK Puram, Delhi",
    "zone_type": "residential",
}


class TestHTMLGeneration:
    def test_generates_html(self):
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION)
        assert html is not None
        assert len(html) > 500

    def test_report_id_in_output(self):
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION)
        assert "TEST-001" in html

    def test_station_name_in_output(self):
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION)
        assert "RK Puram" in html

    def test_pollutant_in_output(self):
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION)
        assert "PM25" in html.upper() or "pm25" in html

    def test_violation_value_in_output(self):
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION)
        assert "85" in html
        assert "60" in html

    def test_cpcb_legal_reference_in_output(self):
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION, rule_result={
            "rule_name": "NAAQS PM2.5 24hr limit (60 μg/m³)",
            "legal_reference": "CPCB NAAQS 2009",
            "rule_version": "CPCB NAAQS 2009",
        })
        assert "CPCB" in html

    def test_officer_action_shown_when_present(self):
        action = {
            "action_type": "DISMISSED",
            "officer_name": "Ravi Kumar (Officer ID: 102)",
            "created_at": "2024-01-16 10:00 UTC",
            "reason": "Reading within sensor error margin",
        }
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION, officer_action=action)
        assert "DISMISSED" in html
        assert "Ravi Kumar" in html

    def test_no_officer_action_shows_placeholder(self):
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION, officer_action=None)
        assert "No officer action" in html

    def test_met_context_inversion_detection(self):
        met = {"temperature": 22.0, "humidity": 90.0, "wind_speed": 1.0}
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION, met_context=met)
        assert "Likely" in html  # Inversion likely

    def test_empty_readings_shows_placeholder(self):
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION, readings=[])
        assert "No readings available" in html

    def test_readings_listed_in_table(self):
        readings = [
            {"timestamp": "2024-01-16 05:00 UTC", "value": 90.0, "aqi": 165, "confidence": 92},
            {"timestamp": "2024-01-16 05:30 UTC", "value": 85.0, "aqi": 156, "confidence": 95},
        ]
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION, readings=readings)
        assert "90" in html
        assert "85" in html

    def test_html_writes_to_file(self, tmp_path):
        out = str(tmp_path / "test_report.html")
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION, output_path=out)
        assert os.path.exists(out)
        assert len(html) > 0

    def test_audit_hash_in_output(self):
        ledger_info = {
            "entry_hash": "a" * 64,
            "id": "ledger-entry-001",
            "sequence_number": 42,
            "chain_valid": True,
        }
        html = generate_html(MINIMAL_EVENT, MINIMAL_STATION, ledger_info=ledger_info)
        assert "a" * 16 in html  # Part of hash shown
        assert "VERIFIED" in html


class TestContextBuilding:
    def test_safe_defaults_all_none(self):
        ctx = _build_context(
            compliance_event={},
            station={},
            readings=[],
            rule_result={},
            met_context=None,
            sensor_info=None,
            officer_action=None,
            station_history=None,
            ledger_info=None,
        )
        assert ctx["station_id"] == "UNKNOWN"
        assert ctx["unit"] == "μg/m³"  # Default for pm25
        assert ctx["chain_valid"] is False

    def test_co_gets_mg_unit(self):
        ctx = _build_context(
            compliance_event={"pollutant": "co"},
            station={},
            readings=[], rule_result={}, met_context=None,
            sensor_info=None, officer_action=None,
            station_history=None, ledger_info=None,
        )
        assert ctx["unit"] == "mg/m³"
