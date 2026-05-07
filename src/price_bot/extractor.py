from __future__ import annotations

import re
from dataclasses import dataclass

from .http_client import FetchError, HttpClient
from .text_utils import clean_product_title, first_url, query_from_url_path, strip_tags, wildberries_product_id


@dataclass(frozen=True)
class ProductQuery:
    query: str
    source_url: str | None = None


class ProductQueryExtractor:
    def __init__(self, http: HttpClient, wb_dest: str = "-1257786"):
        self.http = http
        self.wb_dest = wb_dest

    def extract(self, text: str) -> ProductQuery:
        url = first_url(text)
        if not url:
            return ProductQuery(clean_product_title(text) or text.strip())

        wb_id = wildberries_product_id(url)
        if wb_id:
            from_wb = self._query_from_wildberries_product(wb_id)
            if from_wb:
                return ProductQuery(from_wb, source_url=url)

        from_path = query_from_url_path(url)
        if from_path:
            return ProductQuery(from_path, source_url=url)

        from_page = self._query_from_page(url)
        if from_page:
            return ProductQuery(from_page, source_url=url)

        return ProductQuery(url, source_url=url)

    def _query_from_wildberries_product(self, nm_id: str) -> str | None:
        api_url = (
            "https://card.wb.ru/cards/v4/detail"
            f"?appType=1&curr=rub&dest={self.wb_dest}&spp=30&nm={nm_id}"
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

        if not isinstance(payload, dict):
            return None
        products = payload.get("products")
        if not isinstance(products, list) or not products:
            return None
        product = products[0]
        if not isinstance(product, dict):
            return None

        brand = str(product.get("brand") or "").strip()
        name = str(product.get("name") or "").strip()
        title = clean_product_title(f"{brand} {name}".strip())
        return title or None

    def _query_from_page(self, url: str) -> str | None:
        try:
            response = self.http.get_text(url)
        except FetchError:
            return None

        html = response.text
        patterns = [
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
            r'<meta[^>]+name=["\']title["\'][^>]+content=["\']([^"\']+)["\']',
            r"<title[^>]*>(.*?)</title>",
        ]
        for pattern in patterns:
            match = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
            if not match:
                continue
            title = clean_product_title(strip_tags(match.group(1)))
            if title and len(title) >= 3:
                return title
        return None
