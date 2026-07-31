from __future__ import annotations

import os

from dotenv import load_dotenv

from src.domain.agent import AgentSettings
from src.domain.weather import WeatherSettings


ENV_FILE = ".env"


def settings_from_env(
    *,
    dotenv_path: str | os.PathLike[str] | None = None,
) -> AgentSettings:
    load_dotenv(dotenv_path=dotenv_path or ENV_FILE, override=True)

    return AgentSettings(
        llm_api_key=_required_env("LLM_API_KEY"),
        llm_base_url=_required_env("LLM_BASE_URL"),
        llm_model=_required_env("LLM_MODEL"),
        llm_temperature=float(_required_env("LLM_TEMPERATURE")),
        llm_request_timeout=float(_required_env("LLM_REQUEST_TIMEOUT")),
    )


def weather_settings_from_env(
    *,
    dotenv_path: str | os.PathLike[str] | None = None,
) -> WeatherSettings:
    load_dotenv(dotenv_path=dotenv_path or ENV_FILE, override=True)

    return WeatherSettings(
        weather_latitude=float(_required_env("WEATHER_DEFAULT_LATITUDE")),
        weather_longitude=float(_required_env("WEATHER_DEFAULT_LONGITUDE")),
        weather_forecast_days=int(_required_env("WEATHER_DEFAULT_FORECAST_DAYS")),
        weather_timezone=_required_env("WEATHER_DEFAULT_TIMEZONE"),
    )


def load_project_env() -> None:
    load_dotenv(dotenv_path=ENV_FILE, override=True)


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

