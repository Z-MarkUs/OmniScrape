"""End-to-end orchestration tests with fetcher and provider test doubles."""

from __future__ import annotations

import asyncio
import builtins
import threading
import time
from collections.abc import Awaitable, Mapping
from typing import Any

import pytest

from omniscrape.config import Settings
from omniscrape.errors import BusyError, ExtractionError, ProviderError, ProviderUnavailableError
from omniscrape.fetcher import FetchResult
from omniscrape.models import (
    Article,
    ContentKind,
    Product,
    ProviderResult,
    TokenUsage,
)
from omniscrape.pipeline import OmniScrape
from omniscrape.pipeline import extract as extract_once
from omniscrape.providers.openai import OpenAIResponsesProvider


class FixtureFetcher:
    def __init__(self, html: str, final_url: str) -> None:
        self.html = html
        self.final_url = final_url
        self.calls: list[tuple[str, bool]] = []
        self.closed = False

    async def fetch(self, url: str, *, render: bool = False) -> FetchResult:
        self.calls.append((url, render))
        return FetchResult(
            requested_url=url,
            final_url=self.final_url,
            status_code=200,
            html=self.html,
            content_type="text/html",
            encoding="utf-8",
            byte_count=len(self.html.encode()),
            elapsed_ms=2.5,
            rendered=render,
        )

    async def aclose(self) -> None:
        self.closed = True


class FixtureProvider:
    name = "fixture-provider"

    def __init__(self, result: ProviderResult) -> None:
        self.result = result
        self.calls: list[tuple[str, str, ContentKind]] = []
        self.closed = False

    async def extract(self, *, html: str, url: str, kind: ContentKind) -> ProviderResult:
        self.calls.append((html, url, kind))
        return self.result

    async def aclose(self) -> None:
        self.closed = True


class ClosableOpenAIClient:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("auto_llm_threshold", True),
        ("auto_llm_threshold", float("nan")),
        ("max_inflight_tasks", True),
        ("max_inflight_tasks", 33),
    ],
)
def test_service_rejects_invalid_direct_resource_limits(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        OmniScrape(**{field: value})  # type: ignore[arg-type]


def test_settings_forward_render_concurrency_to_fetcher() -> None:
    service = OmniScrape.from_settings(Settings(max_render_concurrency=1))
    assert service.fetcher.config.max_render_concurrency == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_article_pipeline_merges_deterministic_layers(article_html: str) -> None:
    url = "https://news.example.test/stories/solar-workshop"
    fetcher = FixtureFetcher(article_html, url)
    service = OmniScrape(fetcher=fetcher)  # type: ignore[arg-type]

    result = await service.extract(url, kind="article", mode="deterministic")

    assert isinstance(result.data, Article)
    assert result.data.title == "Harbor Lab Opens a Solar Workshop"
    assert result.data.author == "Avery Chen"
    assert "safe wiring" in (result.data.text or "")
    assert [str(image) for image in result.data.images] == [
        "https://cdn.example.test/images/solar-workshop.jpg"
    ]
    assert result.metadata.sources == ["json-ld", "readability", "heuristic"]
    assert result.metadata.token_usage is None
    assert result.metadata.provider is None
    assert fetcher.calls == [(url, False)]


@pytest.mark.asyncio
async def test_product_pipeline_preserves_price_as_source_string(product_html: str) -> None:
    url = "https://shop.example.test/products/field-notes-lamp"
    result = await OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher(product_html, url)
    ).extract(url, kind="product", mode="deterministic")

    assert isinstance(result.data, Product)
    assert result.data.name == "Field Notes Lamp"
    assert result.data.price == "49.90"
    assert result.data.currency == "USD"
    assert result.data.sku == "FNL-2048-BLU"
    assert result.metadata.completeness_score == 1.0


