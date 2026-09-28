from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx

from src.domain.telegram import TelegramSettings
from src.presentation.telegram import TelegramWeatherBot, split_telegram_message


def test_poll_once_sends_assistant_answer() -> None:
    requests: list[tuple[str, dict[str, Any]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        requests.append((request.url.path, payload))

        if request.url.path.endswith("/getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 10,
                            "message": {
                                "chat": {"id": 42},
                                "text": "Погода в Москве завтра",
                            },
                        }
                    ],
                },
            )

        return httpx.Response(200, json={"ok": True, "result": True})

    async def run() -> FakeAssistant:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            assistant = FakeAssistant(answer="Будет дождь.")
            bot = TelegramWeatherBot(
                settings=TelegramSettings(bot_token="token", poll_timeout=1),
                assistant=assistant,
                client=client,
            )

            updates = await bot.poll_once()

        assert updates == 1
        return assistant

    assistant = asyncio.run(run())

    assert assistant.messages == ["Погода в Москве завтра"]
    assert requests == [
        ("/bottoken/getUpdates", {"timeout": 1, "allowed_updates": ["message"]}),
        ("/bottoken/sendChatAction", {"chat_id": 42, "action": "typing"}),
        (
            "/bottoken/sendMessage",
            {
                "chat_id": 42,
                "text": "Будет дождь.",
                "disable_web_page_preview": True,
            },
        ),
    ]


def test_poll_once_uses_offset_after_seen_update() -> None:
    requests: list[dict[str, Any]] = []
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        payload = json.loads(request.content.decode())
        requests.append(payload)
        calls += 1

        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 99,
                            "message": {"chat": {"id": 42}, "text": "/start"},
                        }
                    ],
                },
            )

        return httpx.Response(200, json={"ok": True, "result": []})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            bot = TelegramWeatherBot(
                settings=TelegramSettings(bot_token="token", poll_timeout=1),
                assistant=FakeAssistant(answer="unused"),
                client=client,
            )

            await bot.poll_once()
            await bot.poll_once()

    asyncio.run(run())

    assert requests[0] == {"timeout": 1, "allowed_updates": ["message"]}
    assert requests[2] == {
        "timeout": 1,
        "allowed_updates": ["message"],
        "offset": 100,
    }


def test_start_command_does_not_call_assistant() -> None:
    sent_messages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        if request.url.path.endswith("/sendMessage"):
            sent_messages.append(payload["text"])
        return httpx.Response(200, json={"ok": True, "result": True})

    async def run() -> FakeAssistant:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            assistant = FakeAssistant(answer="unused")
            bot = TelegramWeatherBot(
                settings=TelegramSettings(bot_token="token"),
                assistant=assistant,
                client=client,
            )

            await bot.handle_update(
                {
                    "message": {
                        "chat": {"id": 42},
                        "text": "/start",
                    },
                }
            )

        return assistant

    assistant = asyncio.run(run())

    assert assistant.messages == []
    assert len(sent_messages) == 1
    assert "SkyAgent" in sent_messages[0]


def test_assistant_error_returns_friendly_message() -> None:
    sent_messages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        if request.url.path.endswith("/sendMessage"):
            sent_messages.append(payload["text"])
        return httpx.Response(200, json={"ok": True, "result": True})

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
        ) as client:
            bot = TelegramWeatherBot(
                settings=TelegramSettings(bot_token="token"),
                assistant=FakeAssistant(error=RuntimeError("llm down")),
                client=client,
            )

            await bot.handle_update(
                {
                    "message": {
                        "chat": {"id": 42},
                        "text": "Погода?",
                    },
                }
            )

    asyncio.run(run())

    assert sent_messages == [
        "Не удалось подготовить прогноз. "
        "Попробуйте переформулировать запрос или повторите позже."
    ]


def test_split_telegram_message() -> None:
    chunks = split_telegram_message("x" * 4097)

    assert chunks == ["x" * 4096, "x"]


class FakeAssistant:
    def __init__(
        self,
        *,
        answer: str = "",
        error: Exception | None = None,
    ) -> None:
        self._answer = answer
        self._error = error
        self.messages: list[str] = []

    async def ask(self, message: str) -> str:
        self.messages.append(message)
        if self._error:
            raise self._error
        return self._answer


