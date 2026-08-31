"""FastAPI application factory for the OmniScrape service."""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, AnyHttpUrl, BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import __version__
from ._tasking import BoundedAdmission
from .config import Settings, _normalize_host_authorities, _parse_host_authority
from .errors import OmniScrapeError, RenderingDisabledError
from .fetcher import renderer_available
from .models import (
    ContentKind,
    ErrorBody,
    ErrorResponse,
    ExtractionMode,
    ExtractionResult,
    HealthResponse,
    jsonable,
)
from .pipeline import OmniScrape

logger = logging.getLogger(__name__)
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
_SENTINEL = object()
_MAX_REQUEST_BODY_BYTES = 16_384
_LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "::1")
_PROTECTED_PATHS = frozenset({"/v1/extract", "/extract", "/v1/extract/stream", "/extract-stream"})


def _scope_has_valid_api_key(scope: Scope, expected: str) -> bool:
    headers = scope.get("headers") or []
    api_keys = [value for name, value in headers if name.lower() == b"x-api-key"]
    authorizations = [value for name, value in headers if name.lower() == b"authorization"]
    if len(api_keys) > 1 or len(authorizations) > 1:
        return False
    supplied = api_keys[0].strip() if api_keys else b""
    if not supplied and authorizations:
        authorization = authorizations[0].strip()
        if authorization[:7].lower() == b"bearer ":
            supplied = authorization[7:].strip()
    return bool(supplied) and hmac.compare_digest(supplied, expected.encode("utf-8"))


