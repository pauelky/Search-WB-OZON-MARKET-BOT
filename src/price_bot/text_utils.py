from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, unquote, urlparse


URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)

STOP_WORDS = {
    "и",
    "в",
    "на",
    "для",
    "с",
    "по",
    "от",
    "до",
    "купить",
    "цена",
    "цены",
    "товар",
    "маркет",
    "market",
    "ozon",
    "wb",
    "wildberries",
    "яндекс",
    "фен",
    "волос",
    "профессиональный",
    "насадками",
}

TOKEN_ALIASES = {
    "dayson": "dyson",
    "дайсон": "dyson",
    "дисон": "dyson",
    "суперсоник": "supersonic",
}

URL_PATH_STOP_PARTS = {
    "card",
    "catalog",
    "category",
    "detail.aspx",
    "product",
    "search",
}


def first_url(text: str) -> str | None:
    match = URL_RE.search(text)
    if not match:
        return None
    return match.group(0).rstrip(".,;)")


def strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return " ".join(html.unescape(value).split())


def clean_product_title(title: str) -> str:
    title = html.unescape(title)
    title = re.sub(r"\s+", " ", title).strip()
    title = re.sub(r"\s*[|—-]\s*(OZON|Ozon|Wildberries|WB|Яндекс Маркет|Yandex Market).*$", "", title)
    title = re.sub(r"\bкупить\b.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\bцена\b.*$", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s{2,}", " ", title).strip(" -|")
    title = title.strip(" -|—")
    return title[:180].strip()


def slug_to_query(slug: str) -> str:
    slug = unquote(slug)
    slug = re.sub(r"[-_]+", " ", slug)
    slug = re.sub(r"\b\d{6,}\b", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip()
    return clean_product_title(slug)


def query_from_url_path(url: str) -> str | None:
    parsed = urlparse(url)
    path = parsed.path.strip("/")
    if not path:
        return None

    parts = [part for part in path.split("/") if part]
    if not parts:
        return None

    if "ozon" in parsed.netloc.lower() and "product" in parts:
        index = parts.index("product")
        if len(parts) > index + 1:
            return slug_to_query(parts[index + 1])

    for part in parts:
        if part.lower() in URL_PATH_STOP_PARTS:
            continue
        if re.search(r"[a-zA-Zа-яА-Я]", part) and len(part) > 4:
            return slug_to_query(part)

    return None


def wildberries_product_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if "wildberries." not in host:
        return None

    match = re.search(r"/catalog/(\d+)(?:/|$)", parsed.path)
    if not match:
        return None
    return match.group(1)


def duckduckgo_real_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" not in parsed.netloc:
        return url
    params = parse_qs(parsed.query)
    target = params.get("uddg", [url])[0]
    return unquote(target)


def normalize_tokens(value: str) -> set[str]:
    tokens = re.findall(r"[a-zA-Zа-яА-Я0-9]{2,}", value.lower())
    normalized = {TOKEN_ALIASES.get(token, token) for token in tokens}
    return {token for token in normalized if token not in STOP_WORDS}


def token_overlap_score(query: str, title: str) -> float:
    query_tokens = normalize_tokens(query)
    if not query_tokens:
        return 0.0
    title_tokens = normalize_tokens(title)
    if not title_tokens:
        return 0.0
    overlap = query_tokens & title_tokens
    return len(overlap) / len(query_tokens)


def has_required_distinctive_terms(query: str, title: str) -> bool:
    required = _distinctive_query_tokens(query)
    if not required:
        return True
    title_tokens = normalize_tokens(title)
    return required.issubset(title_tokens)


def brand_matches(query: str, title: str) -> bool:
    query_tokens = normalize_tokens(query)
    if "dyson" not in query_tokens:
        return True

    leading_token = _first_meaningful_title_token(title)
    return leading_token in {None, "dyson"}


def has_required_numbers(query: str, title: str) -> bool:
    query_numbers = set(re.findall(r"\d+", query.lower()))
    if not query_numbers:
        return True
    title_numbers = set(re.findall(r"\d+", title.lower()))
    return query_numbers.issubset(title_numbers)


def has_required_model_phrases(query: str, title: str) -> bool:
    query_norm = _phrase_norm(query)
    title_norm = _phrase_norm(title)
    for phrase in ("pro max",):
        if phrase in query_norm and phrase not in title_norm:
            return False
    return True


def condition_matches(query: str, title: str) -> bool:
    if _mentions_used_or_refurbished(query):
        return True
    return not _mentions_used_or_refurbished(title)


def _distinctive_query_tokens(query: str) -> set[str]:
    tokens = normalize_tokens(query)
    strong_tokens = {
        token
        for token in tokens
        if token in {"dyson", "supersonic"}
        or (len(token) >= 6 and not token.isdigit() and not re.fullmatch(r"\d+gb", token))
    }
    return strong_tokens


def _first_meaningful_title_token(title: str) -> str | None:
    raw_tokens = re.findall(r"[a-zA-Zа-яА-Я0-9]{2,}", title.lower())
    for token in raw_tokens:
        normalized = TOKEN_ALIASES.get(token, token)
        if normalized in STOP_WORDS:
            continue
        return normalized
    return None


def _phrase_norm(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-zа-я0-9]+", " ", value)
    return " ".join(value.split())


def _mentions_used_or_refurbished(value: str) -> bool:
    normalized = _phrase_norm(value)
    markers = (
        "восстановлен",
        "refurbished",
        "renewed",
        "уценка",
        "уцененный",
        "уценённый",
        "б у",
        "бу",
    )
    return any(marker in normalized for marker in markers)


def extract_prices_rub(text: str) -> list[int]:
    normalized = html.unescape(text)
    patterns = [
        r"(?<!\d)(\d{1,3}(?:[\s\u00a0]\d{3})+|\d{3,8})(?:[,.]\d{1,2})?\s*(?:₽|руб\.?|р\b)",
        r"(?:₽|руб\.?)\s*(\d{1,3}(?:[\s\u00a0]\d{3})+|\d{3,8})(?:[,.]\d{1,2})?",
    ]
    prices: list[int] = []
    for pattern in patterns:
        for match in re.finditer(pattern, normalized, flags=re.IGNORECASE):
            raw = match.group(1)
            number = re.sub(r"[^\d]", "", raw)
            if not number:
                continue
            price = int(number)
            if 10 <= price <= 50_000_000:
                prices.append(price)
    return sorted(set(prices))


def format_price_rub(price: int | None) -> str:
    if price is None:
        return "цена не найдена"
    return f"{price:,}".replace(",", " ") + " ₽"
