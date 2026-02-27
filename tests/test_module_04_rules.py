"""
Tests for Module 05 — Rule Engine.
Tests CPCB NAAQS 2009 limits for all 6 pollutants and all averaging periods.
"""
import pytest
from pipeline.rules.rule_engine import evaluate, get_limit


class TestRuleEngineLoads:
    def test_loads_without_error(self):
        """Config loads and returns a limit without error."""
        limit = get_limit("pm25", "24hr")
        assert limit is not None
        assert limit > 0


class TestPM25:
    def test_24hr_limit_is_60(self):
        """CRITICAL: PM2.5 24hr limit must be 60 (not 120)."""
        assert get_limit("pm25", "24hr") == 60.0

    def test_annual_limit_is_40(self):
        assert get_limit("pm25", "annual") == 40.0

    def test_within_24hr_limit(self):
        result = evaluate("pm25", "24hr", 55.0)
        assert result.within_limit is True
        assert result.exceedance_value == 0.0
        assert result.exceedance_percent == 0.0

    def test_at_24hr_limit(self):
        result = evaluate("pm25", "24hr", 60.0)
        assert result.within_limit is True  # Exactly at limit is OK

    def test_exceeding_24hr_limit(self):
        result = evaluate("pm25", "24hr", 61.0)
        assert result.within_limit is False
        assert result.exceedance_value == 1.0
        assert result.exceedance_percent > 0

    def test_1_unit_above_limit(self):
        result = evaluate("pm25", "24hr", 61.0)
        assert not result.within_limit
        assert abs(result.exceedance_value - 1.0) < 0.01

    def test_1_unit_below_limit(self):
        result = evaluate("pm25", "24hr", 59.0)
        assert result.within_limit


class TestPM10:
    def test_24hr_limit_is_100(self):
        assert get_limit("pm10", "24hr") == 100.0

    def test_annual_limit_is_60(self):
        assert get_limit("pm10", "annual") == 60.0

    def test_within_limit(self):
        result = evaluate("pm10", "24hr", 90.0)
        assert result.within_limit

    def test_exceeds_limit(self):
        result = evaluate("pm10", "24hr", 101.0)
        assert not result.within_limit


class TestNO2:
    def test_24hr_limit_is_80(self):
        assert get_limit("no2", "24hr") == 80.0

    def test_annual_limit_is_40(self):
        assert get_limit("no2", "annual") == 40.0

    def test_exceeds_limit(self):
        result = evaluate("no2", "24hr", 90.0)
        assert not result.within_limit
        assert result.legal_reference != ""


class TestSO2:
    def test_24hr_limit_is_80(self):
        assert get_limit("so2", "24hr") == 80.0

    def test_within_limit(self):
        result = evaluate("so2", "24hr", 79.9)
        assert result.within_limit


class TestO3:
    def test_8hr_limit_is_100(self):
        assert get_limit("o3", "8hr") == 100.0

    def test_1hr_limit_is_180(self):
        assert get_limit("o3", "1hr") == 180.0

    def test_no_24hr_limit(self):
        assert get_limit("o3", "24hr") is None

    def test_exceeds_8hr_limit(self):
        result = evaluate("o3", "8hr", 110.0)
        assert not result.within_limit


class TestCO:
    def test_8hr_limit_is_2_mg(self):
        assert get_limit("co", "8hr") == 2.0

    def test_1hr_limit_is_4_mg(self):
        assert get_limit("co", "1hr") == 4.0

    def test_exceeds_8hr(self):
        result = evaluate("co", "8hr", 2.5)
        assert not result.within_limit


class TestRuleResultFields:
    def test_rule_name_is_descriptive(self):
        result = evaluate("pm25", "24hr", 70.0)
        assert "PM25" in result.rule_name.upper() or "PM2.5" in result.rule_name

    def test_legal_reference_not_empty(self):
        result = evaluate("pm25", "24hr", 70.0)
        assert result.legal_reference != ""
        assert "CPCB" in result.legal_reference

    def test_exceedance_percent_correct(self):
        result = evaluate("pm25", "24hr", 120.0)
        # 120/60 - 1 = 100%
        assert abs(result.exceedance_percent - 100.0) < 0.01

    def test_unknown_period_raises(self):
        with pytest.raises(ValueError):
            evaluate("pm25", "99hr", 60.0)

    def test_unknown_pollutant_raises(self):
        with pytest.raises(ValueError):
            evaluate("benzene", "24hr", 60.0)
