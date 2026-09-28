from __future__ import annotations

from dataclasses import dataclass, field
import math


@dataclass(frozen=True)
class TelegramSettings:
    bot_token: str = field(repr=False)
    poll_timeout: int = 30
    request_timeout: float = 35.0

    def __post_init__(self) -> None:
        if not self.bot_token.strip():
            raise ValueError("TELEGRAM_BOT_TOKEN must not be empty")
        if self.poll_timeout < 0:
            raise ValueError("TELEGRAM_POLL_TIMEOUT must be non-negative")
        if not math.isfinite(self.request_timeout) or self.request_timeout <= self.poll_timeout:
            raise ValueError("TELEGRAM_REQUEST_TIMEOUT must exceed TELEGRAM_POLL_TIMEOUT")