@pytest.mark.asyncio
async def test_deterministic_mode_never_calls_provider() -> None:
    url = "https://safe.example.test/minimal"
    provider = FixtureProvider(
        ProviderResult(
            data=Article(url=url, title="Provider title"),
            provider="fixture-provider",
            model="fixture-model",
        )
    )
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<h1>Local title</h1>", url),
        provider=provider,
    )

    result = await service.extract(url, mode="deterministic")
    assert result.data.title == "Local title"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_client_default_mode_is_deterministic() -> None:
    url = "https://safe.example.test/minimal"
    provider = FixtureProvider(
        ProviderResult(
            data=Article(url=url, title="Provider title"),
            provider="fixture-provider",
            model="fixture-model",
        )
    )
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<h1>Local title</h1>", url),
        provider=provider,
    )

    result = await service.extract(url)

    assert result.mode.value == "deterministic"
    assert result.data.title == "Local title"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_convenience_default_does_not_load_openai_for_ambient_key(
    monkeypatch: Any,
) -> None:
    url = "https://safe.example.test/minimal"
    fetcher = FixtureFetcher("<h1>Local title</h1>", url)
    vendor_imports: list[str] = []
    original_import = builtins.__import__

    def reject_openai(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "openai":
            vendor_imports.append(name)
            raise ImportError("optional SDK intentionally unavailable")
        return original_import(name, *args, **kwargs)

    monkeypatch.setenv("OPENAI_API_KEY", "fixture-ambient-key")
    monkeypatch.setattr(builtins, "__import__", reject_openai)

    result = await extract_once(url, fetcher=fetcher)  # type: ignore[arg-type]

    assert result.mode.value == "deterministic"
    assert result.data.title == "Local title"
    assert vendor_imports == []
    assert fetcher.closed is True


@pytest.mark.asyncio
async def test_auto_mode_calls_provider_only_below_threshold() -> None:
    url = "https://safe.example.test/minimal"
    provider = FixtureProvider(
        ProviderResult(
            data=Article(
                url=url,
                title="Provider title",
                author="Provider Author",
                text="Provider supplied text " * 20,
            ),
            provider="fixture-provider",
            model="fixture-model",
            token_usage=TokenUsage(input_tokens=20, output_tokens=10, total_tokens=30),
        )
    )
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<h1>Local title</h1>", url),
        provider=provider,
        auto_llm_threshold=0.9,
    )

    result = await service.extract(url, mode="auto")

    assert len(provider.calls) == 1
    assert result.data.title == "Local title"
    assert result.data.author == "Provider Author"
    assert result.metadata.provider == "fixture-provider"
    assert result.metadata.token_usage is not None
    assert result.metadata.token_usage.total_tokens == 30
    assert result.metadata.sources[-1] == "llm"


@pytest.mark.asyncio
async def test_auto_mode_skips_provider_for_complete_fixture(article_html: str) -> None:
    url = "https://news.example.test/stories/solar-workshop"
    provider = FixtureProvider(
        ProviderResult(
            data=Article(url=url, title="Should not be used"),
            provider="fixture-provider",
            model="fixture-model",
        )
    )
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher(article_html, url),
        provider=provider,
        auto_llm_threshold=0.7,
    )

    result = await service.extract(url, mode="auto")
    assert result.data.title == "Harbor Lab Opens a Solar Workshop"
    assert provider.calls == []


@pytest.mark.asyncio
async def test_wrong_kind_provider_result_is_stable_in_llm_and_auto_modes() -> None:
    url = "https://safe.example.test/minimal"
    provider = FixtureProvider(
        ProviderResult(
            data=Product(url=url, name="Wrong kind"),
            provider="fixture-provider",
            model="fixture-model",
        )
    )
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<h1>Local article</h1>", url),
        provider=provider,
        auto_llm_threshold=0.9,
    )

    with pytest.raises(ProviderError, match="wrong content kind"):
        await service.extract(url, kind="article", mode="llm")

    result = await service.extract(url, kind="article", mode="auto")
    assert isinstance(result.data, Article)
    assert result.data.title == "Local article"
    assert result.metadata.provider is None
    assert result.metadata.warnings == ["LLM fallback failed; deterministic result returned"]


@pytest.mark.asyncio
async def test_wrong_url_provider_result_is_stable_in_llm_and_auto_modes() -> None:
    url = "https://safe.example.test/minimal"
    provider = FixtureProvider(
        ProviderResult(
            data=Article(url="https://other.example.test/contradiction", title="Wrong URL"),
            provider="fixture-provider",
            model="fixture-model",
        )
    )
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<h1>Local article</h1>", url),
        provider=provider,
        auto_llm_threshold=0.9,
    )

    with pytest.raises(ProviderError, match="wrong source URL"):
        await service.extract(url, kind="article", mode="llm")

    result = await service.extract(url, kind="article", mode="auto")
    assert isinstance(result.data, Article)
    assert str(result.data.url) == url
    assert result.metadata.provider is None
    assert result.metadata.warnings == ["LLM fallback failed; deterministic result returned"]


@pytest.mark.asyncio
async def test_busy_provider_falls_back_in_auto_but_surfaces_in_llm() -> None:
    class BusyProvider:
        name = "busy-provider"

        async def extract(self, **_kwargs: Any) -> ProviderResult:
            raise BusyError("provider cleanup capacity")

    url = "https://safe.example.test/minimal"
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<h1>Local article</h1>", url),
        provider=BusyProvider(),  # type: ignore[arg-type]
        auto_llm_threshold=0.9,
    )

    result = await service.extract(url, mode="auto")
    assert result.data.title == "Local article"
    assert result.metadata.warnings == ["LLM fallback failed; deterministic result returned"]

    with pytest.raises(BusyError, match="provider cleanup capacity"):
        await service.extract(url, mode="llm")


@pytest.mark.asyncio
async def test_cpu_bound_parsing_does_not_block_event_loop(monkeypatch: Any) -> None:
    from omniscrape import pipeline as pipeline_module

    original = pipeline_module._extract_local

    def slow_extract(*args: Any, **kwargs: Any):
        time.sleep(0.2)
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline_module, "_extract_local", slow_extract)
    url = "https://safe.example.test/minimal"
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<h1>Local article</h1>", url)
    )
    task = asyncio.create_task(service.extract(url))
    started = asyncio.get_running_loop().time()
    await asyncio.sleep(0.02)
    elapsed = asyncio.get_running_loop().time() - started

    assert elapsed < 0.1
    assert task.done() is False
    assert (await task).data.title == "Local article"


