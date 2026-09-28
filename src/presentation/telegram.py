from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from src.domain.telegram import TelegramSettings
from src.infrastructure.llm import WeatherAssistant


LOGGER = logging.getLogger(__name__)
TELEGRAM_API_BASE_URL = "https://api.telegram.org"
MAX_TELEGRAM_MESSAGE_LENGTH = 4096
POLLING_RETRY_DELAY_SECONDS = 5.0


class Assistant(Protocol):
    async def ask(self, message: str) -> str: ...


class TelegramApiError(RuntimeError):
    """Raised when Telegram Bot API returns an unusable response."""

    def __init__(self, message: str, *, error_code: int | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class TelegramWeatherBot:
    def __init__(
        self,
        *,
        settings: TelegramSettings,
        assistant: Assistant | None = None,
        client: httpx.AsyncClient | None = None,
        api_base_url: str = TELEGRAM_API_BASE_URL,
    ) -> None:
        self._settings = settings
        self._assistant = assistant or WeatherAssistant()
        self._api_base_url = api_base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=settings.request_timeout,
        )
        self._offset: int | None = None
        self._username: str | None = None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> TelegramWeatherBot:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def run_forever(self) -> None:
        LOGGER.info("Telegram bot polling started")
        initialized = False
        while True:
            try:
                if not initialized:
                    await self.initialize()
                    initialized = True
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except TelegramApiError as exc:
                if exc.error_code in (401, 404, 409):
                    raise
                LOGGER.warning("Telegram polling failed: %s", exc)
                await asyncio.sleep(POLLING_RETRY_DELAY_SECONDS)

    async def initialize(self) -> None:
        me = await self._telegram_request("getMe", {})
        if not isinstance(me, Mapping) or not isinstance(me.get("username"), str):
            raise TelegramApiError("Telegram getMe returned no username")
        self._username = me["username"].lower()
        await self._telegram_request("deleteWebhook", {"drop_pending_updates": False})
        await self._telegram_request("setMyCommands", {"commands": [
            {"command": "start", "description": "Знакомство с SkyAgent"},
            {"command": "help", "description": "Как запросить прогноз"},
        ]})

    async def poll_once(self) -> int:
        updates = await self._get_updates()
        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int) and self._offset is not None and update_id < self._offset:
                continue

            try:
                await self.handle_update(update)
            except TelegramApiError as exc:
                if exc.error_code in (401, 404, 409):
                    raise
                LOGGER.warning("Failed to handle Telegram update: %s", exc)
            except Exception:
                LOGGER.exception("Failed to handle Telegram update")
            if isinstance(update_id, int):
                self._offset = update_id + 1

        return len(updates)

    async def handle_update(self, update: Mapping[str, Any]) -> None:
        message = update.get("message")
        if not isinstance(message, Mapping):
            return

        chat = message.get("chat")
        if not isinstance(chat, Mapping):
            return

        chat_id = chat.get("id")
        text = message.get("text")
        if not isinstance(chat_id, int) or not isinstance(text, str):
            return

        text = text.strip()
        if not text:
            return

        command, _, recipient = text.split()[0].partition("@")
        if command.startswith("/") and recipient and recipient.lower() != self._username:
            return

        if command == "/start":
            await self._send_message(
                chat_id,
                "Привет. Я SkyAgent, погодный ассистент. "
                "Спросите, например: погода в Москве завтра.",
            )
            return

        if command == "/help":
            await self._send_message(
                chat_id,
                "Напишите город и период прогноза: сейчас, завтра, на 3 дня. "
                "Я отвечу по погоде и дам практические рекомендации.",
            )
            return

        if command.startswith("/"):
            await self._send_message(chat_id, "Неизвестная команда. Используйте /help.")
            return

        try:
            await self._send_chat_action(chat_id, "typing")
        except TelegramApiError:
            LOGGER.exception("Failed to send Telegram chat action")

        answer = await self._ask_assistant(text)
        await self._send_message(chat_id, answer)

    async def _ask_assistant(self, text: str) -> str:
        try:
            answer = await self._assistant.ask(text)
        except Exception:
            LOGGER.exception("Weather assistant failed")
            return (
                "Не удалось подготовить прогноз. "
                "Попробуйте переформулировать запрос или повторите позже."
            )

        if not isinstance(answer, str) or not answer.strip():
            return "Не удалось получить ответ по прогнозу. Попробуйте еще раз."

        return answer

    async def _get_updates(self) -> list[Mapping[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": self._settings.poll_timeout,
            "allowed_updates": ["message"],
        }
        if self._offset is not None:
            payload["offset"] = self._offset

        result = await self._telegram_request("getUpdates", payload)
        if not isinstance(result, list):
            raise TelegramApiError("Telegram getUpdates returned non-list result")

        return [update for update in result if isinstance(update, Mapping)]

    async def _send_chat_action(self, chat_id: int, action: str) -> None:
        await self._telegram_request(
            "sendChatAction",
            {
                "chat_id": chat_id,
                "action": action,
            },
        )

    async def _send_message(self, chat_id: int, text: str) -> None:
        for chunk in split_telegram_message(text):
            await self._telegram_request(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
            )

    async def _telegram_request(
        self,
        method: str,
        payload: Mapping[str, Any],
    ) -> Any:
        # Only explicit rate-limit rejections are safe to retry for sendMessage:
        # a transport failure can occur after Telegram has accepted the message.
        for attempt in range(3):
            result, retry_after = await self._request_once(method, payload)
            if retry_after is None:
                return result
            if attempt == 2:
                raise TelegramApiError("Telegram rate limit exceeded", error_code=429)
            await asyncio.sleep(retry_after)

    async def _request_once(
        self, method: str, payload: Mapping[str, Any],
    ) -> tuple[Any, int | None]:
        try:
            response = await self._client.post(
                self._method_url(method),
                json=dict(payload),
            )
            body = response.json()
        except (httpx.HTTPError, ValueError):
            # HTTP exceptions contain the request URL, including the bot token.
            raise TelegramApiError("Telegram API request failed") from None

        if not isinstance(body, Mapping):
            raise TelegramApiError("Telegram API returned non-object response")

        if response.is_error or body.get("ok") is not True:
            code = body.get("error_code", response.status_code)
            parameters = body.get("parameters")
            delay = parameters.get("retry_after") if isinstance(parameters, Mapping) else None
            if code == 429 and type(delay) is int and delay >= 0:
                return None, delay
            raise TelegramApiError(f"Telegram API error ({code})", error_code=code)

        return body.get("result"), None

    def _method_url(self, method: str) -> str:
        return (
            f"{self._api_base_url}/bot{self._settings.bot_token}/{method}"
        )


def split_telegram_message(text: str) -> list[str]:
    if len(text) <= MAX_TELEGRAM_MESSAGE_LENGTH:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > MAX_TELEGRAM_MESSAGE_LENGTH:
        split_at = remaining.rfind("\n", 0, MAX_TELEGRAM_MESSAGE_LENGTH + 1)
        if split_at <= 0:
            split_at = MAX_TELEGRAM_MESSAGE_LENGTH

        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


async def run_telegram_bot(settings: TelegramSettings) -> None:
    async with TelegramWeatherBot(settings=settings) as bot:
        await bot.run_forever()


def run_telegram_bot_sync(settings: TelegramSettings) -> None:
    asyncio.run(run_telegram_bot(settings))
