from __future__ import annotations

import asyncio
from collections.abc import Callable

import httpx
import pytest

from src.domain.weather import CityForecast, CurrentForecast, DailyForecast
from src.infrastructure.weather import (
    OpenMeteoWeatherClient,
    WeatherApiError,
    create_weather_client,
    describe_weather_code,
)


Handler = Callable[[httpx.Request], httpx.Response]


def test_get_current_forecast() -> None:
    request_params: httpx.QueryParams | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_params
        request_params = request.url.params
        return httpx.Response(200, json=_current_payload())

    current = asyncio.run(_get_current(handler))

    assert request_params is not None
    assert "current" in request_params
    assert "daily" not in request_params
    assert current.time == "2026-07-31T14:00"
    assert current.temperature == 25.1
    assert current.relative_humidity == 47
    assert current.wind_speed == 3.7
    assert current.description == "mainly clear"


def test_get_daily_forecast() -> None:
    request_params: httpx.QueryParams | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_params
        request_params = request.url.params
        return httpx.Response(200, json=_daily_payload())

    daily = asyncio.run(_get_daily(handler, forecast_days=2))

    assert request_params is not None
    assert "daily" in request_params
    assert "current" not in request_params
    assert request_params["forecast_days"] == "2"
    assert len(daily) == 2
    assert daily[0].date == "2026-07-31"
    assert daily[0].temperature_min == 16.2
    assert daily[0].temperature_max == 25.6
    assert daily[1].description == "slight rain showers"
    assert daily[1].precipitation_sum == 0.4


def test_get_city_forecast() -> None:
    request_params: httpx.QueryParams | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_params
        request_params = request.url.params
        return httpx.Response(200, json=_geocoding_payload())

    location = asyncio.run(_get_city_forecast(handler))

    assert request_params is not None
    assert request_params["name"] == "Москва"
    assert request_params["count"] == "1"
    assert request_params["language"] == "ru"
    assert location == CityForecast(
        name="Moscow",
        latitude=55.7522,
        longitude=37.6156
    )


def test_api_error_raises_weather_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": True, "reason": "Latitude must be in range"},
        )

    with pytest.raises(WeatherApiError, match="Latitude must be in range"):
        asyncio.run(_get_current(handler))


def test_http_error_raises_weather_api_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    with pytest.raises(WeatherApiError, match="HTTP 503"):
        asyncio.run(_get_current(handler))


def test_invalid_forecast_days_are_rejected_before_request() -> None:
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json=_daily_payload())

    with pytest.raises(ValueError, match="forecast_days"):
        asyncio.run(_get_daily(handler, forecast_days=17))

    assert called is False


def test_describe_weather_code() -> None:
    assert describe_weather_code(95) == "thunderstorm"
    assert describe_weather_code(12345) == "unknown weather code 12345"


def test_create_weather_client_returns_open_meteo_client() -> None:
    assert asyncio.run(_factory_client_is_open_meteo()) is True


async def _get_current(handler: Handler) -> CurrentForecast:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = OpenMeteoWeatherClient(client=http)
        return await client.get_current_forecast(latitude=55.75, longitude=37.61)


async def _factory_client_is_open_meteo() -> bool:
    async with create_weather_client() as client:
        return isinstance(client, OpenMeteoWeatherClient)


async def _get_daily(
    handler: Handler,
    *,
    forecast_days: int,
) -> list[DailyForecast]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = OpenMeteoWeatherClient(client=http)
        return await client.get_daily_forecast(
            latitude=55.75,
            longitude=37.61,
            forecast_days=forecast_days,
        )


async def _get_city_forecast(handler: Handler) -> CityForecast:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = OpenMeteoWeatherClient(client=http)
        return await client.get_city_forecast(city="Москва", language="ru")


def _current_payload() -> dict:
    return {
        "current": {
            "time": "2026-07-31T14:00",
            "temperature_2m": 25.1,
            "apparent_temperature": 24.7,
            "relative_humidity_2m": 47,
            "weather_code": 1,
            "wind_speed_10m": 3.7,
        },
    }


def _daily_payload() -> dict:
    return {
        "daily": {
            "time": ["2026-07-31", "2026-08-01"],
            "weather_code": [3, 80],
            "temperature_2m_max": [25.6, 30.6],
            "temperature_2m_min": [16.2, 19.1],
            "precipitation_sum": [0.0, 0.4],
            "wind_speed_10m_max": [3.9, 3.4],
        },
    }


def _geocoding_payload() -> dict:
    return {
        "results": [
            {
                "name": "Moscow",
                "latitude": 55.7522,
                "longitude": 37.6156
            },
        ],
    }