@pytest.mark.asyncio
async def test_cancelled_parser_retains_capacity_until_worker_exits(monkeypatch: Any) -> None:
    from omniscrape import pipeline as pipeline_module

    original = pipeline_module._extract_local
    worker_started = threading.Event()
    release_worker = threading.Event()
    starts = 0

    def blocked_extract(*args: Any, **kwargs: Any):
        nonlocal starts
        starts += 1
        worker_started.set()
        assert release_worker.wait(timeout=2)
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline_module, "_extract_local", blocked_extract)
    url = "https://safe.example.test/minimal"
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<h1>Local article</h1>", url),
        max_inflight_tasks=1,
    )
    first = asyncio.create_task(service.extract(url))
    try:
        for _ in range(100):
            if worker_started.is_set():
                break
            await asyncio.sleep(0.005)
        assert worker_started.is_set()

        first.cancel()
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

        assert service._parse_tasks.outstanding == 1
        with pytest.raises(BusyError, match="Parser cleanup capacity"):
            await service.extract(url)
        assert starts == 1
    finally:
        release_worker.set()
        for _ in range(100):
            if service._parse_tasks.outstanding == 0:
                break
            await asyncio.sleep(0.005)

    assert service._parse_tasks.outstanding == 0


@pytest.mark.asyncio
async def test_deterministic_parser_rejects_excessive_markup_before_layers(
    monkeypatch: Any,
) -> None:
    from omniscrape import pipeline as pipeline_module

    calls: list[str] = []

    def unexpected_layer(*_args: Any, **_kwargs: Any) -> None:
        calls.append("called")

    monkeypatch.setattr(pipeline_module, "extract_structured", unexpected_layer)
    monkeypatch.setattr(pipeline_module, "extract_readability", unexpected_layer)
    monkeypatch.setattr(pipeline_module, "extract_heuristic", unexpected_layer)
    html = "<i></i>" * (pipeline_module._MAX_DETERMINISTIC_MARKUP_TOKENS // 2 + 1)
    url = "https://safe.example.test/markup"
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher(html, url)
    )

    with pytest.raises(ExtractionError, match="structural parsing limit"):
        await service.extract(url)

    assert calls == []


def test_falsey_injected_fetcher_is_preserved() -> None:
    class FalseyFetcher(FixtureFetcher):
        def __bool__(self) -> bool:
            return False

    fetcher = FalseyFetcher("<h1>Fixture</h1>", "https://safe.example.test/")
    service = OmniScrape(fetcher=fetcher)  # type: ignore[arg-type]
    assert service.fetcher is fetcher


@pytest.mark.asyncio
async def test_llm_mode_requires_an_explicit_provider() -> None:
    url = "https://safe.example.test/minimal"
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<h1>Local title</h1>", url)
    )
    with pytest.raises(ProviderUnavailableError):
        await service.extract(url, mode="llm")


@pytest.mark.asyncio
async def test_empty_document_is_an_extraction_error() -> None:
    url = "https://safe.example.test/empty"
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher("<html><body></body></html>", url)
    )
    with pytest.raises(ExtractionError):
        await service.extract(url, mode="deterministic")


@pytest.mark.asyncio
async def test_progress_events_are_ordered_and_real(article_html: str) -> None:
    url = "https://news.example.test/stories/solar-workshop"
    events: list[tuple[str, Mapping[str, Any]]] = []

    def progress(event: str, data: Mapping[str, Any]) -> Awaitable[None] | None:
        events.append((event, data))
        return None

    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=FixtureFetcher(article_html, url)
    )
    await service.extract(url, mode="deterministic", progress=progress)

    assert [event for event, _ in events] == [
        "fetch_started",
        "fetch_complete",
        "deterministic_complete",
        "finished",
    ]
    assert events[1][1]["content_bytes"] == len(article_html.encode())


@pytest.mark.asyncio
async def test_context_manager_closes_injected_components() -> None:
    url = "https://safe.example.test/minimal"
    fetcher = FixtureFetcher("<h1>Local title</h1>", url)
    provider = FixtureProvider(
        ProviderResult(
            data=Article(url=url, title="Provider title"),
            provider="fixture-provider",
            model="fixture-model",
        )
    )
    async with OmniScrape(  # type: ignore[arg-type]
        fetcher=fetcher,
        provider=provider,
    ):
        pass
    assert fetcher.closed is True
    assert provider.closed is True


@pytest.mark.asyncio
async def test_service_close_closes_provider_owned_openai_client() -> None:
    url = "https://safe.example.test/minimal"
    fetcher = FixtureFetcher("<h1>Local title</h1>", url)
    client = ClosableOpenAIClient()
    provider = OpenAIResponsesProvider(client=client, owns_client=True)
    service = OmniScrape(  # type: ignore[arg-type]
        fetcher=fetcher,
        provider=provider,
    )

    await service.aclose()

    assert fetcher.closed is True
    assert client.closed is True
