from __future__ import annotations

from .config import Config
from .extractor import ProductQueryExtractor
from .http_client import HttpClient
from .models import PriceSearchResult, ProductCandidate
from .providers import WildberriesProvider, build_default_providers


class PriceSearchService:
    def __init__(self, config: Config):
        self.config = config
        self.http = HttpClient(timeout_seconds=config.http_timeout_seconds)
        self.extractor = ProductQueryExtractor(self.http, wb_dest=config.wb_dest)
        self.providers = build_default_providers(self.http, config)

    def search_from_text(self, text: str) -> PriceSearchResult:
        product = self.extractor.extract(text)
        all_candidates: list[ProductCandidate] = []
        warnings: list[str] = []

        source_candidate = self._source_candidate(product.source_url)
        if source_candidate:
            all_candidates.append(source_candidate)

        for provider in self.providers:
            marketplace_result = provider.search(product.query, self.config.market_price_limit)
            all_candidates.extend(marketplace_result.candidates)
            if marketplace_result.warning:
                warnings.append(marketplace_result.warning)

        ranked = rank_candidates(all_candidates, self.config.market_price_limit)
        return PriceSearchResult(
            query=product.query,
            source_url=product.source_url,
            candidates=ranked,
            warnings=warnings,
        )

    def _source_candidate(self, source_url: str | None) -> ProductCandidate | None:
        if not source_url:
            return None
        for provider in self.providers:
            if isinstance(provider, WildberriesProvider):
                return provider.product_from_url(source_url)
        return None


def rank_candidates(candidates: list[ProductCandidate], limit: int) -> list[ProductCandidate]:
    seen: set[tuple[str, str]] = set()
    unique: list[ProductCandidate] = []

    for candidate in candidates:
        key = (candidate.marketplace.lower(), candidate.url.split("?")[0].rstrip("/").lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)

    unique.sort(
        key=lambda item: (
            item.price_rub is None,
            item.price_rub or 0,
            -(item.rating or 0),
            -(item.reviews_count or 0),
            -item.confidence,
            item.marketplace,
        )
    )
    return unique[:limit]