def test_initialize_keeps_pending_updates_and_registers_commands() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.url.path.rsplit("/", 1)[-1], json.loads(request.content)))
        result = {"username": "SkyAgentBot"} if requests[-1][0] == "getMe" else True
        return httpx.Response(200, json={"ok": True, "result": result})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            bot = TelegramWeatherBot(settings=TelegramSettings(bot_token="token"),
                                     assistant=FakeAssistant(), client=client)
            await bot.initialize()
            await bot.handle_update({"message": {"chat": {"id": 42}, "text": "/help@OtherBot"}})
            assert len(requests) == 3
            await bot.handle_update({"message": {"chat": {"id": 42}, "text": "/help@SkyAgentBot"}})

    asyncio.run(run())
    assert [method for method, _ in requests] == ["getMe", "deleteWebhook", "setMyCommands", "sendMessage"]
    assert requests[1][1] == {"drop_pending_updates": False}
    assert [cmd["command"] for cmd in requests[2][1]["commands"]] == ["start", "help"]


def test_unknown_command_does_not_match_start_prefix() -> None:
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["text"])
        return httpx.Response(200, json={"ok": True, "result": True})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            assistant = FakeAssistant()
            bot = TelegramWeatherBot(settings=TelegramSettings(bot_token="token"),
                                     assistant=assistant, client=client)
            await bot.handle_update({"message": {"chat": {"id": 42}, "text": "/startled"}})
            assert assistant.messages == []

    asyncio.run(run())
    assert sent == ["Неизвестная команда. Используйте /help."]


def test_rate_limit_retries_same_message(monkeypatch) -> None:
    requests = []
    delays = []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("src.presentation.telegram.asyncio.sleep", sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(429, json={"ok": False, "error_code": 429,
                                           "parameters": {"retry_after": 7}})
        return httpx.Response(200, json={"ok": True, "result": True})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            bot = TelegramWeatherBot(settings=TelegramSettings(bot_token="token"),
                                     assistant=FakeAssistant(), client=client)
            await bot.handle_update({"message": {"chat": {"id": 42}, "text": "/start"}})

    asyncio.run(run())
    assert delays == [7]
    assert len(requests) == 2 and requests[0] == requests[1]


def test_transport_error_does_not_expose_token() -> None:
    import traceback
    from src.presentation.telegram import TelegramApiError

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(str(request.url), request=request)

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            bot = TelegramWeatherBot(settings=TelegramSettings(bot_token="secret-token"),
                                     assistant=FakeAssistant(), client=client)
            try:
                await bot.poll_once()
            except TelegramApiError:
                assert "secret-token" not in traceback.format_exc()
            else:
                raise AssertionError("Expected TelegramApiError")

    asyncio.run(run())


def test_invalid_token_stops_polling() -> None:
    import pytest
    from src.presentation.telegram import TelegramApiError

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "error_code": 401})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            bot = TelegramWeatherBot(settings=TelegramSettings(bot_token="token"),
                                     assistant=FakeAssistant(), client=client)
            with pytest.raises(TelegramApiError) as exc:
                await bot.run_forever()
            assert exc.value.error_code == 401

    asyncio.run(run())


def test_telegram_settings_validation() -> None:
    import pytest

    for kwargs in ({"bot_token": " "}, {"bot_token": "token", "poll_timeout": -1},
                   {"bot_token": "token", "request_timeout": 30},
                   {"bot_token": "token", "request_timeout": float("nan")}):
        with pytest.raises(ValueError):
            TelegramSettings(**kwargs)
    assert "secret-token" not in repr(TelegramSettings(bot_token="secret-token"))


def test_cancellation_does_not_acknowledge_unfinished_update() -> None:
    import pytest

    class CancelledAssistant:
        async def ask(self, message: str) -> str:
            raise asyncio.CancelledError

    offsets = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("getUpdates"):
            offsets.append(json.loads(request.content).get("offset"))
            return httpx.Response(200, json={"ok": True, "result": [
                {"update_id": 10, "message": {"chat": {"id": 42}, "text": "Погода?"}}
            ]})
        return httpx.Response(200, json={"ok": True, "result": True})

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            bot = TelegramWeatherBot(settings=TelegramSettings(bot_token="token"),
                                     assistant=CancelledAssistant(), client=client)
            for _ in range(2):
                with pytest.raises(asyncio.CancelledError):
                    await bot.poll_once()

    asyncio.run(run())
    assert offsets == [None, None]


def test_context_manager_closes_owned_client_on_cancellation() -> None:
    import pytest

    async def run() -> None:
        bot = TelegramWeatherBot(settings=TelegramSettings(bot_token="token"),
                                 assistant=FakeAssistant())
        with pytest.raises(asyncio.CancelledError):
            async with bot:
                raise asyncio.CancelledError
        assert bot._client.is_closed

    asyncio.run(run())
