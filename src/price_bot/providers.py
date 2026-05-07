from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from urllib.parse import quote, urlencode, urljoin, urlparse
from urllib.parse import parse_qsl

from .config import Config
from .http_client import FetchError, HttpClient
from .models import MarketplaceSearch, ProductCandidate
from .text_utils import (
    clean_product_title,
    brand_matches,
    condition_matches,
    duckduckgo_real_url,
    extract_prices_rub,
    has_required_model_phrases,
    has_required_distinctive_terms,
    has_required_numbers,
    strip_tags,
    token_overlap_score,
    wildberries_product_id,
)


class MarketplaceProvider:
    marketplace = "unknown"

    def search(self, query: str, limit: int) -> MarketplaceSearch:
        raise NotImplementedError


class WildberriesProvider(MarketplaceProvider):
    marketplace = "Wildberries"

    def __init__(self, http: HttpClient, config: Config):
        self.http = http
        self.config = config

    def search(self, query: str, limit: int) -> MarketplaceSearch:
        params = {
            "appType": "1",
            "curr": "rub",
            "dest": self.config.wb_dest,
            "query": query,
            "resultset": "catalog",
            "sort": "priceup",
            "spp": "30",
            "suppressSpellcheck": "false",
            "page": "1",
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "x-userid": "0",
            "x-queryid": uuid.uuid4().hex,
        }
        payload = None
        errors: list[str] = []
        endpoints = (
            ("common", "v5"),
            ("female", "v5"),
            ("male", "v5"),
            ("common", "v13"),
        )
        for segment, version in endpoints:
            headers["x-queryid"] = uuid.uuid4().hex
            url = f"https://search.wb.ru/exactmatch/ru/{segment}/{version}/search?" + urlencode(params)
            try:
                payload = self.http.get_json(url, headers=headers)
            except FetchError as exc:
                errors.append(f"{segment}/{version}: {exc}")
                continue
            if _wb_products_from_payload(payload):
                break

        if payload is None:
            return MarketplaceSearch(
                self.marketplace,
                warning=f"Wildberries public search недоступен ({'; '.join(errors)}).",
            )

        products = _wb_products_from_payload(payload)
        if not products and isinstance(payload, dict):
            products = self._load_wb_catalog_payload(payload, headers)

        candidates: list[ProductCandidate] = []
        for item in products:
            candidate = _wb_candidate_from_item(item, query, self.marketplace)
            if not candidate:
                continue
            candidates.append(candidate)
            if len(candidates) >= limit:
                break

        return MarketplaceSearch(self.marketplace, candidates=candidates)

    def product_from_url(self, url: str) -> ProductCandidate | None:
        nm_id = wildberries_product_id(url)
        if not nm_id:
            return None
        product = self._load_wb_product(nm_id)
        if not product:
            return None
        return _wb_candidate_from_item(product, "", self.marketplace, min_score=0.0)

    def _load_wb_product(self, nm_id: str) -> dict[str, object] | None:
        api_url = (
            "https://card.wb.ru/cards/v4/detail"
            f"?appType=1&curr=rub&dest={self.config.wb_dest}&spp=30&nm={nm_id}"
        )
        headers = {
            "Accept": "application/json",
            "User-Agent": "Wildberries/6.6.0 (iPhone; iOS 17.0)",
            "x-userid": "0",
            "x-queryid": "market-price-bot",
        }
        try:
            payload = self.http.get_json(api_url, headers=headers)
        except FetchError:
            return None

        products = _wb_products_from_payload(payload)
        return products[0] if products else None

    def _load_wb_catalog_payload(self, payload: dict[str, object], headers: dict[str, str]) -> list[dict[str, object]]:
        shard_key = payload.get("shardKey")
        query_string = payload.get("query")
        if not isinstance(shard_key, str) or not isinstance(query_string, str):
            return []

        catalog_params = {
            "appType": "1",
            "curr": "rub",
            "dest": self.config.wb_dest,
            "sort": "priceup",
            "spp": "30",
            "page": "1",
        }
        catalog_params.update(dict(parse_qsl(query_string)))
        url = f"https://catalog.wb.ru/catalog/{shard_key}/catalog?" + urlencode(catalog_params)
        try:
            catalog_payload = self.http.get_json(url, headers=headers)
        except FetchError:
            return []

        return _wb_products_from_payload(catalog_payload)


def _wb_products_from_payload(payload: object) -> list[dict[str, object]]:
    products = []
    if isinstance(payload, dict):
        if isinstance(payload.get("products"), list):
            products = payload["products"]
        data = payload.get("data")
        if isinstance(data, dict) and isinstance(data.get("products"), list):
            products = data["products"]
        search_result = payload.get("search_result")
        if isinstance(search_result, dict) and isinstance(search_result.get("products"), list):
            products = search_result["products"]
    return [item for item in products if isinstance(item, dict)]


