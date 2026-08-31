"""HTTP contract, authentication, safe errors, and SSE behavior."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Awaitable
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from omniscrape.api import _RequestBodyLimitMiddleware, create_app
from omniscrape.config import Settings
from omniscrape.errors import URLSafetyError
from omniscrape.models import Article, ExtractionMetadata, ExtractionResult

URL = "https://news.example.test/story"


def extraction_result(mode: str = "deterministic") -> ExtractionResult:
    return ExtractionResult(
        url=URL,
        final_url=URL,
        kind="article",
        mode=mode,
        data=Article(url=URL, title="Fixture title", text="Fixture body"),
        metadata=ExtractionMetadata(
            sources=["heuristic"],
            http_status=200,
            content_bytes=128,
            completeness_score=0.4,
        ),
    )


class StubService:
    provider = None

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    async def extract(
        self,
        url: str,
        kind: Any,
        mode: Any,
        *,
        render: bool = False,
        progress: Any = None,
    ) -> ExtractionResult:
        self.calls.append({"url": url, "kind": kind, "mode": mode, "render": render})
        if self.error is not None:
            raise self.error
        if progress is not None:
            possible = progress("fixture_progress", {"step": 1})
            if isinstance(possible, Awaitable):
                await possible
        return extraction_result(str(mode.value))


@asynccontextmanager
async def app_client(app: FastAPI):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        yield client


@pytest.mark.asyncio
async def test_health_and_compatibility_alias_do_not_require_authentication() -> None:
    service = StubService()
    app = create_app(Settings(api_key="secret"), service=service)
    async with app_client(app) as client:
        health = await client.get("/health", headers={"X-Request-ID": "fixture-request-1"})
        alias = await client.get("/healthz")

    assert health.status_code == alias.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["deterministic"] is True
    assert health.json()["llm_configured"] is False
    assert health.json()["llm_available"] is False
    assert health.json()["renderer_enabled"] is False
    assert health.json()["renderer_available"] is False
    assert health.headers["X-Request-ID"] == "fixture-request-1"
    assert health.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.asyncio
async def test_exceptional_lifespan_exit_closes_owned_service(monkeypatch: Any) -> None:
    class OwnedService(StubService):
        def __init__(self) -> None:
            super().__init__()
            self.close_calls = 0

        async def aclose(self) -> None:
            self.close_calls += 1

    owned = OwnedService()
    monkeypatch.setattr("omniscrape.api.OmniScrape.from_settings", lambda _settings: owned)
    app = create_app(Settings())

    with pytest.raises(RuntimeError, match="fixture lifespan failure"):
        async with app.router.lifespan_context(app):
            raise RuntimeError("fixture lifespan failure")

    assert owned.close_calls == 1


@pytest.mark.asyncio
async def test_falsey_injected_service_is_used_exactly() -> None:
    class FalseyService(StubService):
        def __bool__(self) -> bool:
            return False

    service = FalseyService()
    app = create_app(Settings(), service=service)
    async with app_client(app) as client:
        response = await client.post("/v1/extract", json={"url": URL})

    assert response.status_code == 200
    assert app.state.scraper is service
    assert len(service.calls) == 1


@pytest.mark.asyncio
async def test_host_allow_list_blocks_dns_rebinding_authorities() -> None:
    app = create_app(Settings(), service=StubService())
    async with app_client(app) as client:
        attacker = await client.get("/health", headers={"Host": "attacker.example"})
        ipv4 = await client.get("/health", headers={"Host": "127.0.0.1:8000"})
        localhost = await client.get("/health", headers={"Host": "localhost:8000"})
        ipv6 = await client.get("/health", headers={"Host": "[::1]:8000"})

    assert attacker.status_code == 400
    assert attacker.json()["error"]["code"] == "invalid_host"
    assert attacker.headers["X-Content-Type-Options"] == "nosniff"
    assert ipv4.status_code == localhost.status_code == ipv6.status_code == 200


@pytest.mark.asyncio
async def test_explicit_host_allow_list_supports_exact_hosts_and_ports() -> None:
    app = create_app(Settings(allowed_hosts=("api.example.test:8443",)), service=StubService())
    async with app_client(app) as client:
        allowed = await client.get("/health", headers={"Host": "api.example.test:8443"})
        wrong_port = await client.get("/health", headers={"Host": "api.example.test:9443"})
        suffix = await client.get("/health", headers={"Host": "api.example.test.evil:8443"})

    assert allowed.status_code == 200
    assert wrong_port.json()["error"]["code"] == "invalid_host"
    assert suffix.json()["error"]["code"] == "invalid_host"


def test_direct_settings_reject_malformed_allowed_host_before_serving() -> None:
    with pytest.raises(ValueError, match="explicit Host authorities"):
        create_app(Settings(allowed_hosts=("api.example:notaport",)), service=StubService())


@pytest.mark.asyncio
async def test_health_distinguishes_provider_configuration_from_readiness() -> None:
    class Provider:
        def __init__(self, available: bool) -> None:
            self._available = available

        def available(self) -> bool:
            return self._available

    service = StubService()
    service.provider = Provider(available=False)
    app = create_app(Settings(), service=service)
    async with app_client(app) as client:
        unavailable = await client.get("/health")

    service.provider = Provider(available=True)
    async with app_client(app) as client:
        ready = await client.get("/health")

    assert unavailable.json()["llm_configured"] is True
    assert unavailable.json()["llm_available"] is False
    assert ready.json()["llm_configured"] is True
    assert ready.json()["llm_available"] is True


@pytest.mark.asyncio
async def test_health_accepts_minimal_injected_service_without_provider_attribute() -> None:
    class MinimalService:
        async def extract(self, *_args: Any, **_kwargs: Any) -> ExtractionResult:
            return extraction_result()

    app = create_app(Settings(), service=MinimalService())
    async with app_client(app) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["llm_configured"] is False
    assert response.json()["llm_available"] is False


@pytest.mark.asyncio
async def test_disabled_renderer_health_does_not_probe_browser(monkeypatch: Any) -> None:
    async def unexpected_probe() -> bool:
        raise AssertionError("disabled API rendering must not launch a browser probe")

    monkeypatch.setattr("omniscrape.api.renderer_available", unexpected_probe)
    app = create_app(Settings(enable_api_rendering=False), service=StubService())
    async with app_client(app) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["renderer_enabled"] is False
    assert response.json()["renderer_available"] is False


@pytest.mark.asyncio
async def test_enabled_renderer_health_reports_runtime_readiness(monkeypatch: Any) -> None:
    probes = 0

    async def ready() -> bool:
        nonlocal probes
        probes += 1
        return True

    monkeypatch.setattr("omniscrape.api.renderer_available", ready)
    app = create_app(Settings(enable_api_rendering=True), service=StubService())
    async with app_client(app) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["renderer_enabled"] is True
    assert response.json()["renderer_available"] is True
    assert probes == 1


@pytest.mark.asyncio
async def test_enabled_renderer_health_reports_unavailable_runtime(monkeypatch: Any) -> None:
    async def unavailable() -> bool:
        return False

    monkeypatch.setattr("omniscrape.api.renderer_available", unavailable)
    app = create_app(Settings(enable_api_rendering=True), service=StubService())
    async with app_client(app) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["renderer_enabled"] is True
    assert response.json()["renderer_available"] is False


@pytest.mark.asyncio
async def test_api_key_authentication_supports_header_and_bearer() -> None:
    service = StubService()
    app = create_app(Settings(api_key="correct-key"), service=service)
    payload = {"url": URL, "kind": "article", "mode": "deterministic"}

    async with app_client(app) as client:
        missing = await client.post("/v1/extract", json=payload)
        wrong = await client.post("/v1/extract", json=payload, headers={"X-API-Key": "wrong"})
        header = await client.post(
            "/v1/extract", json=payload, headers={"X-API-Key": "correct-key"}
        )
        bearer = await client.post(
            "/v1/extract",
            json=payload,
            headers={"Authorization": "Bearer correct-key"},
        )

    assert missing.status_code == wrong.status_code == 401
    assert missing.json()["error"]["code"] == "authentication_required"
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert header.status_code == bearer.status_code == 200


@pytest.mark.asyncio
async def test_non_ascii_header_bytes_fail_authentication_without_server_error() -> None:
    service = StubService()
    app = create_app(Settings(api_key="correct-key"), service=service)
    payload = json.dumps({"url": URL, "kind": "article", "mode": "deterministic"}).encode()
    async with app_client(app) as client:
        response = await client.post(
            "/v1/extract",
            content=payload,
            headers=[
                (b"content-type", b"application/json"),
                (b"x-api-key", b"\xff"),
            ],
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"
    assert service.calls == []


@pytest.mark.asyncio
async def test_authentication_is_opt_in() -> None:
    service = StubService()
    app = create_app(Settings(api_key=None), service=service)
    async with app_client(app) as client:
        response = await client.post(
            "/v1/extract",
            json={"url": URL, "kind": "article", "mode": "deterministic"},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_omitted_api_mode_defaults_to_deterministic() -> None:
    service = StubService()
    app = create_app(Settings(), service=service)
    async with app_client(app) as client:
        response = await client.post(
            "/v1/extract",
            json={"url": URL, "kind": "article"},
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "deterministic"
    assert service.calls[0]["mode"].value == "deterministic"
    request_schema = app.openapi()["components"]["schemas"]["ExtractRequest"]
    assert request_schema["properties"]["mode"]["default"] == "deterministic"
    responses = app.openapi()["paths"]["/v1/extract"]["post"]["responses"]
    stream_responses = app.openapi()["paths"]["/v1/extract/stream"]["post"]["responses"]
    assert responses["415"]["content"]["application/json"]["schema"]
    assert responses["403"]["content"]["application/json"]["schema"]
    assert stream_responses["403"]["content"]["application/json"]["schema"]


@pytest.mark.asyncio
async def test_web_console_selects_deterministic_mode_by_default() -> None:
    app = create_app(Settings(), service=StubService())
    async with app_client(app) as client:
        response = await client.get("/")

    assert response.status_code == 200
    assert '<option value="deterministic" selected>' in response.text
    assert '<option value="auto" selected>' not in response.text
    assert 'id="render" name="render" type="checkbox" disabled' in response.text
    assert 'id="render-help"' in response.text


@pytest.mark.asyncio
async def test_web_console_uses_health_renderer_policy() -> None:
    app = create_app(Settings(), service=StubService())
    async with app_client(app) as client:
        response = await client.get("/assets/app.js")

    assert response.status_code == 200
    assert "health.renderer_enabled" in response.text
    assert "health.renderer_available" in response.text
    assert "render.disabled = !available" in response.text
    assert "Browser rendering disabled" in response.text
    assert "Browser renderer unavailable" in response.text
    assert "Browser renderer ready" in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "route",
    ["/v1/extract", "/extract", "/v1/extract/stream", "/extract-stream"],
)
async def test_api_rendering_is_rejected_before_admission_by_default(route: str) -> None:
    service = StubService()
    app = create_app(
        Settings(
            enable_api_rendering=False,
            max_concurrency=1,
            queue_timeout_seconds=0.001,
        ),
        service=service,
    )
    await app.state.extraction_slots.acquire()
    try:
        async with app_client(app) as client:
            response = await client.post(route, json={"url": URL, "render": True})
    finally:
        app.state.extraction_slots.release()

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "rendering_disabled"
    assert service.calls == []


@pytest.mark.asyncio
async def test_api_rendering_can_be_explicitly_enabled() -> None:
    service = StubService()
    app = create_app(Settings(enable_api_rendering=True), service=service)
    async with app_client(app) as client:
        response = await client.post("/v1/extract", json={"url": URL, "render": True})

    assert response.status_code == 200
    assert service.calls[0]["render"] is True


@pytest.mark.asyncio
async def test_legacy_route_and_mode_field_are_accepted() -> None:
    service = StubService()
    app = create_app(Settings(), service=service)
    async with app_client(app) as client:
        response = await client.post(
            "/extract",
            json={"url": URL, "kind": "article", "llmMode": "none"},
        )

    assert response.status_code == 200
    assert response.json()["mode"] == "deterministic"
    assert service.calls[0]["mode"].value == "deterministic"


@pytest.mark.asyncio
async def test_validation_errors_are_stable_and_do_not_echo_input() -> None:
    service = StubService()
    app = create_app(Settings(), service=service)
    async with app_client(app) as client:
        response = await client.post(
            "/v1/extract",
            json={"url": "file:///private/path", "unknown": "do-not-echo"},
        )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "private" not in response.text
    assert "do-not-echo" not in response.text


@pytest.mark.asyncio
async def test_declared_and_chunked_oversized_bodies_are_rejected_before_parsing() -> None:
    service = StubService()
    app = create_app(Settings(), service=service)

    async def oversized_chunks():
        yield b"{" + (b"x" * 9_000)
        yield b"x" * 9_000 + b"}"

    async with app_client(app) as client:
        declared = await client.post(
            "/v1/extract",
            content=b"x" * 20_000,
            headers={"Content-Type": "application/json"},
        )
        chunked = await client.post(
            "/v1/extract/stream",
            content=oversized_chunks(),
            headers={"Content-Type": "application/json"},
        )

    for response in (declared, chunked):
        assert response.status_code == 413
        assert response.json()["error"]["code"] == "request_too_large"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert service.calls == []


@pytest.mark.asyncio
async def test_body_reader_has_deadline_before_auth_or_dispatch() -> None:
    downstream_called = False
    sent: list[dict[str, Any]] = []

    async def downstream(_scope: Any, _receive: Any, _send: Any) -> None:
        nonlocal downstream_called
        downstream_called = True

    async def never_receive() -> dict[str, Any]:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def capture(message: dict[str, Any]) -> None:
        sent.append(message)

    middleware = _RequestBodyLimitMiddleware(
        downstream, max_body_bytes=16_384, body_timeout_seconds=0.001
    )
    await middleware(
        {"type": "http", "headers": []},
        never_receive,
        capture,  # type: ignore[arg-type]
    )

    assert downstream_called is False
    assert sent[0]["status"] == 408
    assert b'"code":"request_timeout"' in sent[1]["body"]


@pytest.mark.asyncio
async def test_unauthenticated_extraction_is_rejected_before_any_body_read() -> None:
    receive_calls = 0

    async def downstream(_scope: Any, _receive: Any, _send: Any) -> None:
        raise AssertionError("unauthenticated request reached the application")

    async def stalled_receive() -> dict[str, Any]:
        nonlocal receive_calls
        receive_calls += 1
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    middleware = _RequestBodyLimitMiddleware(
        downstream,
        max_body_bytes=16_384,
        body_timeout_seconds=5.0,
        api_key="fixture-key",
        max_body_readers=1,
    )

    async def attempt() -> list[dict[str, Any]]:
        sent: list[dict[str, Any]] = []

        async def capture(message: dict[str, Any]) -> None:
            sent.append(message)

        await middleware(
            {
                "type": "http",
                "method": "POST",
                "path": "/v1/extract",
                "headers": [],
            },
            stalled_receive,
            capture,  # type: ignore[arg-type]
        )
        return sent

    responses = await asyncio.gather(*(attempt() for _ in range(16)))

    assert receive_calls == 0
    assert all(messages[0]["status"] == 401 for messages in responses)
    assert all((b"www-authenticate", b"Bearer") in messages[0]["headers"] for messages in responses)


@pytest.mark.asyncio
async def test_body_reader_capacity_bounds_slow_unknown_post_paths() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    first_sent: list[dict[str, Any]] = []
    second_sent: list[dict[str, Any]] = []
    second_receive_calls = 0

    async def downstream(_scope: Any, _receive: Any, send: Any) -> None:
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def slow_receive() -> dict[str, Any]:
        entered.set()
        await release.wait()
        return {"type": "http.request", "body": b"{}", "more_body": False}

    async def unexpected_receive() -> dict[str, Any]:
        nonlocal second_receive_calls
        second_receive_calls += 1
        return {"type": "http.request", "body": b"{}", "more_body": False}

    async def capture_first(message: dict[str, Any]) -> None:
        first_sent.append(message)

    async def capture_second(message: dict[str, Any]) -> None:
        second_sent.append(message)

    middleware = _RequestBodyLimitMiddleware(
        downstream,
        max_body_bytes=16_384,
        body_timeout_seconds=5.0,
        max_body_readers=1,
    )
    scope = {"type": "http", "method": "POST", "path": "/not-a-route", "headers": []}
    first = asyncio.create_task(
        middleware(scope, slow_receive, capture_first)  # type: ignore[arg-type]
    )
    await asyncio.wait_for(entered.wait(), timeout=0.1)
    try:
        await middleware(
            scope,
            unexpected_receive,
            capture_second,  # type: ignore[arg-type]
        )
    finally:
        release.set()
        await first

    assert second_receive_calls == 0
    assert second_sent[0]["status"] == 503
    assert b'"code":"service_busy"' in second_sent[1]["body"]
    assert first_sent[0]["status"] == 204


@pytest.mark.asyncio
async def test_body_reader_coalesces_many_tiny_frames_before_dispatch() -> None:
    frames = deque(
        {"type": "http.request", "body": b"x", "more_body": index < 16_383}
        for index in range(16_384)
    )
    downstream_frames: list[dict[str, Any]] = []
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return frames.popleft() if frames else {"type": "http.disconnect"}

    async def downstream(_scope: Any, replay: Any, send: Any) -> None:
        downstream_frames.append(await replay())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def capture(message: dict[str, Any]) -> None:
        sent.append(message)

    middleware = _RequestBodyLimitMiddleware(
        downstream, max_body_bytes=16_384, body_timeout_seconds=2.0
    )
    await middleware(
        {"type": "http", "headers": []},
        receive,
        capture,  # type: ignore[arg-type]
    )

    assert len(downstream_frames) == 1
    assert downstream_frames[0] == {
        "type": "http.request",
        "body": b"x" * 16_384,
        "more_body": False,
    }
    assert sent[0]["status"] == 204


@pytest.mark.asyncio
async def test_domain_errors_hide_internal_details() -> None:
    service = StubService()
    service.error = URLSafetyError("internal resolver detail 10.0.0.1")
    app = create_app(Settings(), service=service)
    async with app_client(app) as client:
        response = await client.post(
            "/v1/extract",
            json={"url": URL, "kind": "article", "mode": "deterministic"},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsafe_url"
    assert "10.0.0.1" not in response.text
    assert response.json()["error"]["request_id"]


@pytest.mark.asyncio
async def test_unknown_route_uses_structured_error() -> None:
    app = create_app(Settings(), service=StubService())
    async with app_client(app) as client:
        response = await client.get("/not-a-route")
    assert response.status_code == 404
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_method_not_allowed_preserves_framework_allow_header() -> None:
    app = create_app(Settings(), service=StubService())
    async with app_client(app) as client:
        response = await client.get("/v1/extract")

    assert response.status_code == 405
    assert response.headers["Allow"] == "POST"
    assert response.json()["error"]["code"] == "http_error"


@pytest.mark.asyncio
async def test_unexpected_errors_are_generic(caplog: pytest.LogCaptureFixture) -> None:
    service = StubService()
    service.error = RuntimeError("database password fixture-secret")
    app = create_app(Settings(), service=service)
    async with app_client(app) as client:
        response = await client.post(
            "/v1/extract",
            json={"url": URL, "kind": "article", "mode": "deterministic"},
        )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "fixture-secret" not in response.text
    assert "fixture-secret" not in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.asyncio
async def test_queue_timeout_returns_busy_error() -> None:
    app = create_app(
        Settings(max_concurrency=1, queue_timeout_seconds=0.001),
        service=StubService(),
    )
    await app.state.extraction_slots.acquire()
    try:
        async with app_client(app) as client:
            response = await client.post(
                "/v1/extract",
                json={"url": URL, "kind": "article", "mode": "deterministic"},
            )
    finally:
        app.state.extraction_slots.release()
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_busy"


@pytest.mark.asyncio
async def test_stream_emits_named_progress_and_terminal_complete_event() -> None:
    app = create_app(Settings(), service=StubService())
    async with app_client(app) as client:
        response = await client.post(
            "/v1/extract/stream",
            json={"url": URL, "kind": "article", "mode": "deterministic"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: started\n" in response.text
    assert "event: fixture_progress\n" in response.text
    assert "event: complete\n" in response.text
    assert '"success":true' in response.text


@pytest.mark.asyncio
async def test_stream_converts_domain_failure_to_terminal_error_event() -> None:
    service = StubService()
    service.error = URLSafetyError("internal address")
    app = create_app(Settings(), service=service)
    async with app_client(app) as client:
        response = await client.post(
            "/v1/extract/stream",
            json={"url": URL, "kind": "article", "mode": "deterministic"},
        )

    assert response.status_code == 200
    assert "event: error\n" in response.text
    assert '"code":"unsafe_url"' in response.text
    assert "internal address" not in response.text


@pytest.mark.asyncio
async def test_stream_converts_unexpected_failure_to_generic_error_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = StubService()
    service.error = RuntimeError("secret stream failure")
    app = create_app(Settings(), service=service)
    async with app_client(app) as client:
        response = await client.post(
            "/v1/extract/stream",
            json={"url": URL, "kind": "article", "mode": "deterministic"},
        )
    assert "event: error\n" in response.text
    assert '"code":"internal_error"' in response.text
    assert "secret stream failure" not in response.text
    assert "secret stream failure" not in caplog.text
    assert "RuntimeError" in caplog.text
