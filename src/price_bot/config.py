from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str | None
    bot_poll_timeout: int = 25
    market_price_limit: int = 8
    http_timeout_seconds: int = 14
    wb_dest: str = "-1257786"
    watch_interval_minutes: int = 360
    watch_file: str = "data/watches.json"

    @classmethod
    def from_env(cls) -> "Config":
        _load_dotenv()
        return cls(
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            bot_poll_timeout=_int_env("BOT_POLL_TIMEOUT", 25),
            market_price_limit=_int_env("MARKET_PRICE_LIMIT", 8),
            http_timeout_seconds=_int_env("HTTP_TIMEOUT_SECONDS", 14),
            wb_dest=os.getenv("WB_DEST", "-1257786"),
            watch_interval_minutes=_int_env("WATCH_INTERVAL_MINUTES", 360),
            watch_file=os.getenv("WATCH_FILE", "data/watches.json"),
        )


def _load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)
