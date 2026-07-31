from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from src.domain.weather import (
    CityForecast,
    CurrentForecast,
    DailyForecast,
    WeatherClient,
)


BASE_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODING_BASE_URL = "https://geocoding-api.open-meteo.com/v1/search"


class WeatherApiError(RuntimeError):
    """Raised when the weather provider cannot return a usable forecast."""


class OpenMeteoWeatherClient(WeatherClient):

    def __init__(
        self,
        *,
        base_url: str = BASE_URL,
        geocoding_base_url: str = GEOCODING_BASE_URL,
        timeout: float = 10.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url
        self._geocoding_base_url = geocoding_base_url
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> OpenMeteoWeatherClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def get_city_forecast(
        self,
        *,
        city: str,
        language: str = "en",
    ) -> CityForecast:
        city = city.strip()
        if not city:
            raise ValueError("city must not be empty")

        params = {
            "name": city,
            "count": 1,
            "language": language,
            "format": "json",
        }
        payload = await self._get_payload(
            self._geocoding_base_url,
            params,
        )
        city_forecast = payload.get("results")

        if not isinstance(city_forecast, list) or not city_forecast:
            raise WeatherApiError(f"Location not found: {city}")

        first = city_forecast[0]
        if not isinstance(first, Mapping):
            raise WeatherApiError("Geocoding API returned an unexpected location")

        return self._parse_city_forecast(first)

    async def get_current_forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        timezone: str = "auto",
    ) -> CurrentForecast:
        self._validate_coordinates(latitude, longitude)

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(
                (
                    "temperature_2m",
                    "apparent_temperature",
                    "relative_humidity_2m",
                    "weather_code",
                    "wind_speed_10m",
                )
            ),
            "timezone": timezone,
            "wind_speed_unit": "ms",
            "temperature_unit": "celsius",
        }

        payload = await self._get_payload(self._base_url, params)
        current = payload.get("current")

        if not isinstance(current, Mapping):
            raise WeatherApiError("Weather API misses current forecast")

        return self._parse_current(current)

    async def get_daily_forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        forecast_days: int = 3,
        timezone: str = "auto",
    ) -> list[DailyForecast]:
        self._validate_coordinates(latitude, longitude)

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(
                (
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                )
            ),
            "forecast_days": self._normalize_forecast_days(forecast_days),
            "timezone": timezone,
            "wind_speed_unit": "ms",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
        }

        payload = await self._get_payload(self._base_url, params)
        daily = payload.get("daily")

        if not isinstance(daily, Mapping):
            raise WeatherApiError("Weather API misses daily forecast")

        return self._parse_daily(daily)

    async def _get_payload(
        self,
        url: str,
        params: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise WeatherApiError(
                f"Weather API returned HTTP {exc.response.status_code}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise WeatherApiError("Weather API request failed") from exc

        if not isinstance(payload, Mapping):
            raise WeatherApiError("Weather API returned an unexpected payload")

        if payload.get("error"):
            reason = payload.get("reason", "unknown reason")
            raise WeatherApiError(f"Weather API error: {reason}")

        return payload

    @staticmethod
    def _validate_coordinates(latitude: float, longitude: float) -> None:
        if not -90 <= latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")

    @staticmethod
    def _normalize_forecast_days(forecast_days: int) -> int:
        if not 1 <= forecast_days <= 16:
            raise ValueError("forecast_days must be between 1 and 16")
        return forecast_days

    def _parse_current(self, current: Mapping[str, Any]) -> CurrentForecast:
        weather_code = int(current["weather_code"])

        return CurrentForecast(
            time=str(current["time"]),
            temperature=float(current["temperature_2m"]),
            apparent_temperature=float(current["apparent_temperature"]),
            relative_humidity=int(current["relative_humidity_2m"]),
            wind_speed=float(current["wind_speed_10m"]),
            weather_code=weather_code,
            description=describe_weather_code(weather_code),
        )

    def _parse_daily(self, daily: Mapping[str, Any]) -> list[DailyForecast]:
        if (
            len(daily["weather_code"]) != len(daily["time"])
            or len(daily["temperature_2m_min"]) != len(daily["time"])
            or len(daily["temperature_2m_max"]) != len(daily["time"])
            or len(daily["precipitation_sum"]) != len(daily["time"])
            or len(daily["wind_speed_10m_max"]) != len(daily["time"])
        ):
            raise WeatherApiError("Weather API returned uneven daily arrays")

        forecast: list[DailyForecast] = []
        for index, date in enumerate(daily["time"]):
            weather_code = int(daily["weather_code"][index])
            forecast.append(
                DailyForecast(
                    date=str(date),
                    temperature_min=float(daily["temperature_2m_min"][index]),
                    temperature_max=float(daily["temperature_2m_max"][index]),
                    precipitation_sum=float(daily["precipitation_sum"][index]),
                    wind_speed_max=float(daily["wind_speed_10m_max"][index]),
                    weather_code=weather_code,
                    description=describe_weather_code(weather_code),
                )
            )

        return forecast

    def _parse_city_forecast(self, location: Mapping[str, Any]) -> CityForecast:
        return CityForecast(
            name=str(location["name"]),
            latitude=float(location["latitude"]),
            longitude=float(location["longitude"]),
        )


def describe_weather_code(code: int) -> str:
    return _WEATHER_CODE_DESCRIPTIONS.get(code, f"unknown weather code {code}")


def create_weather_client() -> WeatherClient:
    return OpenMeteoWeatherClient()


_WEATHER_CODE_DESCRIPTIONS = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snow fall",
    73: "moderate snow fall",
    75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}
