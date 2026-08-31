"""MCP adapter tests install a tiny in-memory SDK stand-in."""

from __future__ import annotations

import asyncio
import builtins
import sys
from types import ModuleType
from typing import Any

import pytest

from omniscrape.config import Settings
from omniscrape.errors import URLSafetyError
from omniscrape.mcp import create_mcp_server
from omniscrape.models import Article, ExtractionMetadata, ExtractionResult

URL = "https://news.example.test/story"


class FakeFastMCP:
    def __init__(self, name: str, *, lifespan: Any = None) -> None:
        self.name = name
        self.lifespan = lifespan
        self.tool_function: Any = None

    def tool(self) -> Any:
        def register(function: Any) -> Any:
            self.tool_function = function
            return function

        return register


class StubService:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.error: Exception | None = None
        self.closed = False

    async def extract(self, *args: Any, **kwargs: Any) -> ExtractionResult:
        self.calls.append((*args, kwargs))
        if self.error is not None:
            raise self.error
        return ExtractionResult(
            url=URL,
            final_url=URL,
            kind="article",
            mode="deterministic",
            data=Article(url=URL, title="Fixture title"),
            metadata=ExtractionMetadata(sources=["heuristic"], completeness_score=0.2),
        )

    async def aclose(self) -> None:
        self.closed = True


@pytest.fixture
def fake_mcp_sdk(monkeypatch: Any) -> None:
    mcp = ModuleType("mcp")
    server = ModuleType("mcp.server")
    fastmcp = ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = FakeFastMCP  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mcp", mcp)
    monkeypatch.setitem(sys.modules, "mcp.server", server)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp)


@pytest.mark.asyncio
async def test_mcp_tool_returns_typed_result_and_forwards_options(fake_mcp_sdk: None) -> None:
    service = StubService()
    server = create_mcp_server(service)

    payload = await server.tool_function(URL, kind="article", mode="deterministic", render=True)

    assert server.name == "OmniScrape"
    assert payload["success"] is True
    assert payload["data"]["title"] == "Fixture title"
    assert service.calls[0][0] == URL
    assert service.calls[0][1].value == "article"
    assert service.calls[0][2].value == "deterministic"
    assert service.calls[0][3] == {"render": True}


@pytest.mark.asyncio
async def test_mcp_tool_defaults_to_deterministic_mode(fake_mcp_sdk: None) -> None:
    service = StubService()
    server = create_mcp_server(service)

    payload = await server.tool_function(URL)

    assert payload["success"] is True
    assert service.calls[0][2].value == "deterministic"


@pytest.mark.asyncio
async def test_falsey_injected_mcp_service_is_preserved(fake_mcp_sdk: None) -> None:
    class FalseyService(StubService):
        def __bool__(self) -> bool:
            return False

    service = FalseyService()
    server = create_mcp_server(service)

    payload = await server.tool_function(URL)

    assert payload["success"] is True
    assert len(service.calls) == 1


@pytest.mark.asyncio
async def test_mcp_honors_configured_concurrency_and_queue_timeout(fake_mcp_sdk: None) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingService(StubService):
        async def extract(self, *args: Any, **kwargs: Any) -> ExtractionResult:
            entered.set()
            await release.wait()
            return await super().extract(*args, **kwargs)

    service = BlockingService()
    server = create_mcp_server(
        service,
        settings=Settings(max_concurrency=1, queue_timeout_seconds=0.001),
    )
    first = asyncio.create_task(server.tool_function(URL))
    await asyncio.wait_for(entered.wait(), timeout=0.1)
    try:
        invalid = await server.tool_function(URL, kind="video")
        second = await server.tool_function(URL)
    finally:
        release.set()
    first_result = await first

    assert first_result["success"] is True
    assert invalid["error"]["code"] == "invalid_request"
    assert second["error"]["code"] == "service_busy"
    assert len(service.calls) == 1


@pytest.mark.asyncio
async def test_mcp_waiter_queue_is_capacity_bounded(fake_mcp_sdk: None) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    class BlockingService(StubService):
        async def extract(self, *args: Any, **kwargs: Any) -> ExtractionResult:
            entered.set()
            await release.wait()
            return await super().extract(*args, **kwargs)

    service = BlockingService()
    server = create_mcp_server(
        service,
        settings=Settings(max_concurrency=1, queue_timeout_seconds=1.0),
    )
    first = asyncio.create_task(server.tool_function(URL))
    await asyncio.wait_for(entered.wait(), timeout=0.1)
    waiter = asyncio.create_task(server.tool_function(URL))
    await asyncio.sleep(0)
    started = asyncio.get_running_loop().time()
    try:
        overflow = await server.tool_function(URL)
        assert asyncio.get_running_loop().time() - started < 0.1
    finally:
        release.set()
    first_result, waiter_result = await asyncio.gather(first, waiter)

    assert overflow["error"]["code"] == "service_busy"
    assert first_result["success"] is True
    assert waiter_result["success"] is True
    assert len(service.calls) == 2


@pytest.mark.asyncio
async def test_mcp_tool_returns_stable_invalid_request(fake_mcp_sdk: None) -> None:
    server = create_mcp_server(StubService())
    payload = await server.tool_function(URL, kind="video")
    assert payload["success"] is False
    assert payload["error"] == {
        "code": "invalid_request",
        "message": "kind or mode is invalid.",
    }


@pytest.mark.asyncio
async def test_mcp_tool_hides_domain_error_details(fake_mcp_sdk: None) -> None:
    service = StubService()
    service.error = URLSafetyError("internal private address")
    server = create_mcp_server(service)

    payload = await server.tool_function(URL, mode="deterministic")

    assert payload["error"]["code"] == "unsafe_url"
    assert "internal private address" not in payload["error"]["message"]


@pytest.mark.asyncio
async def test_mcp_tool_redacts_unexpected_errors(fake_mcp_sdk: None, caplog: Any) -> None:
    service = StubService()
    service.error = RuntimeError("fixture secret internal detail")
    server = create_mcp_server(service)

    payload = await server.tool_function(URL)

    assert payload["error"] == {
        "code": "internal_error",
        "message": "An unexpected server error occurred.",
    }
    assert "fixture secret" not in str(payload)
    assert "RuntimeError" in caplog.text
    assert "fixture secret" not in caplog.text


@pytest.mark.asyncio
async def test_mcp_lifespan_closes_only_an_owned_service(
    fake_mcp_sdk: None, monkeypatch: Any
) -> None:
    injected = StubService()
    injected_server = create_mcp_server(injected)
    assert injected_server.lifespan is None
    assert injected.closed is False

    owned = StubService()

    class StubFactory:
        @classmethod
        def from_settings(cls, settings: Any) -> StubService:
            return owned

    monkeypatch.setattr("omniscrape.mcp.OmniScrape", StubFactory)
    owned_server = create_mcp_server()
    assert owned_server.lifespan is not None

    async with owned_server.lifespan(owned_server):
        assert owned.closed is False
    assert owned.closed is True


def test_missing_mcp_extra_has_actionable_error(monkeypatch: Any) -> None:
    original_import = builtins.__import__

    def missing_sdk(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "mcp.server.fastmcp":
            raise ImportError("fixture missing SDK")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_sdk)
    for name in ("mcp.server.fastmcp", "mcp.server", "mcp"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    with pytest.raises(RuntimeError, match="install OmniScrape's mcp extra"):
        create_mcp_server(StubService())
