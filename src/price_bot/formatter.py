from __future__ import annotations

from .models import PriceSearchResult, ProductCandidate
from .text_utils import format_price_rub


def format_candidate(candidate: ProductCandidate, index: int) -> str:
    price = format_price_rub(candidate.price_rub)
    availability = "наличие не проверено"
    if candidate.available is True:
        availability = "в наличии"
    elif candidate.available is False:
        availability = "нет в наличии"

    metrics = _candidate_metrics(candidate)
    note = f"\nИсточник: {candidate.note}" if candidate.note else ""
    return (
        f"{index}. {candidate.marketplace} — {price}\n"
        f"{candidate.title}\n"
        f"{metrics} · {availability}\n"
        f"{candidate.url}{note}"
    )


def format_cli_results(result: PriceSearchResult) -> str:
    lines = [f"Запрос: {result.query}"]
    if result.source_url:
        lines.append(f"Источник: {result.source_url}")
    lines.append("")

    if not result.candidates:
        lines.append("Ничего не нашел. Уточни бренд, модель, объем памяти/размер/цвет или пришли ссылку на карточку.")
    else:
        lines.extend(format_candidate(candidate, index) for index, candidate in enumerate(result.candidates, 1))

    if result.warnings:
        lines.append("")
        lines.append("Статус источников:")
        lines.extend(f"- {warning}" for warning in result.warnings)

    return "\n\n".join(lines)


def format_telegram_results(result: PriceSearchResult) -> str:
    if not result.candidates:
        return (
            f"По запросу «{result.query}» ничего не нашел.\n\n"
            "Уточни бренд, модель и важные параметры. Например: «Dyson Supersonic HD08» или «iPhone 15 128GB Black»."
        )

    best_price = next((candidate for candidate in result.candidates if candidate.price_rub is not None), None)
    best_social = _best_social_candidate(result.candidates)
    header = f"Запрос: {result.query}"
    if best_price:
        header += f"\nЛучшая цена: {best_price.marketplace}, {format_price_rub(best_price.price_rub)}"
        if best_social and best_social is not best_price:
            header += f"\nБольше доверия: {best_social.marketplace}, {_short_social(best_social)}"
    else:
        header += "\nЦены не удалось получить автоматически. Даю прямые ссылки на поиск."

    lines = [header, ""]
    for index, candidate in enumerate(result.candidates, 1):
        price = format_price_rub(candidate.price_rub)
        suffix = ""
        if candidate.note == "fallback search link":
            suffix = " (поиск)"
        elif candidate.note == "search result without parsed price":
            suffix = " (цена не распознана)"
        lines.append(f"{index}. {candidate.marketplace} — {price}{suffix}")
        lines.append(candidate.title)
        lines.append(_candidate_metrics(candidate))
        lines.append(candidate.url)
        lines.append("")

    if result.warnings:
        lines.append("Статус источников: часть площадок ограничила автоматический доступ, поэтому выдача может быть неполной.")

    return "\n".join(lines).strip()


def _candidate_metrics(candidate: ProductCandidate) -> str:
    parts: list[str] = []
    if candidate.rating is not None:
        parts.append(f"рейтинг {candidate.rating:.1f}/5")
    if candidate.reviews_count is not None:
        parts.append(f"отзывов/оценок: {_format_int(candidate.reviews_count)}")
    parts.append(_confidence_label(candidate.confidence))
    return " · ".join(parts)


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.9:
        return "совпадение высокое"
    if confidence >= 0.65:
        return "совпадение хорошее"
    if confidence >= 0.35:
        return "совпадение среднее"
    return "требует проверки"


def _best_social_candidate(candidates: list[ProductCandidate]) -> ProductCandidate | None:
    rated = [
        candidate
        for candidate in candidates
        if candidate.rating is not None or candidate.reviews_count is not None
    ]
    if not rated:
        return None
    return max(
        rated,
        key=lambda candidate: (
            candidate.rating or 0,
            candidate.reviews_count or 0,
            candidate.confidence,
        ),
    )


def _short_social(candidate: ProductCandidate) -> str:
    parts: list[str] = []
    if candidate.rating is not None:
        parts.append(f"{candidate.rating:.1f}/5")
    if candidate.reviews_count is not None:
        parts.append(f"{_format_int(candidate.reviews_count)} отзывов/оценок")
    return ", ".join(parts) if parts else "есть рейтинг/отзывы"


def _format_int(value: int) -> str:
    return f"{value:,}".replace(",", " ")