def _wb_candidate_from_item(
    item: dict[str, object],
    query: str,
    marketplace: str,
    min_score: float = 0.2,
) -> ProductCandidate | None:
    nm_id = item.get("id")
    name = str(item.get("name") or "").strip()
    brand = str(item.get("brand") or "").strip()
    title = clean_product_title(f"{brand} {name}".strip())
    if not title:
        return None

    price = _wb_price(item)
    score = token_overlap_score(query, title) if query else 1.0
    if query and (
        not has_required_numbers(query, title)
        or not has_required_model_phrases(query, title)
        or not has_required_distinctive_terms(query, title)
        or not brand_matches(query, title)
        or not condition_matches(query, title)
    ):
        return None
    if score < min_score:
        return None

    quantity = item.get("totalQuantity")
    available = price is not None
    if isinstance(quantity, (int, float)):
        available = quantity > 0 and price is not None

    return ProductCandidate(
        marketplace=marketplace,
        title=title,
        price_rub=price,
        url=f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
        available=available,
        confidence=min(1.0, 0.35 + score),
        note="WB catalog endpoint",
    )


def _wb_price(item: dict[str, object]) -> int | None:
    for key in ("salePriceU", "priceU"):
        value = item.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return round(value / 100)

    for key in ("salePrice", "price"):
        value = item.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return round(value)

    sizes = item.get("sizes")
    if isinstance(sizes, list):
        prices = []
        for size in sizes:
            if not isinstance(size, dict):
                continue
            price_block = size.get("price")
            if not isinstance(price_block, dict):
                continue
            for key in ("product", "total", "basic"):
                value = price_block.get(key)
                if isinstance(value, (int, float)) and value > 0:
                    prices.append(round(value / 100))
        if prices:
            return min(prices)

    return None


@dataclass(frozen=True)
class MarketplaceSearchConfig:
    name: str
    domain: str
    product_path_hint: str
    search_url_template: str
    query_suffix: str


class YandexMarketProvider(MarketplaceProvider):
    marketplace = "Яндекс Маркет"

    def __init__(self, http: HttpClient):
        self.http = http

    def search(self, query: str, limit: int) -> MarketplaceSearch:
        search_url = "https://market.yandex.ru/search?" + urlencode({"text": query, "how": "aprice"})
        try:
            response = self.http.get_text(search_url)
        except FetchError as exc:
            return MarketplaceSearch(
                self.marketplace,
                candidates=[self._fallback_candidate(query)],
                warning=f"Яндекс Маркет: поиск недоступен ({exc}).",
            )

        candidates = self._parse_cards(response.text, query, limit)
        if not candidates:
            candidates.append(self._fallback_candidate(query))
        return MarketplaceSearch(self.marketplace, candidates=candidates)

    def _parse_cards(self, html: str, query: str, limit: int) -> list[ProductCandidate]:
        anchor_matches = [
            match
            for match in re.finditer(
                r'<a\s+href="([^"]+)"[^>]+data-auto="snippet-link"[^>]*>(.*?)</a>',
                html,
                re.IGNORECASE | re.DOTALL,
            )
            if 'data-auto="snippet-title"' in match.group(2)
        ]
        candidates: list[ProductCandidate] = []
        seen_urls: set[str] = set()

        for index, anchor_match in enumerate(anchor_matches):
            block_end = anchor_matches[index + 1].start() if index + 1 < len(anchor_matches) else anchor_match.end() + 8000
            block = html[anchor_match.start():block_end]
            title_match = re.search(
                r'data-auto="snippet-title"[^>]+title="([^"]+)"',
                block,
                re.IGNORECASE | re.DOTALL,
            )
            if not title_match:
                continue

            url = urljoin("https://market.yandex.ru", anchor_match.group(1).replace("&amp;", "&"))
            clean_url = url.split("#")[0].split("?")[0]
            if clean_url in seen_urls:
                continue

            title = clean_product_title(title_match.group(1))
            score = token_overlap_score(query, title)
            if (
                not has_required_numbers(query, title)
                or not has_required_model_phrases(query, title)
                or not has_required_distinctive_terms(query, title)
                or not brand_matches(query, title)
                or not condition_matches(query, title)
            ):
                continue
            if score < 0.45:
                continue

            visible_text = strip_tags(block)
            price = _yandex_market_price(visible_text)
            seen_urls.add(clean_url)
            candidates.append(
                ProductCandidate(
                    marketplace=self.marketplace,
                    title=title,
                    url=clean_url,
                    price_rub=price,
                    available=None if price is None else True,
                    confidence=min(1.0, 0.4 + score),
                    note="market search page",
                )
            )
            if len(candidates) >= limit:
                break

        candidates.sort(key=lambda item: (item.price_rub is None, item.price_rub or 0, -item.confidence))
        return candidates

    def _fallback_candidate(self, query: str) -> ProductCandidate:
        return ProductCandidate(
            marketplace=self.marketplace,
            title=f"Открыть поиск: {query}",
            url="https://market.yandex.ru/search?" + urlencode({"text": query, "how": "aprice"}),
            price_rub=None,
            available=None,
            confidence=0.0,
            note="fallback search link",
        )


