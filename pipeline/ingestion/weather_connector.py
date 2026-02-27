"""
OpenWeatherMap API Connector.

Fetches current weather context for a given location (lat/lon).
Returns WeatherContext dataclass or None on any failure.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OWM_BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
REQUEST_TIMEOUT = 10  # seconds


@dataclass
class WeatherContext:
    """Meteorological context from OpenWeatherMap."""
    latitude: float
    longitude: float
    timestamp: datetime
    temperature: Optional[float] = None     # °C
    feels_like: Optional[float] = None      # °C
    humidity: Optional[float] = None        # %
    pressure: Optional[float] = None        # hPa
    wind_speed: Optional[float] = None      # m/s
    wind_direction: Optional[float] = None  # degrees
    wind_gust: Optional[float] = None       # m/s
    visibility: Optional[float] = None      # metres
    cloud_cover: Optional[int] = None       # %
    weather_description: Optional[str] = None
    is_inversion_likely: bool = False       # Temp inversion heuristic


def _check_inversion(temp: Optional[float], humidity: Optional[float],
                     wind_speed: Optional[float]) -> bool:
    """
    Simple heuristic: temperature inversion likely when
    - wind speed < 2 m/s AND humidity > 80%
    These conditions trap pollutants near ground level.
    """
    if temp is None or humidity is None or wind_speed is None:
        return False
    return wind_speed < 2.0 and humidity > 80.0


def fetch_weather(latitude: float, longitude: float) -> Optional[WeatherContext]:
    """
    Fetch current weather for the given coordinates.

    Args:
        latitude: Station latitude
        longitude: Station longitude

    Returns:
        WeatherContext or None on failure.
    """
    api_key = os.getenv("OPENWEATHERMAP_KEY", "")
    if not api_key:
        logger.error("OPENWEATHERMAP_KEY not set in environment")
        return None

    params = {
        "lat": latitude,
        "lon": longitude,
        "appid": api_key,
        "units": "metric",  # Celsius, m/s
    }

    try:
        resp = httpx.get(OWM_BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except httpx.TimeoutException:
        logger.error("OpenWeatherMap request timed out for %.4f,%.4f", latitude, longitude)
        return None
    except httpx.HTTPStatusError as e:
        logger.error("OpenWeatherMap HTTP error %s", e.response.status_code)
        return None
    except httpx.RequestError as e:
        logger.error("OpenWeatherMap network error: %s", e)
        return None

    try:
        data = resp.json()
    except Exception:
        logger.error("OpenWeatherMap returned malformed JSON")
        return None

    try:
        main = data.get("main", {})
        wind = data.get("wind", {})
        clouds = data.get("clouds", {})
        weather_list = data.get("weather", [{}])
        description = weather_list[0].get("description") if weather_list else None

        temp = main.get("temp")
        humidity = main.get("humidity")
        wind_speed = wind.get("speed")

        ctx = WeatherContext(
            latitude=latitude,
            longitude=longitude,
            timestamp=datetime.fromtimestamp(data.get("dt", 0), tz=timezone.utc),
            temperature=temp,
            feels_like=main.get("feels_like"),
            humidity=humidity,
            pressure=main.get("pressure"),
            wind_speed=wind_speed,
            wind_direction=wind.get("deg"),
            wind_gust=wind.get("gust"),
            visibility=data.get("visibility"),
            cloud_cover=clouds.get("all"),
            weather_description=description,
            is_inversion_likely=_check_inversion(temp, humidity, wind_speed),
        )

        logger.info(
            "Weather fetched for %.4f,%.4f: T=%.1f°C, Wind=%.1fm/s, Humidity=%s%%",
            latitude, longitude,
            ctx.temperature or 0,
            ctx.wind_speed or 0,
            ctx.humidity or 0,
        )
        return ctx

    except (KeyError, TypeError, IndexError) as e:
        logger.error("OpenWeatherMap response parse error: %s", e)
        return None
