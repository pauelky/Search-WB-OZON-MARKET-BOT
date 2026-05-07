from __future__ import annotations

from .models import PriceSearchResult, ProductCandidate
from .text_utils import format_price_rub


def format_candidate(candidate: ProductCandidate, index: int) -> str:
    price = format_price_rub(candidate.price_rub)
    availability = ""
    if candidate.available is True:
        availability = " · похоже, доступно"
    elif candidate.available is False:
        availability = " · нет в наличии"

    note = f" · {candidate.note}" if candidate.note else ""
    return (
        f"{index}. {candidate.marketplace}: {price}{availability}\n"
        f"{candidate.title}\n"
        f"{candidate.url}{note}"
    )


def format_cli_results(result: PriceSearchResult) -> str:
    lines = [f"Запрос: {result.query}"]
    if result.source_url:
        lines.append(f"Источник: {result.source_url}")
    lines.append("")

    if not result.candidates:
        lines.append("Ничего не нашел.")
    else:
        lines.extend(format_candidate(candidate, index) for index, candidate in enumerate(result.candidates, 1))

    if result.warnings:
        lines.append("")
        lines.append("Предупреждения:")
        lines.extend(f"- {warning}" for warning in result.warnings)

    return "\n\n".join(lines)


def format_telegram_results(result: PriceSearchResult) -> str:
    if not result.candidates:
        return (
            f"По запросу «{result.query}» ничего не нашел.\n\n"
            "Попробуй скинуть более точное название: бренд, модель, память/размер/цвет."
        )

    best = next((candidate for candidate in result.candidates if candidate.price_rub is not None), None)
    header = f"Ищу: {result.query}"
    if best:
        header += f"\nСамое дешевое из найденного: {best.marketplace}, {format_price_rub(best.price_rub)}"
    else:
        header += "\nЦены не удалось достать автоматически, даю прямые ссылки на поиск."

    lines = [header, ""]
    for index, candidate in enumerate(result.candidates, 1):
        price = format_price_rub(candidate.price_rub)
        suffix = ""
        if candidate.note == "fallback search link":
            suffix = " (поиск)"
        elif candidate.note == "search result without parsed price":
            suffix = " (цена не распознана)"
        lines.append(f"{index}. {candidate.marketplace}: {price}{suffix}")
        lines.append(candidate.title)
        lines.append(candidate.url)
        lines.append("")

    if result.warnings:
        lines.append("Часть источников ответила с защитой/ошибкой, поэтому результат может быть неполным.")

    return "\n".join(lines).strip()
