"""
Report Generator — GreenPulse 2.0

Renders violation reports using Jinja2 templates.
Supports HTML and PDF (via WeasyPrint) output.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
REPORTS_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "generated")

# Ensure output directory exists
os.makedirs(REPORTS_OUTPUT_DIR, exist_ok=True)


def _jinja_env() -> Environment:
    """Create a Jinja2 environment pointing at the templates directory."""
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )


def _build_context(
    compliance_event: Dict[str, Any],
    station: Dict[str, Any],
    readings: List[Dict[str, Any]],
    rule_result: Dict[str, Any],
    met_context: Optional[Dict[str, Any]],
    sensor_info: Optional[Dict[str, Any]],
    officer_action: Optional[Dict[str, Any]],
    station_history: Optional[List[Dict[str, Any]]],
    ledger_info: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the full template context dict from component data.
    All fields have safe defaults to avoid Jinja2 UndefinedError.
    """
    pollutant = compliance_event.get("pollutant", "pm25")
    unit_map = {
        "pm25": "μg/m³", "pm10": "μg/m³", "no2": "μg/m³",
        "so2": "μg/m³", "o3": "μg/m³", "co": "mg/m³",
    }

    tier = compliance_event.get("tier", "MONITOR")
    status = compliance_event.get("status", "PENDING_OFFICER_REVIEW")

    # Met context — ensure is_inversion_likely is always present
    met = met_context or {}
    wind_speed = met.get("wind_speed")
    humidity = met.get("humidity")
    if wind_speed is not None and humidity is not None:
        met["is_inversion_likely"] = wind_speed < 2.0 and humidity > 80.0
    else:
        met["is_inversion_likely"] = False

    return {
        "report_id": compliance_event.get("report_id", str(uuid.uuid4())[:8].upper()),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "status": status,
        # Station
        "station_id": station.get("station_id", "UNKNOWN"),
        "station_name": station.get("name", "Unknown Station"),
        "station_zone": station.get("zone_type", "residential"),
        # Violation
        "pollutant": pollutant,
        "unit": unit_map.get(pollutant, "μg/m³"),
        "tier": tier,
        "observed_value": compliance_event.get("observed_value", 0.0),
        "limit_value": compliance_event.get("limit_value", 0.0),
        "exceedance_value": compliance_event.get("exceedance_value", 0.0),
        "exceedance_percent": compliance_event.get("exceedance_percent", 0.0),
        "averaging_period": compliance_event.get("averaging_period", "24hr"),
        "window_start": compliance_event.get("window_start", "—"),
        "window_end": compliance_event.get("window_end", "—"),
        # Readings
        "readings": readings or [],
        # Rule
        "rule_name": rule_result.get("rule_name", "CPCB NAAQS"),
        "legal_reference": rule_result.get("legal_reference", "CPCB NAAQS 2009"),
        "rule_version": rule_result.get("rule_version", "CPCB NAAQS 2009"),
        # Meteorological
        "met": met,
        # Sensor
        "sensor": sensor_info or {},
        # Officer
        "officer_action": officer_action,
        # History
        "station_history": station_history or [],
        # Audit ledger
        "ledger_hash": (ledger_info or {}).get("entry_hash", "—"),
        "ledger_entry_id": (ledger_info or {}).get("id", "—"),
        "ledger_sequence": (ledger_info or {}).get("sequence_number", "—"),
        "chain_valid": (ledger_info or {}).get("chain_valid", False),
    }


def generate_html(
    compliance_event: Dict[str, Any],
    station: Dict[str, Any],
    readings: Optional[List[Dict[str, Any]]] = None,
    rule_result: Optional[Dict[str, Any]] = None,
    met_context: Optional[Dict[str, Any]] = None,
    sensor_info: Optional[Dict[str, Any]] = None,
    officer_action: Optional[Dict[str, Any]] = None,
    station_history: Optional[List[Dict[str, Any]]] = None,
    ledger_info: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
) -> str:
    """
    Render the violation report as HTML.

    Args:
        compliance_event: Dict with violation details (tier, pollutant, values, etc.)
        station: Dict with station metadata.
        readings: List of recent reading dicts.
        rule_result: Dict from rule_engine with rule_name, legal_reference.
        met_context: Meteorological context dict.
        sensor_info: Sensor confidence info.
        officer_action: Officer action dict or None.
        station_history: List of historical summary dicts.
        ledger_info: Ledger entry dict (hash, id, sequence).
        output_path: Optional path to write HTML file.

    Returns:
        Rendered HTML string.
    """
    env = _jinja_env()
    template = env.get_template("violation_report.html")

    context = _build_context(
        compliance_event=compliance_event,
        station=station,
        readings=readings or [],
        rule_result=rule_result or {},
        met_context=met_context,
        sensor_info=sensor_info,
        officer_action=officer_action,
        station_history=station_history,
        ledger_info=ledger_info,
    )

    html = template.render(**context)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("HTML report written to %s", output_path)

    return html


def generate_pdf(
    compliance_event: Dict[str, Any],
    station: Dict[str, Any],
    output_path: Optional[str] = None,
    **kwargs,
) -> bytes:
    """
    Generate a PDF violation report using WeasyPrint.

    Falls back gracefully with a warning if WeasyPrint is not available.

    Args:
        compliance_event: See generate_html() for full args.
        station: Station metadata dict.
        output_path: Optional path to write PDF file.
        **kwargs: Passed through to generate_html().

    Returns:
        PDF bytes, or empty bytes if WeasyPrint unavailable.
    """
    html = generate_html(compliance_event, station, **kwargs)

    try:
        from weasyprint import HTML as WeasyHTML
        pdf_bytes = WeasyHTML(string=html, base_url=TEMPLATES_DIR).write_pdf()

        if output_path:
            with open(output_path, "wb") as f:
                f.write(pdf_bytes)
            logger.info("PDF report written to %s", output_path)

        return pdf_bytes

    except ImportError:
        logger.warning(
            "WeasyPrint not installed; PDF generation unavailable. "
            "Install with: pip install weasyprint"
        )
        return b""
