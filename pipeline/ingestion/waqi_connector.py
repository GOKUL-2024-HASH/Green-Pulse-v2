"""
WAQI (World Air Quality Index) API Connector.

Fetches real-time pollutant readings for a given city/station.
Handles API timeouts, malformed responses, and missing fields gracefully.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

WAQI_BASE_URL = "https://api.waqi.info/feed"
REQUEST_TIMEOUT = 10  # seconds


@dataclass
class PollutantReading:
    """Typed container for a single pollutant observation from a station."""
    station_id: str
    station_name: str
    timestamp: datetime
    # Pollutants (μg/m³ unless noted)
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    no2: Optional[float] = None
    so2: Optional[float] = None
    co: Optional[float] = None   # mg/m³
    o3: Optional[float] = None
    # Meteorological context
    temperature: Optional[float] = None    # °C
    humidity: Optional[float] = None       # %
    wind_speed: Optional[float] = None     # m/s
    wind_direction: Optional[float] = None # degrees
    pressure: Optional[float] = None       # hPa
    dew_point: Optional[float] = None      # °C
    # Source metadata
    aqi: Optional[int] = None
    source_url: str = ""


def _safe_float(val) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if val is None or val == "-" or val == "":
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _parse_iaqi(data: dict) -> dict:
    """Extract individual AQI pollutant values from the WAQI iaqi block."""
    iaqi = data.get("iaqi", {})
    result = {}
    mapping = {
        "pm25": "pm25",
        "pm10": "pm10",
        "no2": "no2",
        "so2": "so2",
        "co": "co",
        "o3": "o3",
        "t": "temperature",
        "h": "humidity",
        "w": "wind_speed",
        "wd": "wind_direction",
        "p": "pressure",
        "dew": "dew_point",
    }
    for waqi_key, field_name in mapping.items():
        if waqi_key in iaqi:
            result[field_name] = _safe_float(iaqi[waqi_key].get("v"))
    return result


def _parse_timestamp(time_block: dict) -> datetime:
    """Parse the 'time' block from WAQI response into a UTC datetime."""
    try:
        iso_str = time_block.get("iso", "")
        if iso_str:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        pass
    return datetime.now(timezone.utc)


def fetch_reading(station_waqi_id: str, station_id: str) -> Optional[PollutantReading]:
    """
    Fetch the latest reading for the given WAQI station ID.

    Args:
        station_waqi_id: The WAQI station numeric ID (e.g. "7024")
        station_id: Internal GreenPulse station ID (e.g. "DL001")

    Returns:
        PollutantReading dataclass or None on failure.
    """
    token = os.getenv("WAQI_TOKEN", "")
    if not token:
        logger.error("WAQI_TOKEN not set in environment")
        return None

    url = f"{WAQI_BASE_URL}/@{station_waqi_id}/?token={token}"

    try:
        resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except httpx.TimeoutException:
        logger.error("WAQI request timed out for station %s", station_waqi_id)
        return None
    except httpx.HTTPStatusError as e:
        logger.error("WAQI HTTP error %s for station %s", e.response.status_code, station_waqi_id)
        return None
    except httpx.RequestError as e:
        logger.error("WAQI network error for station %s: %s", station_waqi_id, e)
        return None

    try:
        payload = resp.json()
    except Exception:
        logger.error("WAQI returned malformed JSON for station %s", station_waqi_id)
        return None

    if payload.get("status") != "ok":
        logger.error(
            "WAQI status not ok for station %s: %s",
            station_waqi_id, payload.get("status")
        )
        return None

    try:
        data = payload["data"]
    except (KeyError, TypeError):
        logger.error("WAQI response missing 'data' for station %s", station_waqi_id)
        return None

    # Parse timestamp
    time_block = data.get("time", {})
    timestamp = _parse_timestamp(time_block)

    # Parse pollutants and meteorology
    fields = _parse_iaqi(data)

    # Parse city/station name
    city_block = data.get("city", {})
    station_name = city_block.get("name", station_id)

    aqi_raw = data.get("aqi")
    try:
        aqi = int(aqi_raw) if aqi_raw not in (None, "-") else None
    except (ValueError, TypeError):
        aqi = None

    reading = PollutantReading(
        station_id=station_id,
        station_name=station_name,
        timestamp=timestamp,
        pm25=fields.get("pm25"),
        pm10=fields.get("pm10"),
        no2=fields.get("no2"),
        so2=fields.get("so2"),
        co=fields.get("co"),
        o3=fields.get("o3"),
        temperature=fields.get("temperature"),
        humidity=fields.get("humidity"),
        wind_speed=fields.get("wind_speed"),
        wind_direction=fields.get("wind_direction"),
        pressure=fields.get("pressure"),
        dew_point=fields.get("dew_point"),
        aqi=aqi,
        source_url=url,
    )

    logger.info(
        "WAQI reading fetched for station %s: PM2.5=%.1f, AQI=%s",
        station_id,
        reading.pm25 or 0,
        reading.aqi
    )
    return reading


def fetch_reading_by_city(city: str, station_id: str) -> Optional[PollutantReading]:
    """
    Fetch the latest reading for a named city (e.g. 'delhi').
    Wraps fetch_reading using the city-name endpoint.
    """
    token = os.getenv("WAQI_TOKEN", "")
    if not token:
        logger.error("WAQI_TOKEN not set")
        return None

    url = f"{WAQI_BASE_URL}/{city}/?token={token}"

    try:
        resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except httpx.TimeoutException:
        logger.error("WAQI city request timed out for %s", city)
        return None
    except httpx.RequestError as e:
        logger.error("WAQI city request error for %s: %s", city, e)
        return None

    try:
        payload = resp.json()
    except Exception:
        logger.error("WAQI city malformed JSON for %s", city)
        return None

    if payload.get("status") != "ok":
        logger.warning("WAQI city %s status: %s", city, payload.get("status"))
        return None

    data = payload.get("data", {})
    waqi_id = str(data.get("idx", ""))
    if waqi_id:
        return fetch_reading(waqi_id, station_id)
    return None
