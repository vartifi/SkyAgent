from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict
from typing import Any

from src.domain.weather import (
    CityForecast,
    CurrentForecast,
    DailyForecast,
    WeatherClientFactory,
    WeatherSettings,
)
from src.infrastructure.settings import weather_settings_from_env
from src.infrastructure.weather import WeatherApiError, create_weather_client


def create_weather_tools(
    weather_settings: WeatherSettings | None = None,
    *,
    client_factory: WeatherClientFactory | None = None,
) -> Sequence[Callable[..., Any]]:
    weather_settings = weather_settings or weather_settings_from_env()
    client_factory = client_factory or create_weather_client

    async def get_current_weather_by_city(
        city: str,
        language: str = "en",
    ) -> str:
        """Get the current weather for a city name."""
        try:
            async with client_factory() as client:
                location = await client.get_city_forecast(
                    city=city,
                    language=language,
                )
                current = await client.get_current_forecast(
                    latitude=location.latitude,
                    longitude=location.longitude,
                    timezone=weather_settings.weather_timezone,
                )
        except (ValueError, WeatherApiError) as exc:
            return f"Weather lookup failed: {exc}"

        return "\n".join(
            (
                f"Location: {_format_location(location)}.",
                format_current_forecast(
                    current,
                    latitude=location.latitude,
                    longitude=location.longitude,
                ),
            )
        )

    async def get_daily_weather_by_city(
        city: str,
        forecast_days: int | None = None,
        language: str = "ru",
    ) -> str:
        """Get a daily weather forecast for a city name."""
        try:
            async with client_factory() as client:
                location = await client.get_city_forecast(
                    city=city,
                    language=language,
                )
                daily = await client.get_daily_forecast(
                    latitude=location.latitude,
                    longitude=location.longitude,
                    forecast_days=(
                        forecast_days or weather_settings.weather_forecast_days
                    ),
                    timezone=weather_settings.weather_timezone,
                )
        except (ValueError, WeatherApiError) as exc:
            return f"Weather lookup failed: {exc}"

        return "\n\n".join(
            (
                f"Location: {_format_location(location)}.",
                format_daily_forecast(
                    daily,
                    latitude=location.latitude,
                    longitude=location.longitude,
                ),
            )
        )

    return (
        get_current_weather_by_city,
        get_daily_weather_by_city,
    )


def format_current_forecast(
    forecast: CurrentForecast,
    *,
    latitude: float,
    longitude: float,
) -> str:
    payload = asdict(forecast)
    return (
        f"Current weather for {latitude:.4f}, {longitude:.4f}: "
        f"{payload['description']} at {payload['time']}. "
        f"Temperature {payload['temperature']:.1f} C, feels like "
        f"{payload['apparent_temperature']:.1f} C, humidity "
        f"{payload['relative_humidity']}%, wind {payload['wind_speed']:.1f} m/s."
    )


def format_daily_forecast(
    forecast: Sequence[DailyForecast],
    *,
    latitude: float,
    longitude: float,
) -> str:
    if not forecast:
        return f"Daily forecast for {latitude:.4f}, {longitude:.4f}: no days returned."

    rows = [
        f"Daily forecast for {latitude:.4f}, {longitude:.4f}:",
    ]
    for day in forecast:
        payload = asdict(day)
        rows.append(
            "- "
            f"{payload['date']}: {payload['description']}, "
            f"{payload['temperature_min']:.1f}.."
            f"{payload['temperature_max']:.1f} C, "
            f"precipitation {payload['precipitation_sum']:.1f} mm, "
            f"max wind {payload['wind_speed_max']:.1f} m/s."
        )

    return "\n".join(rows)


def _format_location(location: CityForecast) -> str:
    return location.name
