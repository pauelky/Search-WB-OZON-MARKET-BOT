from __future__ import annotations

import logging
import time

from .config import Config
from .formatter import format_telegram_results
from .http_client import FetchError, HttpClient
from .monitor import (
    WatchSnapshot,
    WatchStore,
    best_watch_candidate,
    describe_watch_change,
    format_watch_snapshot,
)
from .search import PriceSearchService


HELP_TEXT = """Привет. Я ищу товар по маркетплейсам и сравниваю не только цену, но и рейтинг с отзывами.

Что можно отправить:
iphone 15 128gb black
Dyson Supersonic HD08
https://www.ozon.ru/product/...
https://www.wildberries.ru/catalog/...

Команды:
/watch <товар или ссылка> — следить за ценой, рейтингом и отзывами
/watchlist — мои наблюдения
/unwatch <id> — удалить наблюдение
/status — статус источников

Поиск строгий: восстановленные, уцененные и похожие копии я не смешиваю с новым оригинальным товаром, если ты сам это не указал."""


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
    watch_store = WatchStore(config.watch_file)
    offset: int | None = None
    last_watch_scan = 0.0

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
                api.send_message(chat_id, "Пришли ссылку на товар или название: бренд, модель и важные параметры.")
                continue

            command = _command_name(text)
            if command in {"/start", "/help"}:
                api.send_message(chat_id, HELP_TEXT)
                continue

            if command == "/status":
                api.send_message(chat_id, _status_text(config))
                continue

            if command == "/watch":
                query = _command_argument(text)
                _handle_watch(api, service, watch_store, chat_id, query)
                continue

            if command == "/watchlist":
                _handle_watchlist(api, watch_store, chat_id)
                continue

            if command == "/unwatch":
                watch_id = _command_argument(text)
                _handle_unwatch(api, watch_store, chat_id, watch_id)
                continue

            api.send_message(chat_id, "Ищу варианты и сверяю цену, рейтинг и отзывы. Обычно это 5-15 секунд.")
            try:
                result = service.search_from_text(text)
                api.send_message(chat_id, format_telegram_results(result))
            except Exception as exc:
                logging.exception("Search failed")
                api.send_message(chat_id, f"Не смог обработать запрос. Деталь для отладки: {exc}")

        now = time.time()
        if now - last_watch_scan >= 60:
            last_watch_scan = now
            _process_due_watches(api, service, watch_store, config)


def _handle_watch(
    api: TelegramApi,
    service: PriceSearchService,
    watch_store: WatchStore,
    chat_id: int,
    query: str,
) -> None:
    if not query:
        api.send_message(chat_id, "Напиши так: /watch Dyson Supersonic HD08 или /watch <ссылка на товар>.")
        return

    api.send_message(chat_id, "Добавляю наблюдение. Сначала сниму текущую цену, рейтинг и отзывы.")
    result = service.search_from_text(query)
    candidate = best_watch_candidate(result)
    if not candidate:
        api.send_message(chat_id, "Не нашел карточку с ценой/рейтингом. Уточни запрос и попробуй еще раз.")
        return

    snapshot = WatchSnapshot.from_candidate(candidate)
    watch = watch_store.add_watch(chat_id, result.query, snapshot)
    api.send_message(
        chat_id,
        "\n".join(
            [
                f"Наблюдение добавлено: #{watch['id']}",
                f"Запрос: {result.query}",
                format_watch_snapshot(snapshot),
                snapshot.title,
                snapshot.url,
            ]
        ),
    )


def _handle_watchlist(api: TelegramApi, watch_store: WatchStore, chat_id: int) -> None:
    watches = watch_store.list_watches(chat_id)
    if not watches:
        api.send_message(chat_id, "У тебя пока нет наблюдений. Добавь: /watch <товар или ссылка>.")
        return

    lines = ["Твои наблюдения:"]
    for item in watches:
        snapshot = WatchSnapshot.from_dict(item.get("last_snapshot") or {})
        lines.append(f"#{item.get('id')} — {item.get('query')}")
        lines.append(format_watch_snapshot(snapshot))
    api.send_message(chat_id, "\n".join(lines))


def _handle_unwatch(api: TelegramApi, watch_store: WatchStore, chat_id: int, watch_id: str) -> None:
    if not watch_id:
        api.send_message(chat_id, "Напиши id наблюдения: /unwatch 1a2b3c4d")
        return
    if watch_store.remove_watch(chat_id, watch_id):
        api.send_message(chat_id, f"Наблюдение #{watch_id} удалено.")
    else:
        api.send_message(chat_id, f"Не нашел наблюдение #{watch_id}. Проверь /watchlist.")


def _process_due_watches(
    api: TelegramApi,
    service: PriceSearchService,
    watch_store: WatchStore,
    config: Config,
) -> None:
    interval_seconds = max(5, config.watch_interval_minutes) * 60
    for item in watch_store.due_watches(interval_seconds):
        watch_id = str(item.get("id") or "")
        chat_id = item.get("chat_id")
        query = str(item.get("query") or "")
        if not isinstance(chat_id, int) or not watch_id or not query:
            continue

        try:
            result = service.search_from_text(query)
            candidate = best_watch_candidate(result)
        except Exception:
            logging.exception("Watch check failed")
            watch_store.touch_watch(watch_id)
            continue

        if not candidate:
            watch_store.touch_watch(watch_id)
            continue

        previous = WatchSnapshot.from_dict(item.get("last_snapshot") or {})
        current = WatchSnapshot.from_candidate(candidate)
        change = describe_watch_change(previous, current)
        watch_store.update_watch(watch_id, current)
        if not change:
            continue

        api.send_message(
            chat_id,
            "\n".join(
                [
                    f"Изменение по наблюдению #{watch_id}",
                    f"Запрос: {query}",
                    change,
                    format_watch_snapshot(current),
                    current.title,
                    current.url,
                ]
            ),
        )


def _status_text(config: Config) -> str:
    return "\n".join(
        [
            "Работаю.",
            "Wildberries: цена, наличие, рейтинг и отзывы через публичные endpoints.",
            "Яндекс Маркет: цена, рейтинг и отзывы, если площадка не закрыла доступ с IP сервера.",
            "Ozon: прямые ссылки и web-search fallback; полноценные цены зависят от доступности страницы/API.",
            f"Наблюдения проверяются раз в {config.watch_interval_minutes} мин.",
        ]
    )


def _command_name(text: str) -> str | None:
    if not text.startswith("/"):
        return None
    return text.split(maxsplit=1)[0].split("@", 1)[0].lower()


def _command_argument(text: str) -> str:
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""
