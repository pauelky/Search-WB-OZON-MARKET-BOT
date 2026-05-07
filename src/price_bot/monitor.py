from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ProductCandidate, PriceSearchResult
from .text_utils import format_price_rub


@dataclass(frozen=True)
class WatchSnapshot:
    marketplace: str
    title: str
    url: str
    price_rub: int | None
    rating: float | None
    reviews_count: int | None

    @classmethod
    def from_candidate(cls, candidate: ProductCandidate) -> "WatchSnapshot":
        return cls(
            marketplace=candidate.marketplace,
            title=candidate.title,
            url=candidate.url,
            price_rub=candidate.price_rub,
            rating=candidate.rating,
            reviews_count=candidate.reviews_count,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchSnapshot":
        return cls(
            marketplace=str(data.get("marketplace") or ""),
            title=str(data.get("title") or ""),
            url=str(data.get("url") or ""),
            price_rub=_optional_int(data.get("price_rub")),
            rating=_optional_float(data.get("rating")),
            reviews_count=_optional_int(data.get("reviews_count")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "marketplace": self.marketplace,
            "title": self.title,
            "url": self.url,
            "price_rub": self.price_rub,
            "rating": self.rating,
            "reviews_count": self.reviews_count,
        }


class WatchStore:
    def __init__(self, path: str):
        self.path = Path(path)

    def add_watch(self, chat_id: int, query: str, snapshot: WatchSnapshot) -> dict[str, Any]:
        data = self._load()
        item = {
            "id": uuid.uuid4().hex[:8],
            "chat_id": chat_id,
            "query": query,
            "created_at": time.time(),
            "last_checked_at": time.time(),
            "last_snapshot": snapshot.to_dict(),
        }
        data["watches"].append(item)
        self._save(data)
        return item

    def list_watches(self, chat_id: int) -> list[dict[str, Any]]:
        data = self._load()
        return [item for item in data["watches"] if item.get("chat_id") == chat_id]

    def remove_watch(self, chat_id: int, watch_id: str) -> bool:
        data = self._load()
        before = len(data["watches"])
        data["watches"] = [
            item
            for item in data["watches"]
            if not (item.get("chat_id") == chat_id and item.get("id") == watch_id)
        ]
        changed = len(data["watches"]) != before
        if changed:
            self._save(data)
        return changed

    def due_watches(self, interval_seconds: int, limit: int = 5) -> list[dict[str, Any]]:
        now = time.time()
        data = self._load()
        due = [
            item
            for item in data["watches"]
            if now - float(item.get("last_checked_at") or 0) >= interval_seconds
        ]
        return due[:limit]

    def update_watch(self, watch_id: str, snapshot: WatchSnapshot) -> None:
        data = self._load()
        for item in data["watches"]:
            if item.get("id") == watch_id:
                item["last_checked_at"] = time.time()
                item["last_snapshot"] = snapshot.to_dict()
                break
        self._save(data)

    def touch_watch(self, watch_id: str) -> None:
        data = self._load()
        for item in data["watches"]:
            if item.get("id") == watch_id:
                item["last_checked_at"] = time.time()
                break
        self._save(data)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"watches": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"watches": []}
        if not isinstance(data, dict) or not isinstance(data.get("watches"), list):
            return {"watches": []}
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def best_watch_candidate(result: PriceSearchResult) -> ProductCandidate | None:
    candidates = [candidate for candidate in result.candidates if candidate.has_market_data]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: (
            candidate.price_rub is None,
            candidate.price_rub or 0,
            -(candidate.rating or 0),
            -(candidate.reviews_count or 0),
        ),
    )


def describe_watch_change(previous: WatchSnapshot, current: WatchSnapshot) -> str | None:
    changes: list[str] = []
    if previous.price_rub is not None and current.price_rub is not None:
        diff = current.price_rub - previous.price_rub
        if diff < 0:
            changes.append(f"цена снизилась на {format_price_rub(abs(diff))}")
        elif diff > 0:
            changes.append(f"цена выросла на {format_price_rub(diff)}")
    elif previous.price_rub is None and current.price_rub is not None:
        changes.append(f"появилась цена {format_price_rub(current.price_rub)}")

    if previous.rating is not None and current.rating is not None and current.rating != previous.rating:
        changes.append(f"рейтинг {previous.rating:.1f} -> {current.rating:.1f}")
    elif previous.rating is None and current.rating is not None:
        changes.append(f"появился рейтинг {current.rating:.1f}/5")

    if previous.reviews_count is not None and current.reviews_count is not None:
        diff = current.reviews_count - previous.reviews_count
        if diff > 0:
            changes.append(f"новых отзывов/оценок: {diff}")
    elif previous.reviews_count is None and current.reviews_count is not None:
        changes.append(f"появились отзывы/оценки: {current.reviews_count}")

    if not changes:
        return None
    return "; ".join(changes)


def format_watch_snapshot(snapshot: WatchSnapshot) -> str:
    parts = [f"{snapshot.marketplace}, {format_price_rub(snapshot.price_rub)}"]
    if snapshot.rating is not None:
        parts.append(f"рейтинг {snapshot.rating:.1f}/5")
    if snapshot.reviews_count is not None:
        parts.append(f"отзывов/оценок: {snapshot.reviews_count}")
    return " · ".join(parts)


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None


def _optional_float(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None
