"""Extraction orchestration with deterministic, LLM, and auto modes."""

from __future__ import annotations

import asyncio
import inspect
import math
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypeAlias

from pydantic import ValidationError

from ._tasking import MAX_TASK_CAPACITY, BoundedTaskSet, create_bounded_task
from .config import Settings
from .errors import BusyError, ExtractionError, ProviderError, ProviderUnavailableError
from .extractors import extract_heuristic, extract_readability, extract_structured
from .extractors.common import ExtractionCandidate, dedupe_strings
from .fetcher import AsyncFetcher, FetcherConfig
from .models import (
    Article,
    ContentKind,
    ExtractedData,
    ExtractionMetadata,
    ExtractionMode,
    ExtractionResult,
    Product,
    ProviderResult,
    utc_now,
)
from .providers.base import LLMProvider

ProgressCallback: TypeAlias = Callable[[str, Mapping[str, Any]], Awaitable[None] | None]
_MAX_DETERMINISTIC_MARKUP_TOKENS = 20_000
_GLOBAL_PARSE_TASKS = BoundedTaskSet(MAX_TASK_CAPACITY, label="Global parser")


async def _emit(callback: ProgressCallback | None, event: str, **payload: Any) -> None:
    if callback is None:
        return
    result = callback(event, payload)
    if inspect.isawaitable(result):
        await result


def _completeness(data: ExtractedData) -> float:
    if isinstance(data, Article):
        text_length = len(data.text or "")
        text_score = 0.0
        if text_length >= 800:
            text_score = 0.55
        elif text_length >= 200:
            text_score = 0.40
        elif text_length >= 50:
            text_score = 0.20
        return min(
            1.0,
            (0.20 if data.title else 0.0)
            + text_score
            + (0.08 if data.author else 0.0)
            + (0.07 if data.date_published else 0.0)
            + (0.05 if data.description else 0.0)
            + (0.05 if data.images else 0.0),
        )
    return min(
        1.0,
        (0.30 if data.name else 0.0)
        + (0.30 if data.price else 0.0)
        + (0.10 if data.currency else 0.0)
        + (0.15 if data.description else 0.0)
        + (0.10 if data.sku else 0.0)
        + (0.05 if data.images else 0.0),
    )


def _candidate_values(
    kind: ContentKind, url: str, candidates: list[ExtractionCandidate]
) -> dict[str, Any]:
    keys = (
        ("title", "author", "date_published", "text", "description")
        if kind is ContentKind.ARTICLE
        else ("name", "price", "currency", "sku", "description")
    )
    values: dict[str, Any] = {"kind": kind.value, "url": url, "images": []}
    for key in keys:
        available = [
            candidate.values.get(key) for candidate in candidates if candidate.values.get(key)
        ]
        if key == "text" and available:
            values[key] = max(available, key=lambda value: len(str(value)))
        else:
            values[key] = available[0] if available else None
    images: list[str] = []
    for candidate in candidates:
        images.extend(str(item) for item in candidate.values.get("images") or [])
    values["images"] = dedupe_strings(images)[:20]
    return values


def _build_data(
    kind: ContentKind, url: str, candidates: list[ExtractionCandidate]
) -> ExtractedData:
    values = _candidate_values(kind, url, candidates)
    try:
        if kind is ContentKind.ARTICLE:
            return Article.model_validate(values)
        return Product.model_validate(values)
    except ValidationError as exc:
        raise ExtractionError("Deterministic extractors produced invalid fields.") from exc


def _extract_local(
    html: str, url: str, kind: ContentKind
) -> tuple[ExtractedData, list[ExtractionCandidate], list[str]]:
    """Run CPU-bound parsers off the event loop and return stable warnings."""

    cursor = 0
    markup_tokens = 0
    while True:
        cursor = html.find("<", cursor)
        if cursor < 0:
            break
        following = html[cursor + 1 : cursor + 3]
        if following and (
            following[0].isalpha()
            or following[0] in {"!", "?"}
            or (following[0] == "/" and len(following) > 1 and following[1].isalpha())
        ):
            markup_tokens += 1
            if markup_tokens > _MAX_DETERMINISTIC_MARKUP_TOKENS:
                raise ExtractionError("The document exceeds the structural parsing limit.")
        cursor += 1

    candidates: list[ExtractionCandidate] = []
    warnings: list[str] = []
    layers = (
        ("structured", extract_structured),
        ("readability", extract_readability),
        ("heuristic", extract_heuristic),
    )
    for name, extractor in layers:
        try:
            candidate = extractor(html, url, kind)
        except Exception:
            warnings.append(f"{name} extractor skipped after a parse error")
            continue
        if candidate is not None:
            candidates.append(candidate)
    return _build_data(kind, url, candidates), candidates, warnings


