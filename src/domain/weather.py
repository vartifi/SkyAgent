from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WeatherSettings:
    weather_latitude: float
    weather_longitude: float
    weather_forecast_days: int
    weather_timezone: str


@dataclass(frozen=True)
class CurrentForecast:
    time: str
    temperature: float
    apparent_temperature: float
    relative_humidity: int
    wind_speed: float
    weather_code: int
    description: str


@dataclass(frozen=True)
class DailyForecast:
    date: str
    temperature_min: float
    temperature_max: float
    precipitation_sum: float
    wind_speed_max: float
    weather_code: int
    description: str


@dataclass(frozen=True)
class CityForecast:
    name: str
    latitude: float
    longitude: float


class WeatherClient(Protocol):
    async def __aenter__(self) -> WeatherClient: ...

    async def __aexit__(self, *_: object) -> None: ...

    async def get_city_forecast(
        self,
        *,
        city: str,
        language: str = "en",
    ) -> CityForecast: ...

    async def get_current_forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        timezone: str,
    ) -> CurrentForecast: ...

    async def get_daily_forecast(
        self,
        *,
        latitude: float,
        longitude: float,
        forecast_days: int,
        timezone: str,
    ) -> list[DailyForecast]: ...

WeatherClientFactory = Callable[[], WeatherClient]
