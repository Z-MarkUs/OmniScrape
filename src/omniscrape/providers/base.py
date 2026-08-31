"""Provider protocol kept independent from any vendor SDK."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..models import ContentKind, ProviderResult


@runtime_checkable
class LLMProvider(Protocol):
    """An optional provider that turns already-fetched HTML into typed content."""

    @property
    def name(self) -> str: ...

    async def extract(self, *, html: str, url: str, kind: ContentKind) -> ProviderResult: ...