def _merge_with_provider(local: ExtractedData, provider: ExtractedData) -> ExtractedData:
    """Keep strong local signals and use the provider to fill genuine gaps."""

    if local.kind is not provider.kind:
        raise ProviderError("The provider returned the wrong content kind.")
    local_values = local.model_dump(mode="json")
    provider_values = provider.model_dump(mode="json")
    for key, value in provider_values.items():
        if key in {"kind", "url"} or value in (None, "", []):
            continue
        if key == "images":
            local_values[key] = dedupe_strings([*(local_values.get(key) or []), *value])[:20]
        elif key == "text":
            if len(str(value)) > len(str(local_values.get(key) or "")):
                local_values[key] = value
        elif not local_values.get(key):
            local_values[key] = value
    if local.kind is ContentKind.ARTICLE:
        return Article.model_validate(local_values)
    return Product.model_validate(local_values)


class OmniScrape:
    """Reusable asynchronous extraction service.

    The constructor has no environment side effects. Use ``from_settings`` for
    explicit environment-backed composition or inject a fetcher/provider directly.
    """

    def __init__(
        self,
        *,
        fetcher: AsyncFetcher | None = None,
        provider: LLMProvider | None = None,
        auto_llm_threshold: float = 0.72,
        max_inflight_tasks: int = 8,
    ) -> None:
        if (
            isinstance(auto_llm_threshold, bool)
            or not isinstance(auto_llm_threshold, (int, float))
            or not math.isfinite(float(auto_llm_threshold))
        ):
            raise ValueError("auto_llm_threshold must be a finite number.")
        if (
            isinstance(max_inflight_tasks, bool)
            or not isinstance(max_inflight_tasks, int)
            or not 1 <= max_inflight_tasks <= MAX_TASK_CAPACITY
        ):
            raise ValueError(
                f"max_inflight_tasks must be an integer between 1 and {MAX_TASK_CAPACITY}."
            )
        self.fetcher = fetcher if fetcher is not None else AsyncFetcher()
        self.provider = provider
        self.auto_llm_threshold = min(max(auto_llm_threshold, 0.0), 1.0)
        self._parse_tasks = BoundedTaskSet(max_inflight_tasks, label="Parser")

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        fetcher: AsyncFetcher | None = None,
        provider: LLMProvider | None = None,
    ) -> OmniScrape:
        if fetcher is None:
            fetcher = AsyncFetcher(
                FetcherConfig(
                    connect_timeout_seconds=settings.connect_timeout_seconds,
                    read_timeout_seconds=settings.read_timeout_seconds,
                    total_timeout_seconds=settings.fetch_timeout_seconds,
                    max_response_bytes=settings.max_response_bytes,
                    max_redirects=settings.max_redirects,
                    user_agent=settings.user_agent,
                    render_timeout_ms=settings.render_timeout_ms,
                    max_render_requests=settings.max_render_requests,
                    max_render_nodes=settings.max_render_nodes,
                    max_inflight_tasks=settings.max_concurrency,
                    max_render_concurrency=settings.max_render_concurrency,
                    outbound_allowed_hosts=settings.outbound_allowed_hosts,
                )
            )
        if provider is None and settings.openai_api_key:
            from .providers.openai import OpenAIResponsesProvider

            provider = OpenAIResponsesProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                timeout_seconds=settings.provider_timeout_seconds,
                max_inflight_tasks=settings.max_concurrency,
            )
        return cls(
            fetcher=fetcher,
            provider=provider,
            auto_llm_threshold=settings.auto_llm_threshold,
            max_inflight_tasks=settings.max_concurrency,
        )

    async def __aenter__(self) -> OmniScrape:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        try:
            await self.fetcher.aclose()
        finally:
            close = getattr(self.provider, "aclose", None)
            if close is not None:
                result = close()
                if inspect.isawaitable(result):
                    await result

    async def extract(
        self,
        url: str,
        kind: ContentKind | str = ContentKind.ARTICLE,
        mode: ExtractionMode | str = ExtractionMode.DETERMINISTIC,
        *,
        render: bool = False,
        progress: ProgressCallback | None = None,
    ) -> ExtractionResult:
        started = time.perf_counter()
        kind = ContentKind(kind)
        mode = ExtractionMode(mode)
        await _emit(progress, "fetch_started", url=url, rendered=render)
        fetched = await self.fetcher.fetch(url, render=render)
        fetched_at = utc_now()
        await _emit(
            progress,
            "fetch_complete",
            final_url=str(fetched.final_url),
            status_code=fetched.status_code,
            content_bytes=fetched.byte_count,
            redirect_count=len(fetched.redirects),
            rendered=fetched.rendered,
        )

        extraction_started = time.perf_counter()
        parse_task = create_bounded_task(
            asyncio.to_thread(
                _extract_local,
                fetched.html,
                str(fetched.final_url),
                kind,
            ),
            registries=(self._parse_tasks, _GLOBAL_PARSE_TASKS),
            name="omniscrape-deterministic-extraction",
        )
        try:
            local, candidates, warnings = await asyncio.shield(parse_task)
        except asyncio.CancelledError:
            # The bounded registries retain the to_thread wrapper until the worker
            # really exits, while request cancellation can still return promptly.
            raise
        local_score = _completeness(local)
        sources = dedupe_strings([candidate.source for candidate in candidates])
        await _emit(
            progress,
            "deterministic_complete",
            sources=sources,
            completeness_score=round(local_score, 3),
        )

        provider_result: ProviderResult | None = None
        data = local
        should_call_provider = mode is ExtractionMode.LLM or (
            mode is ExtractionMode.AUTO and local_score < self.auto_llm_threshold
        )
        if should_call_provider:
            if self.provider is None:
                if mode is ExtractionMode.LLM:
                    raise ProviderUnavailableError()
                warnings.append("LLM fallback was unavailable; deterministic result returned")
            else:
                await _emit(progress, "provider_started", provider=self.provider.name)
                try:
                    received = await self.provider.extract(
                        html=fetched.html, url=str(fetched.final_url), kind=kind
                    )
                    if received.data.kind is not kind:
                        raise ProviderError("The provider returned the wrong content kind.")
                    if str(received.data.url) != str(fetched.final_url):
                        raise ProviderError("The provider returned the wrong source URL.")
                    provider_data = (
                        received.data
                        if mode is ExtractionMode.LLM
                        else _merge_with_provider(local, received.data)
                    )
                except (BusyError, ProviderError, ProviderUnavailableError):
                    if mode is ExtractionMode.LLM or local_score == 0:
                        raise
                    warnings.append("LLM fallback failed; deterministic result returned")
                else:
                    provider_result = received
                    data = provider_data
                    sources.append("llm")
                    await _emit(
                        progress,
                        "provider_complete",
                        provider=provider_result.provider,
                        model=provider_result.model,
                    )

        score = _completeness(data)
        if score == 0:
            raise ExtractionError()
        extraction_ms = (time.perf_counter() - extraction_started) * 1000
        metadata = ExtractionMetadata(
            sources=dedupe_strings(sources),
            fetched_at=fetched_at,
            http_status=fetched.status_code,
            content_bytes=fetched.byte_count,
            redirect_count=len(fetched.redirects),
            rendered=fetched.rendered,
            fetch_ms=fetched.elapsed_ms,
            extraction_ms=extraction_ms,
            total_ms=(time.perf_counter() - started) * 1000,
            completeness_score=score,
            provider=provider_result.provider if provider_result else None,
            model=provider_result.model if provider_result else None,
            token_usage=provider_result.token_usage if provider_result else None,
            warnings=warnings,
        )
        result = ExtractionResult.model_validate(
            {
                "url": url,
                "final_url": fetched.final_url,
                "kind": kind,
                "mode": mode,
                "data": data,
                "metadata": metadata,
            }
        )
        await _emit(
            progress,
            "finished",
            sources=metadata.sources,
            completeness_score=round(score, 3),
        )
        return result


async def extract(
    url: str,
    kind: ContentKind | str = ContentKind.ARTICLE,
    mode: ExtractionMode | str = ExtractionMode.DETERMINISTIC,
    *,
    render: bool = False,
    provider: LLMProvider | None = None,
    fetcher: AsyncFetcher | None = None,
    settings: Settings | None = None,
    progress: ProgressCallback | None = None,
) -> ExtractionResult:
    """One-shot convenience API; use :class:`OmniScrape` for repeated work."""

    resolved_settings = settings if settings is not None else Settings.from_env()
    service = OmniScrape.from_settings(resolved_settings, fetcher=fetcher, provider=provider)
    try:
        return await service.extract(url, kind, mode, render=render, progress=progress)
    finally:
        await service.aclose()


__all__ = ["LLMProvider", "OmniScrape", "ProgressCallback", "extract"]
