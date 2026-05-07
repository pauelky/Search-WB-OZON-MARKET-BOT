from __future__ import annotations

import logging
import time

from .config import Config
from .formatter import format_telegram_results
from .http_client import FetchError, HttpClient
from .search import PriceSearchService


HELP_TEXT = """Привет. Скинь ссылку на товар или просто название.

Примеры:
iphone 15 128gb black
https://www.ozon.ru/product/...

Я попробую найти похожие варианты на WB / Ozon / Яндекс Маркете и отсортировать по цене."""


class TelegramApi:
    def __init__(self, token: str, timeout_seconds: int):
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.http = HttpClient(timeout_seconds=timeout_seconds)

    def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, object]]:
        payload: dict[str, object] = {
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset

        data = self.http.post_json(f"{self.base_url}/getUpdates", payload, timeout_seconds=timeout + 10)
        if not isinstance(data, dict) or not data.get("ok"):
            return []
        result = data.get("result")
        return result if isinstance(result, list) else []

    def send_message(self, chat_id: int, text: str) -> None:
        self.http.post_json(
            f"{self.base_url}/sendMessage",
            {
                "chat_id": chat_id,
                "text": text[:3900],
                "disable_web_page_preview": True,
            },
        )


def run_polling_bot(config: Config) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    assert config.telegram_bot_token

    api = TelegramApi(config.telegram_bot_token, config.http_timeout_seconds)
    service = PriceSearchService(config)
    offset: int | None = None

    logging.info("Market price bot started")
    while True:
        try:
            updates = api.get_updates(offset, config.bot_poll_timeout)
        except FetchError as exc:
            logging.warning("Telegram getUpdates failed: %s", exc)
            time.sleep(3)
            continue

        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                offset = update_id + 1

            message = update.get("message")
            if not isinstance(message, dict):
                continue

            chat = message.get("chat")
            if not isinstance(chat, dict) or not isinstance(chat.get("id"), int):
                continue
            chat_id = chat["id"]

            text = str(message.get("text") or "").strip()
            if not text:
                api.send_message(chat_id, "Пришли ссылку на товар или название товара текстом.")
                continue

            if text.startswith("/start") or text.startswith("/help"):
                api.send_message(chat_id, HELP_TEXT)
                continue

            api.send_message(chat_id, "Смотрю цены. Обычно это занимает 5-15 секунд.")
            try:
                result = service.search_from_text(text)
                api.send_message(chat_id, format_telegram_results(result))
            except Exception as exc:
                logging.exception("Search failed")
                api.send_message(chat_id, f"Не смог обработать запрос: {exc}")
