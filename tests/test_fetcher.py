"""Redirect-aware HTTP behavior with an in-memory transport."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Iterable
from types import ModuleType, SimpleNamespace
from typing import Any

import httpx
import pytest

from omniscrape.errors import (
    BusyError,
    FetchError,
    ResponseTooLargeError,
    UnsupportedContentError,
    URLSafetyError,
)
from omniscrape.fetcher import (
    AsyncFetcher,
    FetcherConfig,
    FetchResult,
    PlaywrightRenderer,
    _peer_address,
    _same_origin,
    renderer_available,
    renderer_package_available,
)

PUBLIC_IP = "93.184.216.34"


def public_resolver(_host: str, _port: int) -> Iterable[Any]:
    return [PUBLIC_IP]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("connect_timeout_seconds", 0),
        ("read_timeout_seconds", float("inf")),
        ("write_timeout_seconds", float("nan")),
        ("pool_timeout_seconds", -1),
        ("total_timeout_seconds", True),
        ("max_response_bytes", float("inf")),
        ("max_redirects", -1),
        ("render_timeout_ms", 0),
        ("max_render_requests", False),
        ("max_render_nodes", "many"),
        ("max_inflight_tasks", 33),
        ("max_render_concurrency", 3),
    ],
)
def test_fetcher_config_rejects_invalid_direct_resource_limits(field: str, value: Any) -> None:
    with pytest.raises(ValueError):
        FetcherConfig(**{field: value})  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_fetches_html_without_real_network(article_html: str) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=article_html.encode(),
            request=request,
        )

    async with AsyncFetcher(
        transport=httpx.MockTransport(handler), resolver=public_resolver
    ) as fetcher:
        result = await fetcher.fetch("https://news.example.test/story#fragment")

    assert len(seen) == 1
    assert str(seen[0].url) == f"https://{PUBLIC_IP}/story"
    assert seen[0].headers["host"] == "news.example.test"
    assert seen[0].headers["connection"] == "close"
    assert seen[0].headers["accept-encoding"] == "identity"
    assert "cookie" not in seen[0].headers
    assert seen[0].extensions["sni_hostname"] == "news.example.test"
    assert str(result.final_url) == "https://news.example.test/story"
    assert result.status_code == 200
    assert result.content_type == "text/html"
    assert result.html == article_html
    assert result.byte_count == len(article_html.encode())
    assert result.redirects == []


@pytest.mark.asyncio
async def test_follows_relative_redirect_and_records_hop(
    redirect_target_html: str,
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/final"}, request=request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text=redirect_target_html,
            request=request,
        )

    async with AsyncFetcher(
        transport=httpx.MockTransport(handler), resolver=public_resolver
    ) as fetcher:
        result = await fetcher.fetch("https://safe.example.test/start")

    assert seen == [
        f"https://{PUBLIC_IP}/start",
        f"https://{PUBLIC_IP}/final",
    ]
    assert str(result.final_url) == "https://safe.example.test/final"
    assert len(result.redirects) == 1
    assert result.redirects[0].status_code == 302
    assert str(result.redirects[0].to_url) == "https://safe.example.test/final"


@pytest.mark.asyncio
async def test_redirect_target_is_revalidated_before_second_request() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(
            302,
            headers={"location": "http://169.254.169.254/latest/meta-data/"},
            request=request,
        )

    async with AsyncFetcher(
        transport=httpx.MockTransport(handler), resolver=public_resolver
    ) as fetcher:
        with pytest.raises(URLSafetyError):
            await fetcher.fetch("https://safe.example.test/start")

    assert seen == [f"https://{PUBLIC_IP}/start"]


@pytest.mark.asyncio
async def test_redirect_limit_is_enforced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        number = int(request.url.path.removeprefix("/hop/"))
        return httpx.Response(
            302,
            headers={"location": f"/hop/{number + 1}"},
            request=request,
        )

    config = FetcherConfig(max_redirects=2)
    async with AsyncFetcher(
        config, transport=httpx.MockTransport(handler), resolver=public_resolver
    ) as fetcher:
        with pytest.raises(FetchError, match="redirect limit"):
            await fetcher.fetch("https://safe.example.test/hop/0")


@pytest.mark.asyncio
async def test_declared_and_streamed_body_limits_are_enforced() -> None:
    config = FetcherConfig(max_response_bytes=16)

    def declared(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-length": "999"},
            content=b"small",
            request=request,
        )

    def streamed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"x" * 17,
            request=request,
        )

    for handler in (declared, streamed):
        async with AsyncFetcher(
            config, transport=httpx.MockTransport(handler), resolver=public_resolver
        ) as fetcher:
            with pytest.raises(ResponseTooLargeError):
                await fetcher.fetch("https://safe.example.test/page")


@pytest.mark.asyncio
async def test_rejects_non_html_and_error_responses() -> None:
    for status, content_type, error in (
        (200, "application/octet-stream", UnsupportedContentError),
        (503, "text/html", FetchError),
    ):
        transport = httpx.MockTransport(
            lambda request, s=status, c=content_type: httpx.Response(
                s, headers={"content-type": c}, content=b"body", request=request
            )
        )
        async with AsyncFetcher(transport=transport, resolver=public_resolver) as fetcher:
            with pytest.raises(error):
                await fetcher.fetch("https://safe.example.test/page")


@pytest.mark.asyncio
async def test_render_mode_delegates_to_injected_renderer() -> None:
    class FakeRenderer:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def fetch(self, url: str) -> FetchResult:
            self.calls.append(url)
            return FetchResult(
                requested_url=url,
                final_url=url,
                status_code=200,
                html="<html><title>Rendered</title></html>",
                content_type="text/html",
                encoding="utf-8",
                byte_count=37,
                elapsed_ms=1.0,
                rendered=True,
            )

    renderer = FakeRenderer()
    async with AsyncFetcher(
        transport=httpx.MockTransport(lambda _: None),
        resolver=public_resolver,
        renderer=renderer,
    ) as fetcher:
        result = await fetcher.fetch("https://render.example.test/", render=True)

    assert renderer.calls == ["https://render.example.test/"]
    assert result.rendered is True


@pytest.mark.asyncio
async def test_falsey_injected_renderer_is_preserved() -> None:
    class FalseyRenderer:
        def __init__(self) -> None:
            self.calls = 0

        def __bool__(self) -> bool:
            return False

        async def fetch(self, url: str) -> FetchResult:
            self.calls += 1
            return FetchResult(
                requested_url=url,
                final_url=url,
                status_code=200,
                html="<h1>Rendered</h1>",
                encoding="utf-8",
                byte_count=17,
                elapsed_ms=1,
                rendered=True,
            )

    renderer = FalseyRenderer()
    async with AsyncFetcher(
        transport=httpx.MockTransport(lambda _: None),
        resolver=public_resolver,
        renderer=renderer,
    ) as fetcher:
        result = await fetcher.fetch("https://render.example.test/", render=True)

    assert result.rendered is True
    assert renderer.calls == 1


@pytest.mark.asyncio
async def test_injected_transport_lifecycle_belongs_to_fetcher() -> None:
    class TrackingTransport(httpx.AsyncBaseTransport):
        def __init__(self) -> None:
            self.closed = False

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="ok", request=request)

        async def aclose(self) -> None:
            self.closed = True

    transport = TrackingTransport()
    fetcher = AsyncFetcher(transport=transport, resolver=public_resolver)
    await fetcher.aclose()
    assert transport.closed is True


@pytest.mark.asyncio
async def test_pinned_transport_never_carries_cookies_between_logical_hosts() -> None:
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.headers["host"]
        seen.append((host, request.headers.get("cookie")))
        headers = {"content-type": "text/html"}
        if host == "first.example.test":
            headers["set-cookie"] = "secret=from-first; Path=/"
        return httpx.Response(200, headers=headers, text="ok", request=request)

    async with AsyncFetcher(
        transport=httpx.MockTransport(handler), resolver=public_resolver
    ) as fetcher:
        await fetcher.fetch("https://first.example.test/")
        await fetcher.fetch("https://second.example.test/")

    assert seen == [
        ("first.example.test", None),
        ("second.example.test", None),
    ]


@pytest.mark.asyncio
async def test_http_content_encoding_is_fail_closed_before_stream_decode() -> None:
    class NeverReadStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.read = False

        async def __aiter__(self):
            self.read = True
            yield b"encoded-body-is-never-decoded"

    stream = NeverReadStream()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(
            200,
            headers={"content-type": "text/html", "content-encoding": "gzip"},
            stream=stream,
            request=request,
        )

    async with AsyncFetcher(
        transport=httpx.MockTransport(handler), resolver=public_resolver
    ) as fetcher:
        with pytest.raises(FetchError, match="identity encoding"):
            await fetcher.fetch("https://safe.example.test/")
    assert stream.read is False


@pytest.mark.asyncio
async def test_owned_client_is_closed_by_context_manager() -> None:
    fetcher = AsyncFetcher(resolver=public_resolver)
    async with fetcher as entered:
        assert entered is fetcher
        assert fetcher._client.is_closed is False
    assert fetcher._client.is_closed is True


@pytest.mark.asyncio
async def test_network_timeout_is_wrapped_as_fetch_error() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fixture timeout", request=request)

    async with AsyncFetcher(
        transport=httpx.MockTransport(timeout), resolver=public_resolver
    ) as fetcher:
        with pytest.raises(FetchError, match="could not be reached safely"):
            await fetcher.fetch("https://safe.example.test/page")


@pytest.mark.asyncio
async def test_redirect_without_location_is_rejected() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(302, request=request))
    async with AsyncFetcher(transport=transport, resolver=public_resolver) as fetcher:
        with pytest.raises(FetchError, match="invalid redirect"):
            await fetcher.fetch("https://safe.example.test/page")


@pytest.mark.asyncio
async def test_invalid_declared_length_and_unknown_encoding_fall_back_safely() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "content-type": "text/html; charset=fixture-unknown",
                "content-length": "not-a-number",
            },
            content=b"fixture body",
            request=request,
        )

    async with AsyncFetcher(
        transport=httpx.MockTransport(handler), resolver=public_resolver
    ) as fetcher:
        result = await fetcher.fetch("https://safe.example.test/page")
    assert result.html == "fixture body"
    assert result.encoding == "utf-8"


@pytest.mark.asyncio
async def test_missing_content_type_is_accepted_for_compatibility() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"plain body", request=request)
    )
    async with AsyncFetcher(transport=transport, resolver=public_resolver) as fetcher:
        result = await fetcher.fetch("https://safe.example.test/page")
    assert result.content_type is None
    assert result.html == "plain body"


def test_peer_address_supports_transport_extension_shapes() -> None:
    class TupleStream:
        def get_extra_info(self, key: str) -> Any:
            return (PUBLIC_IP, 443) if key == "server_addr" else None

    class StringStream:
        def get_extra_info(self, key: str) -> Any:
            return PUBLIC_IP if key == "peername" else None

    class Socket:
        def getpeername(self) -> tuple[str, int]:
            return PUBLIC_IP, 443

    class SocketStream:
        def get_extra_info(self, key: str) -> Any:
            return Socket() if key == "socket" else None

    request = httpx.Request("GET", "https://safe.example.test/")
    assert (
        _peer_address(
            httpx.Response(200, request=request, extensions={"network_stream": TupleStream()})
        )
        == PUBLIC_IP
    )
    assert (
        _peer_address(
            httpx.Response(200, request=request, extensions={"network_stream": StringStream()})
        )
        == PUBLIC_IP
    )
    assert (
        _peer_address(
            httpx.Response(200, request=request, extensions={"network_stream": SocketStream()})
        )
        == PUBLIC_IP
    )
    assert _peer_address(httpx.Response(200, request=request)) is None


def test_renderer_package_availability_handles_missing_and_broken_import_specs(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr("omniscrape.fetcher.importlib.util.find_spec", lambda _: None)
    assert renderer_package_available() is False

    def broken_spec(_name: str) -> Any:
        raise ValueError("fixture broken spec")

    monkeypatch.setattr("omniscrape.fetcher.importlib.util.find_spec", broken_spec)
    assert renderer_package_available() is False


class FakeRoute:
    def __init__(self) -> None:
        self.action: str | None = None

    async def abort(self) -> None:
        self.action = "abort"

    async def continue_(self, **_kwargs: Any) -> None:
        self.action = "continue"


class FakeBrowserRequest:
    def __init__(
        self,
        url: str,
        *,
        redirected_from: FakeBrowserRequest | None = None,
        status: int = 200,
    ) -> None:
        self.url = url
        self.redirected_from = redirected_from
        self.status = status

    async def response(self) -> Any:
        return SimpleNamespace(status=self.status)


class FakeCDPSession:
    def __init__(self, page: FakePage) -> None:
        self.callbacks: dict[str, Any] = {}
        self.sent: list[tuple[str, dict[str, Any] | None]] = []
        self.page = page
        self.frame_tree_before_navigation: bool | None = None

    async def send(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        self.sent.append((method, params))
        if method == "Page.getFrameTree":
            self.frame_tree_before_navigation = not self.page.goto_calls
            return {"frameTree": {"frame": {"id": "fixture-frame"}}}
        if method == "Page.createIsolatedWorld":
            return {"executionContextId": 17}
        if method == "Runtime.evaluate":
            if self.page.mutate_before_budget_url is not None:
                self.page.url = self.page.mutate_before_budget_url
            html = self.page.html
            if self.page.mutate_after_budget_html is not None:
                self.page.html = self.page.mutate_after_budget_html
            return {
                "result": {
                    "value": {
                        "nodeCount": self.page.dom_nodes,
                        "contentBytes": self.page.dom_content_units,
                        "exceeded": False,
                        "documentURL": self.page.url,
                        "html": html,
                    }
                }
            }
        return None

    def on(self, event: str, callback: Any) -> None:
        self.callbacks[event] = callback

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        self.callbacks[event](payload)


class FakeWebSocketRoute:
    def __init__(self) -> None:
        self.closed: dict[str, Any] | None = None

    async def close(self, **kwargs: Any) -> None:
        self.closed = kwargs


class FakePage:
    def __init__(
        self,
        *,
        final_url: str = "https://render.example.test/final",
        html: str = "<html><h1>Rendered fixture</h1></html>",
        status: int | None = 200,
        error: Exception | None = None,
        network_bytes: int = 0,
        decoded_network_bytes: int = 0,
        request: FakeBrowserRequest | None = None,
        network_requests: list[Any] | None = None,
        dom_nodes: int = 1,
        dom_content_units: int = 0,
        mutate_after_budget_html: str | None = None,
        mutate_before_budget_url: str | None = None,
        close_network_bytes: int = 0,
    ) -> None:
        self.url = final_url
        self.html = html
        self.status = status
        self.error = error
        self.network_bytes = network_bytes
        self.decoded_network_bytes = decoded_network_bytes
        self.request = request
        self.network_requests = network_requests or []
        self.dom_nodes = dom_nodes
        self.dom_content_units = dom_content_units
        self.mutate_after_budget_html = mutate_after_budget_html
        self.mutate_before_budget_url = mutate_before_budget_url
        self.close_network_bytes = close_network_bytes
        self.content_called = False
        self.route_actions: list[str | None] = []
        self.cdp: FakeCDPSession | None = None
        self.route_callback: Any = None
        self.goto_calls: list[dict[str, Any]] = []
        self.init_scripts: list[str] = []
        self.main_frame = object()

    async def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)

    async def route(self, pattern: str, callback: Any) -> None:
        assert pattern == "**/*"
        self.route_callback = callback

    async def goto(self, url: str, **kwargs: Any) -> Any:
        self.goto_calls.append({"url": url, **kwargs})
        if self.error is not None:
            raise self.error
        for network_request in self.network_requests:
            route = FakeRoute()
            await self.route_callback(route, network_request)
            self.route_actions.append(route.action)
        if self.cdp is not None and (self.network_bytes or self.decoded_network_bytes):
            self.cdp.emit(
                "Network.dataReceived",
                {
                    "encodedDataLength": self.network_bytes,
                    "dataLength": self.decoded_network_bytes,
                },
            )
        request = self.request or FakeBrowserRequest(self.url)
        return None if self.status is None else SimpleNamespace(status=self.status, request=request)

    async def content(self) -> str:
        self.content_called = True
        return self.html


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.closed = False
        self.cdp = FakeCDPSession(page)
        self.init_scripts: list[str] = []
        self.web_socket_callback: Any = None

    async def new_page(self) -> FakePage:
        return self.page

    async def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)

    async def route_web_socket(self, pattern: str, callback: Any) -> None:
        assert pattern == "**/*"
        self.web_socket_callback = callback

    async def new_cdp_session(self, page: FakePage) -> FakeCDPSession:
        assert page is self.page
        page.cdp = self.cdp
        return self.cdp

    async def route(self, pattern: str, callback: Any) -> None:
        assert pattern == "**/*"
        self.page.route_callback = callback

    async def close(self) -> None:
        if self.page.close_network_bytes:
            self.cdp.emit(
                "Network.dataReceived",
                {
                    "encodedDataLength": self.page.close_network_bytes,
                    "dataLength": self.page.close_network_bytes,
                },
            )
        self.closed = True


class FakeBrowser:
    def __init__(self, page: FakePage) -> None:
        self.context = FakeContext(page)
        self.closed = False
        self.context_options: dict[str, Any] = {}
        self.launch_args: list[str] = []
        self.chromium_sandbox: bool | None = None
        self.launch_error: Exception | None = None
        self.chromium = FakeChromium(self)

    async def new_context(self, **kwargs: Any) -> FakeContext:
        self.context_options = kwargs
        return self.context

    async def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser
        self.launch_count = 0

    async def launch(
        self,
        *,
        headless: bool,
        chromium_sandbox: bool,
        args: list[str] | None = None,
    ) -> FakeBrowser:
        assert headless is True
        self.browser.chromium_sandbox = chromium_sandbox
        self.launch_count += 1
        if self.browser.launch_error is not None:
            raise self.browser.launch_error
        self.browser.launch_args = args or []
        return self.browser


class FakePlaywrightManager:
    def __init__(self, browser: FakeBrowser) -> None:
        self.playwright = SimpleNamespace(chromium=browser.chromium)
        self.stopped = False

    async def start(self) -> Any:
        return self.playwright

    async def __aenter__(self) -> Any:
        return await self.start()

    async def __aexit__(self, *_args: Any) -> None:
        self.stopped = True


def install_fake_playwright(monkeypatch: Any, page: FakePage) -> FakeBrowser:
    browser = FakeBrowser(page)
    playwright = ModuleType("playwright")
    async_api = ModuleType("playwright.async_api")
    async_api.async_playwright = lambda: FakePlaywrightManager(browser)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", playwright)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api)
    return browser


@pytest.mark.asyncio
async def test_renderer_readiness_probe_launches_and_closes_chromium(monkeypatch: Any) -> None:
    browser = install_fake_playwright(monkeypatch, FakePage())
    monkeypatch.setattr("omniscrape.fetcher.renderer_package_available", lambda: True)
    monkeypatch.setattr("omniscrape.fetcher._renderer_probe_result", None)

    assert await renderer_available(refresh=True) is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_renderer_readiness_probe_rejects_missing_chromium(monkeypatch: Any) -> None:
    browser = install_fake_playwright(monkeypatch, FakePage())
    browser.launch_error = RuntimeError("fixture executable missing")
    monkeypatch.setattr("omniscrape.fetcher.renderer_package_available", lambda: True)
    monkeypatch.setattr("omniscrape.fetcher._renderer_probe_result", None)

    assert await renderer_available(refresh=True) is False


@pytest.mark.asyncio
async def test_concurrent_renderer_readiness_checks_share_one_launch(monkeypatch: Any) -> None:
    browser = install_fake_playwright(monkeypatch, FakePage())
    monkeypatch.setattr("omniscrape.fetcher.renderer_package_available", lambda: True)
    monkeypatch.setattr("omniscrape.fetcher._renderer_probe_result", None)
    monkeypatch.setattr("omniscrape.fetcher._renderer_probe_task", None)

    assert await asyncio.gather(
        renderer_available(refresh=True), renderer_available(refresh=True)
    ) == [True, True]
    assert browser.chromium.launch_count == 1
    assert browser.chromium_sandbox is True
    assert browser.closed is True


def test_cancelled_renderer_probe_does_not_poison_a_replacement_event_loop(
    monkeypatch: Any,
) -> None:
    calls = 0

    async def probe() -> bool:
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.Event().wait()
        return True

    monkeypatch.setattr("omniscrape.fetcher._probe_renderer", probe)
    monkeypatch.setattr("omniscrape.fetcher._renderer_probe_result", None)
    monkeypatch.setattr("omniscrape.fetcher._renderer_probe_task", None)

    async def cancel_first_waiter() -> None:
        waiter = asyncio.create_task(renderer_available(refresh=True))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter

    asyncio.run(cancel_first_waiter())

    assert asyncio.run(renderer_available(refresh=True)) is True
    assert calls == 2


def test_browser_origin_check_is_exact_and_side_effect_free() -> None:
    validated = SimpleNamespace(scheme="https", host="render.example.test", port=443)
    assert _same_origin("https://render.example.test/app.js", validated) is True
    assert _same_origin("https://render.example.test:444/app.js", validated) is False
    assert _same_origin("http://render.example.test/app.js", validated) is False
    assert _same_origin("https://cdn.example.test/app.js", validated) is False
    assert _same_origin("blob:https://render.example.test/id", validated) is False


@pytest.mark.asyncio
async def test_playwright_renderer_is_bounded_and_guards_subresources(monkeypatch: Any) -> None:
    page = FakePage(status=None)
    browser = install_fake_playwright(monkeypatch, page)
    config = FetcherConfig(max_response_bytes=1_000, render_timeout_ms=321)
    result = await PlaywrightRenderer(config, resolver=public_resolver).fetch(
        "https://render.example.test/start"
    )

    assert result.rendered is True
    assert result.status_code == 200
    assert str(result.final_url) == "https://render.example.test/final"
    assert page.goto_calls[0]["timeout"] == 321
    assert "WebSocket" in browser.context.init_scripts[0]
    assert "Worker" in browser.context.init_scripts[0]
    assert "SharedWorker" in browser.context.init_scripts[0]
    assert "WebTransport" in browser.context.init_scripts[0]
    assert "'open'" in browser.context.init_scripts[0]
    assert browser.context_options["service_workers"] == "block"
    assert browser.context_options["accept_downloads"] is False
    assert browser.context_options["extra_http_headers"] == {"Accept-Encoding": "identity"}
    assert browser.chromium_sandbox is True
    assert any("MAP render.example.test 93.184.216.34" in item for item in browser.launch_args)
    resolver_arg = next(
        item for item in browser.launch_args if item.startswith("--host-resolver-rules=")
    )
    assert resolver_arg.endswith("MAP render.example.test 93.184.216.34, MAP * ^NOTFOUND")
    assert "--proxy-server=direct://" in browser.launch_args
    assert "--proxy-bypass-list=*" in browser.launch_args
    assert "--no-proxy-server" not in browser.launch_args
    assert "--dns-prefetch-disable" in browser.launch_args
    assert "--disable-quic" in browser.launch_args
    assert "--enable-features=PreloadingHoldback,Prerender2Holdback" in browser.launch_args
    assert "--disable-features=Prerender2,SpeculationRulesPrefetchProxy" in browser.launch_args
    assert any(
        item.startswith("--disable-blink-features=SpeculationRules") for item in browser.launch_args
    )
    assert ("Network.enable", None) in browser.context.cdp.sent
    assert browser.context.cdp.frame_tree_before_navigation is True
    assert browser.context.closed is True
    assert browser.closed is True

    web_socket = FakeWebSocketRoute()
    await browser.context.web_socket_callback(web_socket)
    assert web_socket.closed == {"code": 1008, "reason": "Blocked by renderer policy"}

    media_route = FakeRoute()
    await page.route_callback(
        media_route,
        SimpleNamespace(resource_type="image", url="https://cdn.example.test/a.png"),
    )
    assert media_route.action == "abort"

    unsafe_route = FakeRoute()
    await page.route_callback(
        unsafe_route,
        SimpleNamespace(resource_type="document", url="http://127.0.0.1/private"),
    )
    assert unsafe_route.action == "abort"

    safe_route = FakeRoute()
    await page.route_callback(
        safe_route,
        SimpleNamespace(resource_type="script", url="https://render.example.test/app.js"),
    )
    assert safe_route.action == "continue"

    cross_origin_route = FakeRoute()
    await page.route_callback(
        cross_origin_route,
        SimpleNamespace(resource_type="script", url="https://cdn.example.test/app.js"),
    )
    assert cross_origin_route.action == "abort"

    mutation_route = FakeRoute()
    await page.route_callback(
        mutation_route,
        SimpleNamespace(
            method="POST",
            resource_type="fetch",
            url="https://render.example.test/account/delete",
        ),
    )
    assert mutation_route.action == "abort"

    popup_route = FakeRoute()
    await page.route_callback(
        popup_route,
        SimpleNamespace(
            resource_type="document",
            url="https://render.example.test/popup",
            frame=object(),
            redirected_from=None,
        ),
    )
    assert popup_route.action == "abort"

    main_document_route = FakeRoute()
    await page.route_callback(
        main_document_route,
        SimpleNamespace(
            resource_type="document",
            url="https://render.example.test/final",
            frame=page.main_frame,
            redirected_from=None,
        ),
    )
    assert main_document_route.action == "continue"

    later_navigation_route = FakeRoute()
    await page.route_callback(
        later_navigation_route,
        SimpleNamespace(
            resource_type="document",
            url="https://render.example.test/later-navigation",
            frame=page.main_frame,
            redirected_from=None,
        ),
    )
    assert later_navigation_route.action == "abort"


@pytest.mark.asyncio
async def test_playwright_renderer_aborts_during_aggregate_network_budget(
    monkeypatch: Any,
) -> None:
    page = FakePage(network_bytes=17)
    browser = install_fake_playwright(monkeypatch, page)
    with pytest.raises(ResponseTooLargeError):
        await PlaywrightRenderer(
            FetcherConfig(max_response_bytes=16), resolver=public_resolver
        ).fetch("https://render.example.test/start")
    assert browser.context.closed is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_renderer_watchdog_aborts_budget_overrun_during_dom_evaluation(
    monkeypatch: Any,
) -> None:
    page = FakePage()
    browser = install_fake_playwright(monkeypatch, page)
    evaluation_started = asyncio.Event()
    context_close_started = asyncio.Event()
    release_evaluation = asyncio.Event()
    original_send = browser.context.cdp.send

    async def blocking_send(
        method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        if method == "Runtime.evaluate":
            evaluation_started.set()
            await release_evaluation.wait()
            raise RuntimeError("fixture context closed")
        return await original_send(method, params)

    async def close_context() -> None:
        context_close_started.set()
        browser.context.closed = True
        release_evaluation.set()

    browser.context.cdp.send = blocking_send  # type: ignore[method-assign]
    browser.context.close = close_context  # type: ignore[method-assign]
    task = asyncio.create_task(
        PlaywrightRenderer(FetcherConfig(max_response_bytes=16), resolver=public_resolver).fetch(
            "https://render.example.test/start"
        )
    )

    await asyncio.wait_for(evaluation_started.wait(), timeout=0.5)
    browser.context.cdp.emit(
        "Network.dataReceived",
        {"encodedDataLength": 17, "dataLength": 17},
    )
    await asyncio.wait_for(context_close_started.wait(), timeout=0.5)

    late_route = FakeRoute()
    await page.route_callback(
        late_route,
        SimpleNamespace(
            method="GET",
            resource_type="script",
            url="https://render.example.test/late.js",
        ),
    )
    assert late_route.action == "abort"
    with pytest.raises(ResponseTooLargeError):
        await task
    assert browser.context.closed is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_renderer_budget_counts_decoded_bytes_not_only_wire_bytes(
    monkeypatch: Any,
) -> None:
    page = FakePage(network_bytes=1, decoded_network_bytes=17)
    browser = install_fake_playwright(monkeypatch, page)
    with pytest.raises(ResponseTooLargeError):
        await PlaywrightRenderer(
            FetcherConfig(max_response_bytes=16), resolver=public_resolver
        ).fetch("https://render.example.test/start")
    assert browser.context.closed is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_playwright_renderer_aborts_during_request_count_budget(
    monkeypatch: Any,
) -> None:
    requests = [
        SimpleNamespace(
            resource_type="script",
            url=f"https://render.example.test/app-{index}.js",
        )
        for index in range(2)
    ]
    page = FakePage(network_requests=requests)
    browser = install_fake_playwright(monkeypatch, page)

    with pytest.raises(ResponseTooLargeError):
        await PlaywrightRenderer(
            FetcherConfig(max_render_requests=1), resolver=public_resolver
        ).fetch("https://render.example.test/start")

    assert page.route_actions == ["continue", "abort"]
    assert browser.context.closed is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_blocked_renderer_requests_also_consume_request_budget(monkeypatch: Any) -> None:
    requests = [
        SimpleNamespace(resource_type="image", url="https://cdn.example.test/a.png"),
        SimpleNamespace(resource_type="script", url="https://cdn.example.test/app.js"),
    ]
    page = FakePage(network_requests=requests)
    browser = install_fake_playwright(monkeypatch, page)

    with pytest.raises(ResponseTooLargeError):
        await PlaywrightRenderer(
            FetcherConfig(max_render_requests=1), resolver=public_resolver
        ).fetch("https://render.example.test/start")

    assert page.route_actions == ["abort", "abort"]
    assert browser.context.closed is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_renderer_caps_javascript_created_dom_before_serialization(
    monkeypatch: Any,
) -> None:
    page = FakePage(dom_nodes=17)
    browser = install_fake_playwright(monkeypatch, page)

    with pytest.raises(ResponseTooLargeError):
        await PlaywrightRenderer(
            FetcherConfig(max_render_nodes=16), resolver=public_resolver
        ).fetch("https://render.example.test/start")

    assert page.content_called is False
    assert any(method == "Runtime.evaluate" for method, _ in browser.context.cdp.sent)
    assert browser.context.closed is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_renderer_caps_text_and_comment_content_before_serialization(
    monkeypatch: Any,
) -> None:
    page = FakePage(dom_nodes=2, dom_content_units=17)
    browser = install_fake_playwright(monkeypatch, page)

    with pytest.raises(ResponseTooLargeError):
        await PlaywrightRenderer(
            FetcherConfig(max_response_bytes=16), resolver=public_resolver
        ).fetch("https://render.example.test/start")

    assert page.content_called is False
    assert browser.context.closed is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_renderer_serialization_is_atomic_with_dom_budget(monkeypatch: Any) -> None:
    safe_html = "<html><body>safe</body></html>"
    page = FakePage(
        html=safe_html,
        mutate_after_budget_html="<html><body>" + ("x" * 10_000) + "</body></html>",
    )
    install_fake_playwright(monkeypatch, page)

    result = await PlaywrightRenderer(
        FetcherConfig(max_response_bytes=1_000), resolver=public_resolver
    ).fetch("https://render.example.test/start")

    assert result.html == safe_html
    assert page.content_called is False


@pytest.mark.asyncio
async def test_renderer_uses_url_captured_atomically_with_html(monkeypatch: Any) -> None:
    page = FakePage(
        final_url="https://render.example.test/initial",
        html="<html><body>history state</body></html>",
        mutate_before_budget_url="https://render.example.test/history-state",
    )
    install_fake_playwright(monkeypatch, page)

    result = await PlaywrightRenderer(resolver=public_resolver).fetch(
        "https://render.example.test/initial"
    )

    assert str(result.final_url) == "https://render.example.test/history-state"
    assert result.html == "<html><body>history state</body></html>"


@pytest.mark.asyncio
async def test_renderer_rechecks_byte_budget_after_network_shutdown(monkeypatch: Any) -> None:
    page = FakePage(close_network_bytes=17)
    browser = install_fake_playwright(monkeypatch, page)

    with pytest.raises(ResponseTooLargeError):
        await PlaywrightRenderer(
            FetcherConfig(max_response_bytes=16), resolver=public_resolver
        ).fetch("https://render.example.test/start")

    assert page.content_called is False
    assert browser.context.closed is True
    assert browser.closed is True


@pytest.mark.asyncio
async def test_total_fetch_deadline_bounds_the_entire_renderer_operation() -> None:
    class SlowRenderer:
        async def fetch(self, _url: str) -> FetchResult:
            await asyncio.sleep(1)
            raise AssertionError("deadline should cancel the renderer")

    async with AsyncFetcher(
        FetcherConfig(total_timeout_seconds=0.001),
        transport=httpx.MockTransport(lambda _: None),
        resolver=public_resolver,
        renderer=SlowRenderer(),
    ) as fetcher:
        with pytest.raises(FetchError, match="total time limit"):
            await fetcher.fetch("https://render.example.test/", render=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("reject_peer", [False, True])
async def test_hard_deadline_retains_http_response_cleanup(
    monkeypatch: Any, reject_peer: bool
) -> None:
    close_started = asyncio.Event()
    release_close = asyncio.Event()

    class BlockingCloseStream(httpx.AsyncByteStream):
        def __init__(self) -> None:
            self.closed = False

        async def __aiter__(self):
            yield b"<h1>bounded cleanup</h1>"

        async def aclose(self) -> None:
            close_started.set()
            await release_close.wait()
            self.closed = True

    stream = BlockingCloseStream()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            stream=stream,
            request=request,
        )

    if reject_peer:
        monkeypatch.setattr("omniscrape.fetcher._peer_address", lambda _response: "127.0.0.1")
    fetcher = AsyncFetcher(
        FetcherConfig(total_timeout_seconds=0.1),
        transport=httpx.MockTransport(handler),
        resolver=public_resolver,
    )
    try:
        with pytest.raises(FetchError, match="total time limit"):
            await fetcher.fetch("https://safe.example.test/")
        await asyncio.wait_for(close_started.wait(), timeout=0.5)
        assert fetcher._operations.outstanding == 1
        assert stream.closed is False
    finally:
        release_close.set()
        for _ in range(100):
            if fetcher._operations.outstanding == 0:
                break
            await asyncio.sleep(0.005)
        await fetcher.aclose()

    assert stream.closed is True
    assert fetcher._operations.outstanding == 0


@pytest.mark.asyncio
async def test_hard_deadline_retains_context_then_browser_cleanup(monkeypatch: Any) -> None:
    browser = install_fake_playwright(monkeypatch, FakePage())
    context_close_started = asyncio.Event()
    browser_close_started = asyncio.Event()
    release_context = asyncio.Event()
    release_browser = asyncio.Event()

    async def close_context() -> None:
        context_close_started.set()
        await release_context.wait()
        browser.context.closed = True

    async def close_browser() -> None:
        browser_close_started.set()
        await release_browser.wait()
        browser.closed = True

    browser.context.close = close_context  # type: ignore[method-assign]
    browser.close = close_browser  # type: ignore[method-assign]
    fetcher = AsyncFetcher(
        FetcherConfig(total_timeout_seconds=0.1),
        transport=httpx.MockTransport(lambda _: None),
        resolver=public_resolver,
    )
    try:
        with pytest.raises(FetchError, match="total time limit"):
            await fetcher.fetch("https://render.example.test/", render=True)
        await asyncio.wait_for(context_close_started.wait(), timeout=0.5)
        assert fetcher._operations.outstanding == 1
        assert fetcher._render_operations.outstanding == 1

        release_context.set()
        await asyncio.wait_for(browser_close_started.wait(), timeout=0.5)
        assert fetcher._operations.outstanding == 1
        assert browser.closed is False
    finally:
        release_context.set()
        release_browser.set()
        for _ in range(100):
            if fetcher._operations.outstanding == 0:
                break
            await asyncio.sleep(0.005)
        await fetcher.aclose()

    assert browser.context.closed is True
    assert browser.closed is True
    assert fetcher._operations.outstanding == 0
    assert fetcher._render_operations.outstanding == 0


@pytest.mark.asyncio
async def test_cancelled_playwright_start_runs_retained_manager_exit(monkeypatch: Any) -> None:
    start_entered = asyncio.Event()
    exit_entered = asyncio.Event()
    release_exit = asyncio.Event()

    class BlockingStartManager:
        def __init__(self) -> None:
            self.exited = False

        async def start(self) -> Any:
            start_entered.set()
            await asyncio.Event().wait()

        async def __aexit__(self, *_args: Any) -> None:
            exit_entered.set()
            await release_exit.wait()
            self.exited = True

    manager = BlockingStartManager()
    playwright = ModuleType("playwright")
    async_api = ModuleType("playwright.async_api")
    async_api.async_playwright = lambda: manager  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", playwright)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api)
    fetcher = AsyncFetcher(
        FetcherConfig(total_timeout_seconds=0.1),
        transport=httpx.MockTransport(lambda _: None),
        resolver=public_resolver,
    )
    try:
        with pytest.raises(FetchError, match="total time limit"):
            await fetcher.fetch("https://render.example.test/", render=True)
        assert start_entered.is_set()
        await asyncio.wait_for(exit_entered.wait(), timeout=0.5)
        assert fetcher._operations.outstanding == 1
        assert manager.exited is False
    finally:
        release_exit.set()
        for _ in range(100):
            if fetcher._operations.outstanding == 0:
                break
            await asyncio.sleep(0.005)
        await fetcher.aclose()

    assert manager.exited is True
    assert fetcher._operations.outstanding == 0


@pytest.mark.asyncio
async def test_cancelled_playwright_exit_remains_retained(monkeypatch: Any) -> None:
    browser = FakeBrowser(FakePage())
    exit_entered = asyncio.Event()
    release_exit = asyncio.Event()

    class BlockingExitManager:
        def __init__(self) -> None:
            self.exited = False

        async def start(self) -> Any:
            return SimpleNamespace(chromium=browser.chromium)

        async def __aexit__(self, *_args: Any) -> None:
            exit_entered.set()
            await release_exit.wait()
            self.exited = True

    manager = BlockingExitManager()
    playwright = ModuleType("playwright")
    async_api = ModuleType("playwright.async_api")
    async_api.async_playwright = lambda: manager  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", playwright)
    monkeypatch.setitem(sys.modules, "playwright.async_api", async_api)
    fetcher = AsyncFetcher(
        FetcherConfig(total_timeout_seconds=0.1),
        transport=httpx.MockTransport(lambda _: None),
        resolver=public_resolver,
    )
    try:
        with pytest.raises(FetchError, match="total time limit"):
            await fetcher.fetch("https://render.example.test/", render=True)
        await asyncio.wait_for(exit_entered.wait(), timeout=0.5)
        assert fetcher._operations.outstanding == 1
        assert manager.exited is False
    finally:
        release_exit.set()
        for _ in range(100):
            if fetcher._operations.outstanding == 0:
                break
            await asyncio.sleep(0.005)
        await fetcher.aclose()

    assert manager.exited is True
    assert browser.closed is True
    assert fetcher._operations.outstanding == 0


@pytest.mark.asyncio
async def test_total_fetch_deadline_does_not_wait_for_stalled_renderer_cleanup() -> None:
    cleanup_started = asyncio.Event()
    release_cleanup = asyncio.Event()

    class CleanupStallingRenderer:
        async def fetch(self, _url: str) -> FetchResult:
            try:
                await asyncio.Event().wait()
            finally:
                cleanup_started.set()
                await release_cleanup.wait()

    fetcher = AsyncFetcher(
        FetcherConfig(total_timeout_seconds=0.005),
        transport=httpx.MockTransport(lambda _: None),
        resolver=public_resolver,
        renderer=CleanupStallingRenderer(),
    )
    started = asyncio.get_running_loop().time()
    try:
        with pytest.raises(FetchError, match="total time limit"):
            await fetcher.fetch("https://render.example.test/", render=True)
        elapsed = asyncio.get_running_loop().time() - started

        assert elapsed < 0.1
        await asyncio.wait_for(cleanup_started.wait(), timeout=0.1)
    finally:
        release_cleanup.set()
        await fetcher.aclose()
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_stalled_fetch_cleanup_is_capacity_bounded_and_drained() -> None:
    release_cleanup = asyncio.Event()
    starts = 0

    class CleanupStallingRenderer:
        async def fetch(self, _url: str) -> FetchResult:
            nonlocal starts
            starts += 1
            try:
                await asyncio.Event().wait()
            finally:
                await release_cleanup.wait()

    fetcher = AsyncFetcher(
        FetcherConfig(total_timeout_seconds=0.001),
        transport=httpx.MockTransport(lambda _: None),
        resolver=public_resolver,
        renderer=CleanupStallingRenderer(),
    )
    try:
        for _ in range(2):
            with pytest.raises(FetchError, match="total time limit"):
                await fetcher.fetch("https://render.example.test/", render=True)

        with pytest.raises(BusyError, match="cleanup capacity"):
            await fetcher.fetch("https://render.example.test/", render=True)
        assert starts == 2
        assert fetcher._operations.outstanding == 2
        assert fetcher._render_operations.outstanding == 2
    finally:
        await fetcher.aclose()
        release_cleanup.set()
        await fetcher.aclose()

    assert fetcher._operations.outstanding == 0
    assert fetcher._render_operations.outstanding == 0


@pytest.mark.asyncio
async def test_renderer_probe_deadline_does_not_wait_for_stalled_close(monkeypatch: Any) -> None:
    browser = install_fake_playwright(monkeypatch, FakePage())
    release_close = asyncio.Event()

    async def stalled_close() -> None:
        await release_close.wait()
        browser.closed = True

    browser.close = stalled_close  # type: ignore[method-assign]
    monkeypatch.setattr("omniscrape.fetcher.renderer_package_available", lambda: True)
    monkeypatch.setattr("omniscrape.fetcher._renderer_probe_result", None)
    monkeypatch.setattr("omniscrape.fetcher._renderer_probe_task", None)
    monkeypatch.setattr("omniscrape.fetcher._RENDERER_PROBE_TIMEOUT_SECONDS", 0.005)

    started = asyncio.get_running_loop().time()
    try:
        assert await renderer_available(refresh=True) is False
        assert asyncio.get_running_loop().time() - started < 0.1
    finally:
        release_close.set()
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_playwright_renderer_records_same_origin_redirects(monkeypatch: Any) -> None:
    first = FakeBrowserRequest(
        "https://render.example.test/start",
        status=302,
    )
    final = FakeBrowserRequest(
        "https://render.example.test/final",
        redirected_from=first,
    )
    page = FakePage(request=final)
    install_fake_playwright(monkeypatch, page)

    result = await PlaywrightRenderer(resolver=public_resolver).fetch(
        "https://render.example.test/start"
    )

    assert len(result.redirects) == 1
    assert result.redirects[0].status_code == 302
    assert str(result.redirects[0].from_url) == "https://render.example.test/start"
    assert str(result.redirects[0].to_url) == "https://render.example.test/final"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("page", "error_type"),
    [
        (FakePage(status=503), FetchError),
        (FakePage(html="x" * 17), ResponseTooLargeError),
        (FakePage(error=RuntimeError("fixture browser crash")), FetchError),
    ],
)
async def test_playwright_renderer_wraps_failures_and_always_closes(
    monkeypatch: Any,
    page: FakePage,
    error_type: type[Exception],
) -> None:
    browser = install_fake_playwright(monkeypatch, page)
    config = FetcherConfig(max_response_bytes=16)
    with pytest.raises(error_type):
        await PlaywrightRenderer(config, resolver=public_resolver).fetch(
            "https://render.example.test/start"
        )
    assert browser.context.closed is True
    assert browser.closed is True
