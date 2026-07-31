from dataclasses import dataclass


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
