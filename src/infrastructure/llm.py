from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from pydantic import SecretStr

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

from src.domain.agent import AgentSettings
from src.infrastructure.settings import load_project_env, settings_from_env
from src.infrastructure.weather_tools import create_weather_tools


class WeatherAssistant:
    def __init__(
        self,
        *,
        settings: AgentSettings | None = None,
        agent: Any | None = None,
    ) -> None:
        self._settings = settings or settings_from_env()
        self._agent = agent or create_weather_agent(self._settings)

    async def ask(self, message: str) -> str:
        if not message.strip():
            raise ValueError("message must not be empty")

        result = await self._agent.ainvoke(
            {"messages": [{"role": "user", "content": message}]}
        )
        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError("LLM agent returned no messages")

        return message_content_to_text(messages[-1])

    def ask_sync(self, message: str) -> str:
        return asyncio.run(self.ask(message))


def create_weather_agent(settings: AgentSettings | None = None) -> Any:
    load_project_env()
    settings = settings or settings_from_env()
    
    model = ChatOpenAI(
        api_key=SecretStr(settings.llm_api_key),
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        timeout=settings.llm_request_timeout,
    )

    return create_agent(
        model=model,
        tools=create_weather_tools(),
        system_prompt=_system_prompt(),
    )


def message_content_to_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if content is None and isinstance(message, Mapping):
        content = message.get("content")

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, Mapping):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()

    return str(content or "").strip()


def _system_prompt() -> str:
    return (
        "You are SkyAgent, a concise weather assistant. Use the available weather "
        "tools whenever the user asks about current weather, forecasts, or "
        "weather-based recommendations. Use city-name weather tools when the "
        "user provides a city name. Ask a clarifying question when the location "
        "or forecast period is missing or ambiguous. Answer in the user's "
        "language, keep units metric, and turn raw forecasts into practical "
        "recommendations."
    )
