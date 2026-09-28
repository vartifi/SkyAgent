from __future__ import annotations

import asyncio
import signal

from src import main as entrypoint
from src.domain.telegram import TelegramSettings


def test_sigterm_cancels_bot_and_removes_handler(monkeypatch) -> None:
    events = []

    async def run() -> None:
        loop = asyncio.get_running_loop()
        handlers = {}

        def add_handler(signum, callback):
            handlers[signum] = callback

        def remove_handler(signum):
            events.append("handler removed")
            del handlers[signum]

        async def fake_bot(settings):
            assert settings.bot_token == "test"
            try:
                handlers[signal.SIGTERM]()
                await asyncio.sleep(0)
            finally:
                events.append("bot closed")

        monkeypatch.setattr(loop, "add_signal_handler", add_handler)
        monkeypatch.setattr(loop, "remove_signal_handler", remove_handler)
        monkeypatch.setattr(entrypoint, "run_telegram_bot", fake_bot)
        monkeypatch.setattr(entrypoint, "telegram_settings_from_env",
                            lambda: TelegramSettings(bot_token="test"))
        await entrypoint.main()
        assert handlers == {}

    asyncio.run(run())
    assert events == ["bot closed", "handler removed"]


def test_unauthorized_has_actionable_error_and_nonzero_exit(monkeypatch, caplog) -> None:
    import pytest
    from src.presentation.telegram import TelegramApiError

    async def unauthorized():
        raise TelegramApiError("Telegram API error (401)", error_code=401)

    monkeypatch.setattr(entrypoint, "main", unauthorized)
    with pytest.raises(SystemExit) as exc:
        entrypoint.run()
    assert exc.value.code == 1
    assert "TELEGRAM_BOT_TOKEN" in caplog.text
    assert "@BotFather" in caplog.text
    assert "401 Unauthorized" in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
