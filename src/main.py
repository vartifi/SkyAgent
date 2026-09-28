from __future__ import annotations

import asyncio
import logging
import signal

from src.infrastructure.settings import telegram_settings_from_env
from src.presentation.telegram import TelegramApiError, run_telegram_bot


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # httpx logs full Telegram URLs, which contain the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    task = asyncio.create_task(run_telegram_bot(telegram_settings_from_env()))
    loop = asyncio.get_running_loop()
    signal_handler_installed = False
    try:
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
        signal_handler_installed = True
    except NotImplementedError:
        # Windows event loops do not support Unix signal handlers.
        pass
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        if signal_handler_installed:
            loop.remove_signal_handler(signal.SIGTERM)


def run() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except TelegramApiError as exc:
        if exc.error_code == 401:
            message = (
                "Telegram отклонил TELEGRAM_BOT_TOKEN (401 Unauthorized). "
                "Получите действующий токен у @BotFather, обновите "
                "TELEGRAM_BOT_TOKEN в .env и перезапустите бота. "
                "Для Docker Compose пересоздайте контейнер: docker compose up -d --force-recreate."
            )
        else:
            message = str(exc)
        logging.getLogger(__name__).error("%s", message)
        raise SystemExit(1) from None


if __name__ == "__main__":
    run()
