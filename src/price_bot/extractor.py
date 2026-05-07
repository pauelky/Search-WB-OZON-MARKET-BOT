from __future__ import annotations

import re
from dataclasses import dataclass

from .http_client import FetchError, HttpClient
from .text_utils import clean_product_title, first_url, query_from_url_path, strip_tags


@dataclass(frozen=True)
class ProductQuery:
    query: str
    source_url: str | None = None


class ProductQueryExtractor:
    def __init__(self, http: HttpClient):
        self.http = http

    def extract(self, text: str) -> ProductQuery:
        url = first_url(text)
        if not url:
            return ProductQuery(clean_product_title(text) or text.strip())

        from_path = query_from_url_path(url)
        if from_path:
            return ProductQuery(from_path, source_url=url)

        from_page = self._query_from_page(url)
        if from_page:
            return ProductQuery(from_page, source_url=url)

        return ProductQuery(url, source_url=url)

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
