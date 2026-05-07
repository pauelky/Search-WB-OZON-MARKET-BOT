from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProductCandidate:
    marketplace: str
    title: str
    url: str
    price_rub: int | None = None
    available: bool | None = None
    confidence: float = 0.0
    note: str | None = None


@dataclass
class MarketplaceSearch:
    marketplace: str
    candidates: list[ProductCandidate] = field(default_factory=list)
    warning: str | None = None


@dataclass
class PriceSearchResult:
    query: str
    source_url: str | None
    candidates: list[ProductCandidate]
    warnings: list[str] = field(default_factory=list)
