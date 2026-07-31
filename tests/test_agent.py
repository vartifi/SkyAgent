from __future__ import annotations

import asyncio
from typing import Any

import pytest

from src.domain.agent import AgentSettings
from src.domain.weather import (
    CityForecast,
    CurrentForecast,
    DailyForecast,
    WeatherSettings,
)
from src.infrastructure.llm import WeatherAssistant
from src.infrastructure.weather_tools import create_weather_tools


def test_current_weather_by_city_tool_resolves_city() -> None:
    fake_client = FakeWeatherClient()
    tool = _tool_by_name(
        create_weather_tools(_weather_settings(), client_factory=lambda: fake_client),
        "get_current_weather_by_city",
    )

    text = asyncio.run(tool(city="Москва", language="ru"))

    assert fake_client.location_call == {"city": "Москва", "language": "ru"}
    assert fake_client.current_call == {
        "latitude": 55.7522,
        "longitude": 37.6156,
        "timezone": "auto",
    }
    assert "Location: Moscow." in text
    assert "Current weather for 55.7522, 37.6156" in text


def test_daily_weather_by_city_tool_resolves_city() -> None:
    fake_client = FakeWeatherClient()
    tool = _tool_by_name(
        create_weather_tools(_weather_settings(), client_factory=lambda: fake_client),
        "get_daily_weather_by_city",
    )

    text = asyncio.run(tool(city="Москва", forecast_days=2, language="ru"))

    assert fake_client.location_call == {"city": "Москва", "language": "ru"}
    assert fake_client.daily_call == {
        "latitude": 55.7522,
        "longitude": 37.6156,
        "forecast_days": 2,
        "timezone": "auto",
    }
    assert "Location: Moscow." in text
    assert "Daily forecast for 55.7522, 37.6156" in text


def test_weather_assistant_invokes_agent() -> None:
    fake_agent = FakeAgent()
    assistant = WeatherAssistant(settings=_agent_settings(), agent=fake_agent)

    answer = asyncio.run(assistant.ask("Какая погода в Москве?"))

    assert answer == "Take an umbrella."
    assert fake_agent.payload == {
        "messages": [{"role": "user", "content": "Какая погода в Москве?"}]
    }


def test_weather_assistant_rejects_empty_message() -> None:
    assistant = WeatherAssistant(settings=_agent_settings(), agent=FakeAgent())

    with pytest.raises(ValueError, match="message"):
        asyncio.run(assistant.ask("  "))


class FakeWeatherClient:
    def __init__(self) -> None:
        self.location_call: dict[str, Any] | None = None
        self.current_call: dict[str, Any] | None = None
        self.daily_call: dict[str, Any] | None = None

    async def __aenter__(self) -> FakeWeatherClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def get_city_forecast(self, **kwargs: Any) -> CityForecast:
        self.location_call = kwargs
        return CityForecast(name="Moscow", latitude=55.7522, longitude=37.6156)

    async def get_current_forecast(self, **kwargs: Any) -> CurrentForecast:
        self.current_call = kwargs
        return CurrentForecast(
            time="2026-07-31T14:00",
            temperature=25.1,
            apparent_temperature=24.7,
            relative_humidity=47,
            wind_speed=3.7,
            weather_code=1,
            description="mainly clear",
        )

    async def get_daily_forecast(self, **kwargs: Any) -> list[DailyForecast]:
        self.daily_call = kwargs
        return [
            DailyForecast(
                date="2026-07-31",
                temperature_min=16.2,
                temperature_max=25.6,
                precipitation_sum=0.0,
                wind_speed_max=3.9,
                weather_code=3,
                description="overcast",
            ),
        ]


class FakeAgent:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None

    async def ainvoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.payload = payload
        return {"messages": [{"role": "assistant", "content": "Take an umbrella."}]}


def _tool_by_name(tools: Any, name: str) -> Any:
    for tool in tools:
        if tool.__name__ == name:
            return tool
    raise AssertionError(f"missing tool: {name}")


def _agent_settings() -> AgentSettings:
    return AgentSettings(
        llm_api_key="test-key",
        llm_base_url=None,
        llm_model="gpt-5-mini",
        llm_temperature=0.2,
        llm_request_timeout=30.0,
    )


def _weather_settings() -> WeatherSettings:
    return WeatherSettings(
        weather_latitude=55.7558,
        weather_longitude=37.6173,
        weather_forecast_days=3,
        weather_timezone="auto",
    )
