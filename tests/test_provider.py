"""Optional provider boundary tests use a fake Responses client only."""

from __future__ import annotations

import asyncio
import json
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from omniscrape.errors import BusyError, ProviderError, ProviderUnavailableError
from omniscrape.models import Article, ContentKind, Product
from omniscrape.providers.openai import OpenAIResponsesProvider

ARTICLE_PAYLOAD = {
    "title": "Fixture article",
    "author": "Avery Chen",
    "date_published": "2026-04-12",
    "text": "Fixture body",
    "description": "Fixture description",
    "images": ["https://cdn.example.test/article.jpg"],
}
PRODUCT_PAYLOAD = {
    "name": "Fixture product",
    "price": "49.90",
    "currency": "USD",
    "sku": "FIX-49",
    "description": "Fixture description",
    "images": ["https://cdn.example.test/product.jpg"],
}


class FakeResponses:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def client_with(responses: FakeResponses) -> Any:
    return SimpleNamespace(responses=responses)


def test_provider_requires_key_when_constructing_default_client() -> None:
    with pytest.raises(ProviderUnavailableError):
        OpenAIResponsesProvider()


def test_lazily_created_client_cannot_be_marked_caller_owned() -> None:
    with pytest.raises(ValueError, match="must be provider-owned"):
        OpenAIResponsesProvider(api_key="fixture-key", owns_client=False)


def test_provider_readiness_is_truthful_without_constructing_client(monkeypatch: Any) -> None:
    injected = OpenAIResponsesProvider(client=client_with(FakeResponses()))
    assert injected.available() is True

    lazy = OpenAIResponsesProvider(api_key="fixture-key")
    monkeypatch.setattr("omniscrape.providers.openai.importlib.util.find_spec", lambda _: None)
    assert lazy.available() is False


@pytest.mark.asyncio
async def test_closed_provider_is_not_available() -> None:
    provider = OpenAIResponsesProvider(client=client_with(FakeResponses()))
    await provider.aclose()
    assert provider.available() is False


@pytest.mark.asyncio
async def test_missing_sdk_error_is_deferred_until_provider_use(monkeypatch: Any) -> None:
    monkeypatch.setitem(sys.modules, "openai", None)
    provider = OpenAIResponsesProvider(api_key="fixture-key")

    with pytest.raises(ProviderUnavailableError, match="SDK is not installed"):
        await provider.extract(
            html="<h1>Fixture</h1>",
            url="https://news.example.test/story",
            kind=ContentKind.ARTICLE,
        )


@pytest.mark.asyncio
async def test_api_key_client_is_created_lazily_and_closed(monkeypatch: Any) -> None:
    clients: list[Any] = []

    class FakeAsyncOpenAI:
        def __init__(self, *, api_key: str | None, timeout: float, max_retries: int) -> None:
            self.api_key = api_key
            self.timeout = timeout
            self.max_retries = max_retries
            self.responses = FakeResponses(
                {
                    "output_text": json.dumps(ARTICLE_PAYLOAD),
                    "model": "fixture-model",
                }
            )
            self.close_calls = 0
            clients.append(self)

        async def close(self) -> None:
            self.close_calls += 1

    openai = ModuleType("openai")
    openai.AsyncOpenAI = FakeAsyncOpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", openai)

    provider = OpenAIResponsesProvider(api_key="fixture-key", model="requested-model")
    assert clients == []

    result = await provider.extract(
        html="<h1>Fixture</h1>",
        url="https://news.example.test/story",
        kind=ContentKind.ARTICLE,
    )
    assert result.data.title == "Fixture article"
    assert clients[0].api_key == "fixture-key"
    assert clients[0].timeout == 30.0
    assert clients[0].max_retries == 0

    await provider.aclose()
    await provider.aclose()
    assert clients[0].close_calls == 1


@pytest.mark.asyncio
async def test_injected_client_is_caller_owned_unless_explicitly_transferred() -> None:
    class ClosableClient:
        def __init__(self) -> None:
            self.responses = FakeResponses()
            self.close_calls = 0

        async def close(self) -> None:
            self.close_calls += 1

    caller_owned = ClosableClient()
    await OpenAIResponsesProvider(client=caller_owned).aclose()
    assert caller_owned.close_calls == 0

    transferred = ClosableClient()
    await OpenAIResponsesProvider(client=transferred, owns_client=True).aclose()
    assert transferred.close_calls == 1


@pytest.mark.asyncio
async def test_article_response_is_validated_with_real_usage_counts() -> None:
    responses = FakeResponses(
        {
            "output_text": json.dumps(ARTICLE_PAYLOAD),
            "usage": {"input_tokens": 101, "output_tokens": 22, "total_tokens": 123},
            "model": "fixture-model-2026",
            "id": "response_fixture",
        }
    )
    provider = OpenAIResponsesProvider(
        client=client_with(responses),
        model="requested-model",
        max_input_chars=12,
        max_output_tokens=321,
    )

    result = await provider.extract(
        html="abcdefghijklmnop", url="https://news.example.test/story", kind=ContentKind.ARTICLE
    )

    assert isinstance(result.data, Article)
    assert result.data.title == "Fixture article"
    assert result.provider == "openai"
    assert result.model == "fixture-model-2026"
    assert result.token_usage is not None
    assert result.token_usage.total_tokens == 123
    request = responses.calls[0]
    assert request["model"] == "requested-model"
    input_payload = json.loads(request["input"])
    assert input_payload == {
        "untrusted_source_url": "https://news.example.test/story",
        "untrusted_page_html": "abcdefghijkl",
    }
    assert request["text"]["format"]["name"] == "omniscrape_article"
    assert request["text"]["format"]["strict"] is True
    assert request["max_output_tokens"] == 321
    assert request["store"] is False