class _HostValidationMiddleware:
    """Block DNS-rebinding Host authorities before any application work."""

    def __init__(self, app: ASGIApp, allowed_hosts: tuple[str, ...]) -> None:
        self.app = app
        self.allowed = tuple(
            _parse_host_authority(item, allow_unbracketed_ip=True) for item in allowed_hosts
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        values = [value for name, value in scope.get("headers") or [] if name.lower() == b"host"]
        try:
            if len(values) != 1:
                raise ValueError("Exactly one Host header is required.")
            requested = _parse_host_authority(values[0].decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            requested = ("", None)
        allowed = any(
            requested[0] == host and (port is None or requested[1] == port)
            for host, port in self.allowed
        )
        if not allowed:
            state = scope.get("state") or {}
            request_id = str(state.get("request_id") or uuid.uuid4().hex)
            response = JSONResponse(
                status_code=400,
                content=jsonable(
                    ErrorResponse(
                        error=ErrorBody(
                            code="invalid_host",
                            message="The request Host authority is not allowed.",
                            request_id=request_id,
                        )
                    )
                ),
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)


class _RequestBodyLimitMiddleware:
    """Authenticate early, then bound body readers, bytes, frames, and time."""

    def __init__(
        self,
        app: ASGIApp,
        max_body_bytes: int,
        body_timeout_seconds: float,
        *,
        api_key: str | None = None,
        max_body_readers: int = 8,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.body_timeout_seconds = body_timeout_seconds
        self.api_key = api_key
        self.max_body_readers = max(1, max_body_readers)
        self._active_body_readers = 0

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        code: str,
        message: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        state = scope.get("state") or {}
        request_id = str(state.get("request_id") or uuid.uuid4().hex)
        response = JSONResponse(
            status_code=status_code,
            content=jsonable(
                ErrorResponse(
                    error=ErrorBody(
                        code=code,
                        message=message,
                        request_id=request_id,
                    )
                )
            ),
            headers={"Connection": "close", **(headers or {})},
        )
        await response(scope, receive, send)

    async def _read_and_dispatch(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                declared_size = int(declared)
            except ValueError:
                declared_size = self.max_body_bytes + 1
            if declared_size < 0 or declared_size > self.max_body_bytes:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=413,
                    code="request_too_large",
                    message="The request body exceeds the service limit.",
                )
                return

        body = bytearray()
        buffered: list[Message] = []
        deadline = asyncio.get_running_loop().time() + self.body_timeout_seconds
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=408,
                    code="request_timeout",
                    message="The request body was not received in time.",
                )
                return
            try:
                message = await asyncio.wait_for(receive(), timeout=remaining)
            except asyncio.TimeoutError:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=408,
                    code="request_timeout",
                    message="The request body was not received in time.",
                )
                return
            if message["type"] != "http.request":
                buffered.append(message)
                break
            body.extend(message.get("body", b""))
            if len(body) > self.max_body_bytes:
                await self._reject(
                    scope,
                    receive,
                    send,
                    status_code=413,
                    code="request_too_large",
                    message="The request body exceeds the service limit.",
                )
                return
            if not message.get("more_body", False):
                break

        buffered.insert(
            0,
            {"type": "http.request", "body": bytes(body), "more_body": False},
        )

        index = 0

        async def replay_receive() -> Message:
            nonlocal index
            if index < len(buffered):
                message = buffered[index]
                index += 1
                return message
            return await receive()

        await self.app(scope, replay_receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method", "POST")).upper()
        if method not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path", ""))
        if (
            self.api_key
            and path in _PROTECTED_PATHS
            and not _scope_has_valid_api_key(scope, self.api_key)
        ):
            await self._reject(
                scope,
                receive,
                send,
                status_code=401,
                code="authentication_required",
                message="A valid API key is required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            return

        # Check and increment without an intervening await. ASGI application code
        # runs cooperatively on one event loop, making this an immediate admission
        # decision rather than an unbounded queue of body-reader waiters.
        if self._active_body_readers >= self.max_body_readers:
            await self._reject(
                scope,
                receive,
                send,
                status_code=503,
                code="service_busy",
                message="The service is busy; try again shortly.",
            )
            return
        self._active_body_readers += 1
        try:
            await self._read_and_dispatch(scope, receive, send)
        finally:
            self._active_body_readers -= 1


class ExtractRequest(BaseModel):
    """API input with a validation-only alias for the original ``llmMode`` key."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    url: AnyHttpUrl
    kind: ContentKind = ContentKind.ARTICLE
    mode: ExtractionMode = Field(
        default=ExtractionMode.DETERMINISTIC,
        validation_alias=AliasChoices("mode", "llmMode"),
    )
    render: bool = Field(
        default=False,
        description=(
            "Execute target JavaScript with the optional browser renderer. The HTTP API "
            "returns 403 unless the server explicitly enables this policy."
        ),
    )


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "")) or uuid.uuid4().hex


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=_request_id(request))
    )
    return JSONResponse(status_code=status_code, content=jsonable(body), headers=headers)


def _sse(event: str, data: Mapping[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _provider_available(provider: Any | None) -> bool:
    """Return truthful provider readiness while supporting injected providers."""

    if provider is None:
        return False
    probe = getattr(provider, "available", None)
    if probe is None:
        return True
    try:
        return bool(probe())
    except Exception:
        return False


def create_app(
    settings: Settings | None = None,
    *,
    service: OmniScrape | Any | None = None,
) -> FastAPI:
    """Create an isolated application with bounded concurrency and safe errors."""

    resolved = settings if settings is not None else Settings.from_env()
    allowed_hosts = _normalize_host_authorities(
        tuple(dict.fromkeys((*_LOOPBACK_HOSTS, *(resolved.allowed_hosts or ()))))
    )
    owns_service = service is None
    scraper = service if service is not None else OmniScrape.from_settings(resolved)
    admission = BoundedAdmission(resolved.max_concurrency, label="API extraction")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            if owns_service:
                close = getattr(scraper, "aclose", None)
                if close is not None:
                    result = close()
                    if isinstance(result, Awaitable):
                        await result

    app = FastAPI(
        title="OmniScrape",
        summary="Safe, typed article and product extraction",
        description=(
            "Deterministic structured-data/readability extraction with an optional "
            "provider fallback. Outbound requests are restricted to public HTTP(S) hosts."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.state.settings = resolved
    app.state.scraper = scraper
    app.state.extraction_slots = admission
    web_root = Path(__file__).with_name("web")
    app.mount("/assets", StaticFiles(directory=web_root), name="assets")
    app.add_middleware(
        _RequestBodyLimitMiddleware,
        max_body_bytes=_MAX_REQUEST_BODY_BYTES,
        body_timeout_seconds=resolved.request_body_timeout_seconds,
        api_key=resolved.api_key,
        max_body_readers=resolved.max_concurrency,
    )
    app.add_middleware(
        _HostValidationMiddleware,
        allowed_hosts=allowed_hosts,
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Any]]
    ) -> Any:
        incoming = request.headers.get("x-request-id", "")
        request.state.request_id = incoming if _REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path in {
            "/v1/extract",
            "/extract",
            "/v1/extract/stream",
            "/extract-stream",
        }:
            response.headers["Cache-Control"] = "no-store, no-transform"
        if request.url.path in {"/docs", "/redoc"}:
            # FastAPI's generated documentation bootstraps its CDN bundle inline.
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "img-src 'self' data: https://fastapi.tiangolo.com; connect-src 'self'; "
                "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
            )
        return response

    @app.exception_handler(OmniScrapeError)
    async def known_error(request: Request, exc: OmniScrapeError) -> JSONResponse:
        return _error_response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.public_message,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
        return _error_response(
            request,
            status_code=422,
            code="invalid_request",
            message="The request body is invalid.",
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        safe_headers = {
            key: value
            for key, value in (exc.headers or {}).items()
            if key.lower() in {"allow", "www-authenticate", "retry-after"}
        }
        if exc.status_code == 401:
            return _error_response(
                request,
                status_code=401,
                code="authentication_required",
                message="A valid API key is required.",
                headers=safe_headers,
            )
        return _error_response(
            request,
            status_code=exc.status_code,
            code="http_error",
            message="The request could not be completed.",
            headers=safe_headers,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled OmniScrape API error (type=%s)", type(exc).__name__)
        return _error_response(
            request,
            status_code=500,
            code="internal_error",
            message="An unexpected server error occurred.",
        )

    async def require_api_key(request: Request) -> None:
        expected = resolved.api_key
        if not expected:
            return
        if not _scope_has_valid_api_key(request.scope, expected):
            raise HTTPException(status_code=401, headers={"WWW-Authenticate": "Bearer"})

    async def limited_extract(
        payload: ExtractRequest,
        *,
        progress: Callable[[str, Mapping[str, Any]], Awaitable[None]] | None = None,
    ) -> ExtractionResult:
        if payload.render and not resolved.enable_api_rendering:
            raise RenderingDisabledError()
        await admission.acquire(timeout=resolved.queue_timeout_seconds)
        try:
            return await scraper.extract(
                str(payload.url),
                payload.kind,
                payload.mode,
                render=payload.render,
                progress=progress,
            )
        finally:
            admission.release()

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    @app.get("/healthz", response_model=HealthResponse, tags=["system"], include_in_schema=False)
    async def health() -> HealthResponse:
        provider = getattr(scraper, "provider", None)
        rendering_enabled = resolved.enable_api_rendering
        return HealthResponse(
            version=__version__,
            llm_configured=provider is not None,
            llm_available=_provider_available(provider),
            renderer_enabled=rendering_enabled,
            renderer_available=rendering_enabled and await renderer_available(),
        )

    @app.get("/", include_in_schema=False, response_class=FileResponse)
    async def homepage() -> FileResponse:
        return FileResponse(web_root / "index.html", media_type="text/html")

    @app.post(
        "/v1/extract",
        response_model=ExtractionResult,
        responses={
            400: {"model": ErrorResponse},
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            408: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            415: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
        tags=["extraction"],
    )
    @app.post("/extract", response_model=ExtractionResult, include_in_schema=False)
    async def extract_endpoint(
        payload: ExtractRequest, _: None = Depends(require_api_key)
    ) -> ExtractionResult:
        return await limited_extract(payload)

    @app.post(
        "/v1/extract/stream",
        responses={
            200: {
                "content": {"text/event-stream": {}},
                "description": "Named progress events followed by complete or error.",
            },
            401: {"model": ErrorResponse},
            403: {"model": ErrorResponse},
            408: {"model": ErrorResponse},
            413: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
        tags=["extraction"],
    )
    @app.post("/extract-stream", include_in_schema=False)
    async def extract_stream_endpoint(
        payload: ExtractRequest, request: Request, _: None = Depends(require_api_key)
    ) -> StreamingResponse:
        if payload.render and not resolved.enable_api_rendering:
            raise RenderingDisabledError()
        queue: asyncio.Queue[tuple[str, Mapping[str, Any]] | object] = asyncio.Queue(maxsize=32)

        async def progress(event: str, data: Mapping[str, Any]) -> None:
            await queue.put((event, data))

        async def produce() -> None:
            try:
                result = await limited_extract(payload, progress=progress)
                await queue.put(("complete", jsonable(result)))
            except asyncio.CancelledError:
                raise
            except OmniScrapeError as exc:
                await queue.put(
                    (
                        "error",
                        {
                            "code": exc.code,
                            "message": exc.public_message,
                            "request_id": _request_id(request),
                        },
                    )
                )
            except Exception as exc:
                logger.error("Unhandled OmniScrape SSE error (type=%s)", type(exc).__name__)
                await queue.put(
                    (
                        "error",
                        {
                            "code": "internal_error",
                            "message": "An unexpected server error occurred.",
                            "request_id": _request_id(request),
                        },
                    )
                )
            finally:
                await queue.put(_SENTINEL)

        async def events() -> AsyncIterator[str]:
            producer = asyncio.create_task(produce(), name="omniscrape-sse-extraction")
            try:
                yield _sse("started", {"request_id": _request_id(request)})
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except asyncio.TimeoutError:
                        if await request.is_disconnected():
                            break
                        yield ": keep-alive\n\n"
                        continue
                    if item is _SENTINEL or not isinstance(item, tuple):
                        break
                    event, data = item
                    yield _sse(event, data)
                    if event in {"complete", "error"}:
                        break
            finally:
                if not producer.done():
                    producer.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await producer

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    return app


__all__ = ["ExtractRequest", "create_app"]