def _yandex_market_price(text: str) -> int | None:
    labels = ("Цена с картой", "Цена")
    for label in labels:
        index = text.find(label)
        if index == -1:
            continue
        window = text[index : index + 180]
        match = re.search(
            r"(\d{1,3}(?:[\s\u00a0]\d{3})+|\d{3,8})(?:[,.]\d{1,2})?\s*₽",
            window,
        )
        if match:
            return _parse_price_number(match.group(1))

    for price in extract_prices_rub(text):
        if price > 1_000:
            return price
    return None


def _parse_price_number(raw: str) -> int:
    return int(re.sub(r"[^\d]", "", raw))


class DuckDuckGoMarketplaceProvider(MarketplaceProvider):
    def __init__(self, http: HttpClient, marketplace: MarketplaceSearchConfig):
        self.http = http
        self.marketplace = marketplace.name
        self.marketplace_config = marketplace

    def search(self, query: str, limit: int) -> MarketplaceSearch:
        ddg_query = f"{query} {self.marketplace_config.query_suffix}"
        url = "https://html.duckduckgo.com/html/?" + urlencode({"q": ddg_query})

        try:
            response = self.http.get_text(url)
        except FetchError as exc:
            fallback = self._fallback_candidate(query)
            return MarketplaceSearch(
                self.marketplace,
                candidates=[fallback],
                warning=f"{self.marketplace}: web search недоступен ({exc}).",
            )

        candidates = self._parse_results(response.text, query, limit)
        if not candidates:
            candidates.append(self._fallback_candidate(query))
        return MarketplaceSearch(self.marketplace, candidates=candidates)

    def _parse_results(self, html: str, query: str, limit: int) -> list[ProductCandidate]:
        blocks = re.split(r'<div class="result results_links', html)
        candidates: list[ProductCandidate] = []
        seen_urls: set[str] = set()

        for block in blocks[1:]:
            anchor = re.search(
                r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                block,
                flags=re.IGNORECASE | re.DOTALL,
            )
            if not anchor:
                continue

            real_url = duckduckgo_real_url(anchor.group(1))
            if real_url in seen_urls or not self._is_marketplace_url(real_url):
                continue

            title = clean_product_title(strip_tags(anchor.group(2)))
            if not title:
                continue

            snippet = self._extract_snippet(block)
            score = token_overlap_score(query, f"{title} {snippet}")
            if (
                not has_required_numbers(query, title)
                or not has_required_model_phrases(query, title)
                or not has_required_distinctive_terms(query, title)
                or not brand_matches(query, title)
                or not condition_matches(query, title)
            ):
                continue
            if score < 0.18:
                continue

            prices = extract_prices_rub(f"{title} {snippet}")
            price = prices[0] if prices else None
            seen_urls.add(real_url)
            candidates.append(
                ProductCandidate(
                    marketplace=self.marketplace,
                    title=title,
                    url=real_url,
                    price_rub=price,
                    available=None if price is None else True,
                    confidence=min(1.0, 0.25 + score),
                    note="web-search snippet" if price else "search result without parsed price",
                )
            )
            if len(candidates) >= limit:
                break

        candidates.sort(key=lambda item: (item.price_rub is None, item.price_rub or 0, -item.confidence))
        return candidates

    def _extract_snippet(self, block: str) -> str:
        patterns = [
            r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
            r'<div[^>]+class="result__snippet"[^>]*>(.*?)</div>',
        ]
        for pattern in patterns:
            match = re.search(pattern, block, flags=re.IGNORECASE | re.DOTALL)
            if match:
                return strip_tags(match.group(1))
        return ""

    def _is_marketplace_url(self, url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if self.marketplace_config.domain not in host:
            return False
        if self.marketplace_config.product_path_hint:
            return self.marketplace_config.product_path_hint in parsed.path.lower()
        return True

    def _fallback_candidate(self, query: str) -> ProductCandidate:
        url = self.marketplace_config.search_url_template.format(query=quote(query))
        return ProductCandidate(
            marketplace=self.marketplace,
            title=f"Открыть поиск: {query}",
            url=url,
            price_rub=None,
            available=None,
            confidence=0.0,
            note="fallback search link",
        )


def build_default_providers(http: HttpClient, config: Config) -> list[MarketplaceProvider]:
    return [
        WildberriesProvider(http, config),
        YandexMarketProvider(http),
        DuckDuckGoMarketplaceProvider(
            http,
            MarketplaceSearchConfig(
                name="Ozon",
                domain="ozon.ru",
                product_path_hint="/product/",
                search_url_template="https://www.ozon.ru/search/?text={query}&sorting=price",
                query_suffix="ozon",
            ),
        ),
        DuckDuckGoMarketplaceProvider(
            http,
            MarketplaceSearchConfig(
                name="Wildberries Web",
                domain="wildberries.ru",
                product_path_hint="/catalog/",
                search_url_template="https://www.wildberries.ru/catalog/0/search.aspx?search={query}&sort=priceup",
                query_suffix="wildberries",
            ),
        ),
    ]