@pytest.mark.asyncio
async def test_product_object_response_uses_product_schema_and_default_model() -> None:
    response = SimpleNamespace(
        output_text=json.dumps(PRODUCT_PAYLOAD),
        usage=SimpleNamespace(
            input_tokens="not-reported",
            output_tokens=None,
            total_tokens=None,
        ),
        id="fixture-id",
    )
    responses = FakeResponses(response)
    provider = OpenAIResponsesProvider(client=client_with(responses), model="fixture-model")

    result = await provider.extract(
        html="<html></html>",
        url="https://shop.example.test/product",
        kind=ContentKind.PRODUCT,
    )

    assert isinstance(result.data, Product)
    assert result.data.price == "49.90"
    assert result.model == "fixture-model"
    assert result.token_usage is None
    assert responses.calls[0]["text"]["format"]["name"] == "omniscrape_product"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("output", "message"),
    [
        (None, "no structured output"),
        ("   ", "no structured output"),
        ("[]", "invalid object"),
        ("{not-json", "invalid structured data"),
        (json.dumps({**ARTICLE_PAYLOAD, "extra": True}), "invalid structured data"),
    ],
)
async def test_invalid_provider_outputs_fail_closed(output: Any, message: str) -> None:
    provider = OpenAIResponsesProvider(client=client_with(FakeResponses({"output_text": output})))
    with pytest.raises(ProviderError, match=message):
        await provider.extract(
            html="<html></html>",
            url="https://news.example.test/story",
            kind=ContentKind.ARTICLE,
        )


@pytest.mark.asyncio
async def test_transport_errors_are_wrapped_without_reflecting_details() -> None:
    provider = OpenAIResponsesProvider(
        client=client_with(FakeResponses(error=RuntimeError("secret upstream response")))
    )
    with pytest.raises(ProviderError, match="provider request failed") as captured:
        await provider.extract(
            html="<html></html>",
            url="https://news.example.test/story",
            kind=ContentKind.ARTICLE,
        )
    assert "secret upstream response" not in str(captured.value)


@pytest.mark.asyncio
async def test_provider_call_has_one_bounded_wall_clock_deadline() -> None:
    class SlowResponses:
        async def create(self, **_kwargs: Any) -> Any:
            await asyncio.sleep(1)
            raise AssertionError("provider deadline should cancel this call")

    provider = OpenAIResponsesProvider(client=client_with(SlowResponses()), timeout_seconds=0.001)
    with pytest.raises(ProviderError, match="timed out"):
        await provider.extract(
            html="<html></html>",
            url="https://news.example.test/story",
            kind=ContentKind.ARTICLE,
        )


@pytest.mark.asyncio
async def test_provider_deadline_does_not_wait_for_stalled_cleanup_and_is_bounded() -> None:
    cleanup_started = asyncio.Event()
    release_cleanup = asyncio.Event()
    starts = 0

    class CleanupStallingResponses:
        async def create(self, **_kwargs: Any) -> Any:
            nonlocal starts
            starts += 1
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await release_cleanup.wait()

    provider = OpenAIResponsesProvider(
        client=client_with(CleanupStallingResponses()), timeout_seconds=0.001
    )
    started = asyncio.get_running_loop().time()
    try:
        for _ in range(8):
            with pytest.raises(ProviderError, match="timed out"):
                await provider.extract(
                    html="<html></html>",
                    url="https://news.example.test/story",
                    kind=ContentKind.ARTICLE,
                )
        assert asyncio.get_running_loop().time() - started < 0.2
        await asyncio.wait_for(cleanup_started.wait(), timeout=0.1)

        with pytest.raises(BusyError, match="cleanup capacity"):
            await provider.extract(
                html="<html></html>",
                url="https://news.example.test/story",
                kind=ContentKind.ARTICLE,
            )
        assert starts == 8
        assert provider._operations.outstanding == 8
    finally:
        await provider.aclose()
        release_cleanup.set()
        await provider.aclose()

    assert provider._operations.outstanding == 0


def test_provider_rejects_non_positive_timeout() -> None:
    for timeout in (0, -1, True, float("inf"), float("nan"), 301):
        with pytest.raises(ValueError, match="timeout must be positive"):
            OpenAIResponsesProvider(client=client_with(FakeResponses()), timeout_seconds=timeout)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("max_output_tokens", 0),
        ("max_output_tokens", True),
        ("max_input_chars", 0),
        ("max_input_chars", float("inf")),
        ("max_inflight_tasks", 33),
        ("max_inflight_tasks", True),
        ("model", ""),
    ],
)
def test_provider_rejects_invalid_direct_resource_limits(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        OpenAIResponsesProvider(
            client=client_with(FakeResponses()),
            **{field: value},  # type: ignore[arg-type]
        )
