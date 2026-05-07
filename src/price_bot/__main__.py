from __future__ import annotations

import sys

from .config import Config
from .formatter import format_cli_results
from .search import PriceSearchService
from .telegram_bot import run_polling_bot


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    config = Config.from_env()

    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:]).strip()
        service = PriceSearchService(config)
        result = service.search_from_text(text)
        print(format_cli_results(result))
        return 0

    if not config.telegram_bot_token:
        print(
            "TELEGRAM_BOT_TOKEN is not set. Set it and run again, or pass a query:\n"
            "  python -m price_bot \"iphone 15 128gb\""
        )
        return 2

    run_polling_bot(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
