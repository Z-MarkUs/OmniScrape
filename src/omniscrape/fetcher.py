"""Bounded, redirect-aware HTTP fetching with an optional browser renderer."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import ipaddress
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from ._tasking import (
    MAX_TASK_CAPACITY,
    BoundedTaskSet,
    await_hard_deadline,
    await_retained_cleanup,
    create_bounded_task,
    retain_task,
    wait_without_cancelling,
)
from .config import _normalize_hostname, _normalize_outbound_host_authorities
from .errors import FetchError, ResponseTooLargeError, UnsupportedContentError, URLSafetyError
from .security import (
    Resolver,
    ValidatedURL,
    default_resolver,
    enforce_outbound_target,
    validate_peer_address,
    validate_url_async,
)

_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})
_HTML_CONTENT_TYPES = frozenset(
    {"text/html", "application/xhtml+xml", "text/plain", "application/xml", "text/xml"}
)
_RENDERER_PROBE_TIMEOUT_SECONDS = 5.0
_SHUTDOWN_GRACE_SECONDS = 0.1
_GLOBAL_FETCH_TASKS = BoundedTaskSet(MAX_TASK_CAPACITY, label="Global outbound fetch")
_GLOBAL_RENDER_TASKS = BoundedTaskSet(2, label="Global browser render")
_RENDERER_PROBE_TASKS = BoundedTaskSet(1, label="Renderer readiness probe")
_DEFERRED_SHUTDOWN_TASKS: set[asyncio.Task[Any]] = set()


@dataclass(frozen=True, slots=True)
class FetcherConfig:
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 15.0
    write_timeout_seconds: float = 5.0
    pool_timeout_seconds: float = 5.0
    max_response_bytes: int = 2_000_000
    max_redirects: int = 5
    total_timeout_seconds: float = 30.0
    user_agent: str = "OmniScrape/0.3 (+https://github.com/Z-MarkUs/OmniScrape)"
    render_timeout_ms: int = 15_000
    max_render_requests: int = 128
    max_render_nodes: int = 50_000
    max_inflight_tasks: int = 8
    max_render_concurrency: int = 2
    outbound_allowed_hosts: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        for name in (
            "connect_timeout_seconds",
            "read_timeout_seconds",
            "write_timeout_seconds",
            "pool_timeout_seconds",
            "total_timeout_seconds",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or float(value) <= 0
                or float(value) > 300
            ):
                raise ValueError(f"{name} must be finite and between 0 and 300.")
        integer_limits = {
            "max_response_bytes": (1, None),
            "max_redirects": (0, 20),
            "render_timeout_ms": (1, 120_000),
            "max_render_requests": (1, 1_024),
            "max_render_nodes": (1, 1_000_000),
            "max_inflight_tasks": (1, MAX_TASK_CAPACITY),
            "max_render_concurrency": (1, 2),
        }
        for name, (minimum, maximum) in integer_limits.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < minimum
                or (maximum is not None and value > maximum)
            ):
                raise ValueError(f"{name} is outside its supported integer range.")
        if not isinstance(self.user_agent, str) or not self.user_agent.strip():
            raise ValueError("user_agent must be a non-empty string.")
        if self.outbound_allowed_hosts is not None:
            if not isinstance(self.outbound_allowed_hosts, tuple):
                raise ValueError("outbound_allowed_hosts must be a tuple of explicit authorities.")
            object.__setattr__(
                self,
                "outbound_allowed_hosts",
                _normalize_outbound_host_authorities(self.outbound_allowed_hosts),
            )


class RedirectHop(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status_code: int
    from_url: AnyHttpUrl
    to_url: AnyHttpUrl


class FetchResult(BaseModel):
    """A successfully fetched document and real transport measurements."""

    model_config = ConfigDict(extra="forbid")

    requested_url: AnyHttpUrl
    final_url: AnyHttpUrl
    status_code: int
    html: str
    content_type: str | None = None
    encoding: str
    byte_count: int = Field(ge=0)
    redirects: list[RedirectHop] = Field(default_factory=list)
    elapsed_ms: float = Field(ge=0)
    rendered: bool = False


class Renderer(Protocol):
    async def fetch(self, url: str) -> FetchResult:
        """Render and return a validated public web page."""


class OutboundPolicyRenderer(Renderer, Protocol):
    """Renderer that explicitly enforces one normalized outbound host policy."""

    @property
    def outbound_allowed_hosts(self) -> tuple[str, ...] | None:
        """Return the exact policy enforced by every renderer-owned request."""


def _require_renderer_outbound_policy(
    renderer: Renderer,
    allowed_hosts: tuple[str, ...] | None,
) -> None:
    """Reject policy-unaware injected renderers before they can perform I/O."""

    if allowed_hosts is None:
        return
    try:
        renderer_policy = cast(OutboundPolicyRenderer, renderer).outbound_allowed_hosts
    except Exception as exc:
        raise ValueError(
            "A custom renderer used with outbound_allowed_hosts must advertise "
            "the identical normalized policy via outbound_allowed_hosts."
        ) from exc
    if renderer_policy != allowed_hosts:
        raise ValueError(
            "A custom renderer used with outbound_allowed_hosts must advertise "
            "the identical normalized policy via outbound_allowed_hosts."
        )


def renderer_package_available() -> bool:
    """Return whether the optional Playwright Python package can be imported."""

    try:
        return importlib.util.find_spec("playwright.async_api") is not None
    except (ImportError, AttributeError, ValueError):
        return False


_renderer_probe_result: bool | None = None
_renderer_probe_task: asyncio.Task[bool] | None = None


def _finish_renderer_probe(completed: asyncio.Task[bool]) -> None:
    global _renderer_probe_result, _renderer_probe_task
    if _renderer_probe_task is not completed:
        return
    _renderer_probe_task = None
    if completed.cancelled():
        return
    try:
        _renderer_probe_result = completed.result()
    except Exception:
        _renderer_probe_result = False


async def _stop_playwright(manager: Any) -> None:
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await manager.__aexit__(None, None, None)


async def _start_playwright(factory: Any, *, name: str) -> tuple[Any, Any]:
    """Start Playwright and clean a partially started driver on cancellation."""

    manager = factory()
    try:
        playwright = await manager.start()
    except BaseException:
        await await_retained_cleanup(
            _stop_playwright(manager),
            tasks=_DEFERRED_SHUTDOWN_TASKS,
            name=f"{name}-failed-start-stop",
        )
        raise
    return manager, playwright


async def _probe_renderer() -> bool:
    """Launch Chromium once; callers share this work through ``renderer_available``."""

    if not renderer_package_available():
        return False

    async def launch_and_close() -> bool:
        from playwright.async_api import async_playwright

        manager, playwright = await _start_playwright(
            async_playwright, name="omniscrape-renderer-probe"
        )
        try:
            browser = await playwright.chromium.launch(
                headless=True,
                chromium_sandbox=True,
            )
            await await_retained_cleanup(
                browser.close(),
                tasks=_DEFERRED_SHUTDOWN_TASKS,
                name="omniscrape-renderer-probe-close",
            )
            return True
        finally:
            await await_retained_cleanup(
                _stop_playwright(manager),
                tasks=_DEFERRED_SHUTDOWN_TASKS,
                name="omniscrape-renderer-probe-driver-stop",
            )

    try:
        task = create_bounded_task(
            launch_and_close(),
            registries=(_RENDERER_PROBE_TASKS,),
            name="omniscrape-renderer-probe-launch",
        )
        return await await_hard_deadline(
            task,
            timeout=_RENDERER_PROBE_TIMEOUT_SECONDS,
        )
    except Exception:
        return False


async def renderer_available(*, refresh: bool = False) -> bool:
    """Probe once whether Playwright and its Chromium binary can actually launch.

    Concurrent first health checks share one in-flight launch instead of each
    spawning a browser process.
    """

    global _renderer_probe_result, _renderer_probe_task
    if _renderer_probe_result is not None and not refresh:
        return _renderer_probe_result

    task = _renderer_probe_task
    if task is not None and task.done():
        _finish_renderer_probe(task)
        if _renderer_probe_result is not None and not refresh:
            return _renderer_probe_result
        task = None
    if task is None:
        task = asyncio.create_task(_probe_renderer(), name="omniscrape-renderer-probe")
        _renderer_probe_task = task
        task.add_done_callback(_finish_renderer_probe)
    try:
        result = await asyncio.shield(task)
    finally:
        if task.done() and _renderer_probe_task is task:
            _renderer_probe_task = None
    _renderer_probe_result = result
    return result


def _content_type(headers: Mapping[str, str]) -> str | None:
    value = headers.get("content-type")
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower() or None


def _peer_address(response: httpx.Response) -> str | None:
    """Best-effort peer inspection supported by httpcore's network stream."""

    stream = response.extensions.get("network_stream")
    if stream is None or not hasattr(stream, "get_extra_info"):
        return None
    for key in ("server_addr", "peername"):
        try:
            peer = stream.get_extra_info(key)
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
            continue
        if isinstance(peer, tuple) and peer:
            return str(peer[0])
        if isinstance(peer, str):
            return peer
    try:
        sock = stream.get_extra_info("socket")
        peer = sock.getpeername() if sock is not None else None
    except Exception:
        return None
    return str(peer[0]) if isinstance(peer, tuple) and peer else None


def _display_host(host: str) -> str:
    return f"[{host}]" if ":" in host else host


def _host_header(validated: ValidatedURL) -> str:
    default_port = 80 if validated.scheme == "http" else 443
    displayed = _display_host(validated.host)
    return displayed if validated.port == default_port else f"{displayed}:{validated.port}"


def _pinned_url(
    validated: ValidatedURL,
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> str:
    """Build a transport URL that cannot trigger a second DNS lookup."""

    parts = urlsplit(validated.url)
    displayed = _display_host(str(address))
    default_port = 80 if validated.scheme == "http" else 443
    netloc = displayed if validated.port == default_port else f"{displayed}:{validated.port}"
    return urlunsplit((validated.scheme, netloc, parts.path, parts.query, ""))


def _chromium_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str:
    return _display_host(str(address))


def _chromium_launch_args(
    validated: ValidatedURL,
    address: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> list[str]:
    """Build a fail-closed browser network policy around one pinned authority."""

    # Rules are evaluated in declaration order. The exact host must be first;
    # every other hostname (including IP literals used by speculative fetches)
    # fails resolution in Chromium's mapped host resolver.
    resolver_rules = f"MAP {validated.host} {_chromium_address(address)}, MAP * ^NOTFOUND"
    return [
        f"--host-resolver-rules={resolver_rules}",
        "--host-resolver-retry-attempts=0",
        # Chromium treats this explicit direct proxy configuration differently
        # from --no-proxy-server when a fail-closed wildcard resolver is active.
        "--proxy-server=direct://",
        "--proxy-bypass-list=*",
        "--dns-prefetch-disable",
        "--disable-quic",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-domain-reliability",
        "--disable-sync",
        # Chromium's own holdback features stop speculative preconnect, prefetch,
        # and prerender work that can bypass Playwright request routing.
        "--enable-features=PreloadingHoldback,Prerender2Holdback",
        "--disable-features=Prerender2,SpeculationRulesPrefetchProxy",
        (
            "--disable-blink-features=SpeculationRules,"
            "SpeculationRulesDocumentRules,SpeculationRulesFetchFromHeader"
        ),
        "--metrics-recording-only",
        "--no-first-run",
    ]


def _dom_budget_expression(max_nodes: int, max_content_units: int) -> str:
    """Build an atomic, bounded serializer that never calls native ``outerHTML``.

    Chromium's native serializer can synthesize namespace declarations and
    expand characters differently for HTML and XML documents. Building a
    controlled extraction-only representation keeps both allocation and UTF-8
    accounting within the configured byte cap before data crosses CDP.
    """

    return f"""
        (() => {{
          const maxNodes = {max(1, max_nodes)};
          const maxContentBytes = {max(1, max_content_units)};
          let nodeCount = 0;
          let contentBytes = 0;
          let wireBytes = 0;
          let documentURL = null;
          const chunks = [];
          let buffer = '';
          const result = (html) => ({{
            nodeCount,
            contentBytes,
            wireBytes,
            exceeded: (
              nodeCount > maxNodes || contentBytes > maxContentBytes ||
              wireBytes > maxContentBytes
            ),
            ...(typeof documentURL === 'string' ? {{ documentURL }} : {{}}),
            ...(typeof html === 'string' ? {{ html }} : {{}}),
          }});
          const flush = () => {{
            if (buffer) {{
              chunks.push(buffer);
              buffer = '';
            }}
          }};
          const wireSize = (unit, bytes) => {{
            const code = unit.charCodeAt(0);
            return code <= 0x1f
              ? 6
              : (code === 0x22 || code === 0x5c
                ? 2
                : (code <= 0x7f ? 1 : (unit.length === 2 ? 12 : 6)));
          }};
          const appendUnit = (unit, bytes) => {{
            const wireIncrement = wireSize(unit, bytes);
            if (
              contentBytes + bytes > maxContentBytes ||
              wireBytes + wireIncrement > maxContentBytes
            ) {{
              contentBytes += bytes;
              wireBytes += wireIncrement;
              return false;
            }}
            contentBytes += bytes;
            wireBytes += wireIncrement;
            buffer += unit;
            if (buffer.length >= 8192) flush();
            return true;
          }};
          const appendCharacter = (text, index) => {{
            const code = text.charCodeAt(index);
            if (code <= 0x7f) return appendUnit(text[index], 1) ? 1 : 0;
            if (code <= 0x7ff) return appendUnit(text[index], 2) ? 1 : 0;
            if (
              code >= 0xd800 && code <= 0xdbff &&
              index + 1 < text.length &&
              text.charCodeAt(index + 1) >= 0xdc00 &&
              text.charCodeAt(index + 1) <= 0xdfff
            ) {{
              return appendUnit(text.slice(index, index + 2), 4) ? 2 : 0;
            }}
            return appendUnit('\ufffd', 3) ? 1 : 0;
          }};
          const appendRaw = (value) => {{
            const text = String(value == null ? '' : value);
            for (let index = 0; index < text.length;) {{
              const width = appendCharacter(text, index);
              if (!width) return false;
              index += width;
            }}
            return true;
          }};
          const appendEscaped = (value, attribute = false) => {{
            const text = String(value == null ? '' : value);
            for (let index = 0; index < text.length;) {{
              let escaped = null;
              const code = text.charCodeAt(index);
              if (code === 0x26) escaped = '&amp;';
              else if (code === 0x3c) escaped = '&lt;';
              else if (code === 0x3e) escaped = '&gt;';
              else if (attribute && code === 0x22) escaped = '&quot;';
              if (escaped !== null) {{
                if (!appendRaw(escaped)) return false;
                index += 1;
                continue;
              }}
              const width = appendCharacter(text, index);
              if (!width) return false;
              index += width;
            }}
            return true;
          }};
          const appendJsonScript = (value, state) => {{
            const text = String(value == null ? '' : value);
            for (let index = 0; index < text.length;) {{
              const character = text[index];
              if (state.pending) {{
                const candidate = state.pending + character;
                if ('</script'.startsWith(candidate.toLowerCase())) {{
                  state.pending = candidate;
                  index += 1;
                  if (state.pending.length === 8) {{
                    if (!appendRaw('\\\\u003c') || !appendRaw(state.pending.slice(1))) {{
                      return false;
                    }}
                    state.pending = '';
                  }}
                  continue;
                }}
                if (!appendRaw(state.pending)) return false;
                state.pending = '';
                continue;
              }}
              if (character === '<') {{
                state.pending = '<';
                index += 1;
                continue;
              }}
              const width = appendCharacter(text, index);
              if (!width) return false;
              index += width;
            }}
            return true;
          }};
          const flushJsonState = (state) => {{
            if (!state || !state.pending) return true;
            const pending = state.pending;
            state.pending = '';
            return appendRaw(pending);
          }};
          const captureDocumentURL = () => {{
            const value = String(document.URL || '');
            if (value.length > 8192) {{
              wireBytes = maxContentBytes + 1;
              return false;
            }}
            for (let index = 0; index < value.length;) {{
              const code = value.charCodeAt(index);
              let unit = value[index];
              let bytes = code <= 0x7f ? 1 : (code <= 0x7ff ? 2 : 3);
              let width = 1;
              if (
                code >= 0xd800 && code <= 0xdbff &&
                index + 1 < value.length &&
                value.charCodeAt(index + 1) >= 0xdc00 &&
                value.charCodeAt(index + 1) <= 0xdfff
              ) {{
                unit = value.slice(index, index + 2);
                bytes = 4;
                width = 2;
              }}
              wireBytes += wireSize(unit, bytes);
              if (wireBytes > maxContentBytes) return false;
              index += width;
            }}
            documentURL = value;
            return true;
          }};
          const frames = [{{
            node: document,
            entered: false,
            nextChild: null,
            template: null,
            closingTag: null,
            mode: 'normal',
            childMode: 'normal',
            jsonState: null,
            childJsonState: null,
          }}];
          while (frames.length) {{
            const frame = frames[frames.length - 1];
            const node = frame.node;
            if (!frame.entered) {{
              frame.entered = true;
              nodeCount += 1;
              if (nodeCount > maxNodes) return result();
              if (node.nodeType === Node.ELEMENT_NODE) {{
                const tag = node.nodeName || node.localName || '';
                const localName = String(node.localName || '').toLowerCase();
                frame.childMode = frame.mode;
                frame.childJsonState = frame.jsonState;
                if (frame.mode === 'normal') {{
                  if (!appendRaw('<') || !appendRaw(tag)) return result();
                  for (const attribute of node.attributes || []) {{
                    if (
                      !appendRaw(' ') || !appendRaw(attribute.name) ||
                      !appendRaw('="') || !appendEscaped(attribute.value, true) ||
                      !appendRaw('"')
                    ) return result();
                  }}
                  if (!appendRaw('>')) return result();
                  frame.closingTag = tag;
                  const type = String(
                    node.getAttribute && node.getAttribute('type') || ''
                  ).trim().toLowerCase();
                  if (localName === 'script') {{
                    frame.childMode = type.includes('ld+json') ? 'json' : 'suppress';
                    frame.childJsonState = frame.childMode === 'json'
                      ? {{ pending: '' }}
                      : null;
                  }} else if (localName === 'style') {{
                    frame.childMode = 'suppress';
                    frame.childJsonState = null;
                  }}
                }}
                if (localName === 'template' && node.content) {{
                  frame.template = node.content;
                }}
              }} else if (
                node.nodeType === Node.TEXT_NODE ||
                node.nodeType === Node.CDATA_SECTION_NODE
              ) {{
                if (
                  (frame.mode === 'normal' && !appendEscaped(node.nodeValue)) ||
                  (
                    frame.mode === 'json' &&
                    !appendJsonScript(node.nodeValue, frame.jsonState)
                  )
                ) return result();
              }}
              frame.nextChild = node.firstChild;
            }}
            if (frame.nextChild) {{
              const child = frame.nextChild;
              frame.nextChild = child.nextSibling;
              frames.push({{
                node: child,
                entered: false,
                nextChild: null,
                template: null,
                closingTag: null,
                mode: frame.childMode,
                childMode: frame.childMode,
                jsonState: frame.childJsonState,
                childJsonState: frame.childJsonState,
              }});
              continue;
            }}
            if (frame.template) {{
              const content = frame.template;
              frame.template = null;
              frames.push({{
                node: content,
                entered: false,
                nextChild: null,
                template: null,
                closingTag: null,
                mode: frame.childMode,
                childMode: frame.childMode,
                jsonState: frame.childJsonState,
                childJsonState: frame.childJsonState,
              }});
              continue;
            }}
            if (frame.mode === 'normal' && frame.childMode === 'json') {{
              if (!flushJsonState(frame.childJsonState)) return result();
            }}
            if (frame.closingTag !== null) {{
              if (
                !appendRaw('</') || !appendRaw(frame.closingTag) || !appendRaw('>')
              ) return result();
            }}
            frames.pop();
          }}
          if (!captureDocumentURL()) return result();
          flush();
          return result(chunks.join(''));
        }})()
    """


def _same_origin(url: str, validated: ValidatedURL) -> bool:
    """Compare a browser request with the exact validated scheme/host/port."""

    try:
        parts = urlsplit(url)
        if parts.username is not None or parts.password is not None or parts.hostname is None:
            return False
        scheme = parts.scheme.lower()
        if scheme not in {"http", "https"}:
            return False
        host = _normalize_hostname(parts.hostname)
        port = parts.port or (80 if scheme == "http" else 443)
    except ValueError:
        return False
    return (scheme, host, port) == (validated.scheme, validated.host, validated.port)


def _browser_target_policy_error() -> URLSafetyError:
    return URLSafetyError(
        "The browser navigation target is not present in the outbound host allowlist."
    )


async def _close_browser_resources(context: Any | None, browser: Any | None) -> None:
    """Close both renderer resources even if one close operation fails."""

    try:
        if context is not None:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await context.close()
    finally:
        if browser is not None:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await browser.close()


async def _cancel_tasks(tasks: tuple[asyncio.Task[Any], ...]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _playwright_redirects(response: Any | None) -> list[RedirectHop]:
    """Reconstruct Playwright's request redirect chain for audit metadata."""

    request = getattr(response, "request", None)
    reverse_hops: list[RedirectHop] = []
    while request is not None:
        previous = getattr(request, "redirected_from", None)
        if previous is None:
            break
        previous_response = await previous.response()
        status = getattr(previous_response, "status", None)
        if isinstance(status, int) and status in _REDIRECT_CODES:
            reverse_hops.append(
                RedirectHop.model_validate(
                    {
                        "status_code": status,
                        "from_url": previous.url,
                        "to_url": request.url,
                    }
                )
            )
        request = previous
    reverse_hops.reverse()
    return reverse_hops


class AsyncFetcher:
    """Fetch public HTML with explicit safety checks on every redirect.

    Tests can inject a trusted ``httpx.AsyncBaseTransport`` and resolver without
    replacing the fetcher's pinned, cookie-free client policy. The fetcher owns
    and closes the client and any injected transport.
    """

    def __init__(
        self,
        config: FetcherConfig | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Resolver = default_resolver,
        renderer: Renderer | None = None,
    ) -> None:
        self.config = config or FetcherConfig()
        self._resolver = resolver
        if renderer is not None:
            _require_renderer_outbound_policy(renderer, self.config.outbound_allowed_hosts)
        self._renderer = renderer
        self._operations = BoundedTaskSet(self.config.max_inflight_tasks, label="Outbound fetch")
        self._render_operations = BoundedTaskSet(
            self.config.max_render_concurrency, label="Browser render"
        )
        self._close_task: asyncio.Task[Any] | None = None
        self._closed = False
        timeout = httpx.Timeout(
            connect=self.config.connect_timeout_seconds,
            read=self.config.read_timeout_seconds,
            write=self.config.write_timeout_seconds,
            pool=self.config.pool_timeout_seconds,
        )
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=False,
            trust_env=False,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5",
                "Accept-Encoding": "identity",
            },
            # The transport origin is an IP literal. Keeping those sockets alive
            # could let a redirect to a different hostname on the same IP reuse
            # the first host's TLS session and SNI. Close every pinned request.
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=0),
            http2=False,
            transport=transport,
        )

    async def __aenter__(self) -> AsyncFetcher:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        close_task = self._close_task
        if close_task is not None:
            await wait_without_cancelling(close_task, timeout=_SHUTDOWN_GRACE_SECONDS)
            return

        self._closed = True
        self._operations.cancel_active()
        operations = self._operations.snapshot()

        async def finish_close() -> None:
            if operations:
                await asyncio.gather(*operations, return_exceptions=True)
            await self._client.aclose()

        close_task = asyncio.create_task(finish_close(), name="omniscrape-fetcher-shutdown")
        self._close_task = close_task
        retain_task(close_task, _DEFERRED_SHUTDOWN_TASKS)
        await wait_without_cancelling(close_task, timeout=_SHUTDOWN_GRACE_SECONDS)

    async def fetch(self, url: str, *, render: bool = False) -> FetchResult:
        if self._closed:
            raise FetchError("The fetcher is closed.")
        if render and self._renderer is not None:
            # Recheck at the point of use so a mutable custom renderer cannot
            # change or discard its advertised policy after construction.
            _require_renderer_outbound_policy(
                self._renderer,
                self.config.outbound_allowed_hosts,
            )
        # Apply configured policy before task admission, custom renderer
        # delegation, and—most importantly—before any DNS resolution.
        enforce_outbound_target(url, self.config.outbound_allowed_hosts)
        operation = (
            (
                self._renderer
                if self._renderer is not None
                else PlaywrightRenderer(self.config, resolver=self._resolver)
            ).fetch(url)
            if render
            else self._fetch_http(url)
        )
        try:
            registries: tuple[BoundedTaskSet, ...] = (
                self._operations,
                _GLOBAL_FETCH_TASKS,
            )
            if render:
                registries += (self._render_operations, _GLOBAL_RENDER_TASKS)
            task = create_bounded_task(
                operation,
                registries=registries,
                name="omniscrape-outbound-fetch",
            )
            return await await_hard_deadline(
                task,
                timeout=self.config.total_timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise FetchError("The outbound fetch exceeded its total time limit.") from exc

    async def _send_pinned(self, validated: ValidatedURL) -> httpx.Response:
        """Connect only to an address from the validated DNS answer set.

        The URL sent to the transport contains an IP literal, so the HTTP stack
        cannot perform a second, potentially rebound DNS lookup. The original
        authority remains in the Host header and HTTPS SNI extension.
        """

        last_error: Exception | None = None
        for address in validated.addresses:
            request = self._client.build_request(
                "GET",
                _pinned_url(validated, address),
                headers={
                    "Host": _host_header(validated),
                    "Connection": "close",
                    "Accept-Encoding": "identity",
                },
            )
            # HTTPX's cookie jar keys against the transport URL (the pinned IP),
            # not the logical Host header. Never transmit or retain those cookies,
            # which could otherwise cross between hostnames sharing an address.
            request.headers.pop("Cookie", None)
            if validated.scheme == "https":
                request.extensions["sni_hostname"] = validated.host
            try:
                response = await self._client.send(request, stream=True)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError) as exc:
                last_error = exc
                continue
            finally:
                self._client.cookies.clear()

            peer = _peer_address(response)
            if peer is not None:
                try:
                    validate_peer_address(peer)
                    connected = ipaddress.ip_address(peer.split("%", 1)[0])
                    if connected != address:
                        raise FetchError("The connected peer did not match the pinned address.")
                except Exception:
                    await await_retained_cleanup(
                        response.aclose(),
                        tasks=_DEFERRED_SHUTDOWN_TASKS,
                        name="omniscrape-rejected-response-close",
                    )
                    raise
            return response

        raise FetchError("The remote server could not be reached safely.") from last_error

    async def _fetch_http(self, url: str) -> FetchResult:
        started = time.perf_counter()
        original = (
            await validate_url_async(
                url,
                self._resolver,
                allowed_hosts=self.config.outbound_allowed_hosts,
            )
        ).url
        current = original
        redirects: list[RedirectHop] = []

        for hop in range(self.config.max_redirects + 1):
            validated = await validate_url_async(
                current,
                self._resolver,
                allowed_hosts=self.config.outbound_allowed_hosts,
            )
            response = await self._send_pinned(validated)

            try:
                if response.status_code in _REDIRECT_CODES:
                    location = response.headers.get("location")
                    if not location:
                        raise FetchError("The remote server returned an invalid redirect.")
                    if hop >= self.config.max_redirects:
                        raise FetchError("The remote server exceeded the redirect limit.")
                    candidate = urljoin(validated.url, location)
                    target = await validate_url_async(
                        candidate,
                        self._resolver,
                        allowed_hosts=self.config.outbound_allowed_hosts,
                    )
                    redirects.append(
                        RedirectHop.model_validate(
                            {
                                "status_code": response.status_code,
                                "from_url": validated.url,
                                "to_url": target.url,
                            }
                        )
                    )
                    current = target.url
                    continue

                if response.status_code < 200 or response.status_code >= 300:
                    raise FetchError(f"The remote server returned HTTP {response.status_code}.")

                content_encoding = response.headers.get("content-encoding", "identity").lower()
                encodings = {item.strip() for item in content_encoding.split(",") if item.strip()}
                if encodings - {"identity"}:
                    raise FetchError("The remote server ignored the identity encoding policy.")

                media_type = _content_type(response.headers)
                if media_type is not None and media_type not in _HTML_CONTENT_TYPES:
                    raise UnsupportedContentError(
                        "The remote resource did not return an HTML-compatible content type."
                    )

                declared = response.headers.get("content-length")
                if declared:
                    try:
                        declared_bytes = int(declared)
                    except ValueError:
                        declared_bytes = 0
                    if declared_bytes > self.config.max_response_bytes:
                        raise ResponseTooLargeError()

                body = bytearray()
                try:
                    # Content-Encoding is already restricted to identity. Iterate
                    # the owned stream directly so HTTPX cannot run an implicit,
                    # cancellation-vulnerable close before our retained finally.
                    stream = response.stream
                    if not isinstance(stream, httpx.AsyncByteStream):
                        raise FetchError("The remote response stream was not asynchronous.")
                    async for chunk in stream:
                        body.extend(chunk)
                        if len(body) > self.config.max_response_bytes:
                            raise ResponseTooLargeError()
                except httpx.DecodingError as exc:
                    raise FetchError(
                        "The remote server returned an invalid content encoding."
                    ) from exc
                except (
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.ProtocolError,
                    httpx.StreamError,
                ) as exc:
                    raise FetchError(
                        "The remote response stream ended before it could be read."
                    ) from exc

                encoding = response.encoding or "utf-8"
                try:
                    html = bytes(body).decode(encoding, errors="replace")
                except LookupError:
                    encoding = "utf-8"
                    html = bytes(body).decode(encoding, errors="replace")
                return FetchResult.model_validate(
                    {
                        "requested_url": original,
                        "final_url": validated.url,
                        "status_code": response.status_code,
                        "html": html,
                        "content_type": media_type,
                        "encoding": encoding,
                        "byte_count": len(body),
                        "redirects": redirects,
                        "elapsed_ms": (time.perf_counter() - started) * 1000,
                        "rendered": False,
                    }
                )
            finally:
                await await_retained_cleanup(
                    response.aclose(),
                    tasks=_DEFERRED_SHUTDOWN_TASKS,
                    name="omniscrape-response-close",
                )

        # The loop always returns or raises; this keeps static analyzers honest.
        raise FetchError("The remote server exceeded the redirect limit.")


class PlaywrightRenderer:
    """Optional JavaScript renderer imported only when explicitly requested."""

    def __init__(
        self,
        config: FetcherConfig | None = None,
        *,
        resolver: Resolver = default_resolver,
    ) -> None:
        self.config = config or FetcherConfig()
        self._resolver = resolver

    @property
    def outbound_allowed_hosts(self) -> tuple[str, ...] | None:
        """Advertise the exact policy enforced by browser request routing."""

        return self.config.outbound_allowed_hosts

    async def fetch(self, url: str) -> FetchResult:
        started = time.perf_counter()
        validated = await validate_url_async(
            url,
            self._resolver,
            allowed_hosts=self.config.outbound_allowed_hosts,
        )
        original = validated.url
        pinned_address = next(
            (
                address
                for address in validated.addresses
                if isinstance(address, ipaddress.IPv4Address)
            ),
            validated.addresses[0],
        )
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:  # pragma: no cover - optional dependency path
            raise FetchError(
                "Browser rendering requires the optional Playwright dependency."
            ) from exc

        manager, playwright = await _start_playwright(
            async_playwright, name="omniscrape-browser-renderer"
        )
        try:
            browser: Any | None = None
            context: Any | None = None
            budget_watchdog: asyncio.Task[Any] | None = None
            policy_watchdog: asyncio.Task[Any] | None = None
            resource_budget_exceeded: asyncio.Event | None = None
            target_policy_denied: asyncio.Event | None = None
            try:
                browser = await playwright.chromium.launch(
                    headless=True,
                    chromium_sandbox=True,
                    args=_chromium_launch_args(validated, pinned_address),
                )
                context = await browser.new_context(
                    user_agent=self.config.user_agent,
                    service_workers="block",
                    java_script_enabled=True,
                    accept_downloads=False,
                    extra_http_headers={"Accept-Encoding": "identity"},
                )
                # Install side-channel defenses on the context before creating a
                # page so every frame and any attempted popup inherits them.
                await context.add_init_script(
                    """
                        (() => {
                          const blocked = () => {
                            throw new DOMException('Blocked by renderer policy');
                          };
                          for (const name of [
                            'WebSocket', 'EventSource', 'RTCPeerConnection',
                            'webkitRTCPeerConnection', 'Worker', 'SharedWorker',
                            'WebTransport', 'open'
                          ]) {
                            try {
                              Object.defineProperty(globalThis, name, { value: blocked });
                            } catch (_) {
                              try { globalThis[name] = blocked; } catch (_) {}
                            }
                          }
                        })();
                    """
                )

                async def block_web_socket(web_socket: Any) -> None:
                    await web_socket.close(code=1008, reason="Blocked by renderer policy")

                await context.route_web_socket("**/*", block_web_socket)
                page = await context.new_page()
                cdp = await context.new_cdp_session(page)
                await cdp.send("Network.enable")
                await cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
                # Capture the stable top-frame id while its URL is still the small
                # about:blank value. A target can expand history state to a huge URL
                # after navigation, so Page.getFrameTree must not cross CDP then.
                await cdp.send("Page.enable")
                frame_tree = await cdp.send("Page.getFrameTree")
                frame_id = str(
                    (((frame_tree or {}).get("frameTree") or {}).get("frame") or {}).get("id", "")
                )
                if not frame_id:
                    raise FetchError("The rendered document frame could not be inspected.")

                budget_event = asyncio.Event()
                resource_budget_exceeded = budget_event
                redirect_limit_exceeded = asyncio.Event()
                target_policy_event = asyncio.Event()
                target_policy_denied = target_policy_event
                transferred_bytes = 0
                allowed_requests = 0
                main_document_root: Any | None = None

                guarded_context = context

                async def abort_on_budget() -> None:
                    await budget_event.wait()
                    await await_retained_cleanup(
                        guarded_context.close(),
                        tasks=_DEFERRED_SHUTDOWN_TASKS,
                        name="omniscrape-browser-budget-context-close",
                    )

                async def abort_on_policy_denial() -> None:
                    await target_policy_event.wait()
                    await await_retained_cleanup(
                        guarded_context.close(),
                        tasks=_DEFERRED_SHUTDOWN_TASKS,
                        name="omniscrape-browser-policy-context-close",
                    )

                budget_watchdog = asyncio.create_task(
                    abort_on_budget(), name="omniscrape-browser-budget-watchdog"
                )
                policy_watchdog = asyncio.create_task(
                    abort_on_policy_denial(),
                    name="omniscrape-browser-policy-watchdog",
                )

                def record_data(event: Mapping[str, Any]) -> None:
                    nonlocal transferred_bytes
                    try:
                        decoded = max(0, int(event.get("dataLength", 0)))
                        encoded = max(0, int(event.get("encodedDataLength", 0)))
                        increment = max(decoded, encoded)
                    except (TypeError, ValueError):
                        increment = 0
                    transferred_bytes += increment
                    if transferred_bytes > self.config.max_response_bytes:
                        budget_event.set()

                cdp.on("Network.dataReceived", record_data)

                async def guard_route(route: Any, request: Any) -> None:
                    nonlocal allowed_requests, main_document_root
                    # Count every observed request before parsing, DNS, or any early
                    # return so a page cannot exhaust work with blocked resources.
                    allowed_requests += 1
                    if budget_event.is_set():
                        await route.abort()
                        return
                    if allowed_requests > max(1, self.config.max_render_requests):
                        budget_event.set()
                        await route.abort()
                        return
                    try:
                        enforce_outbound_target(
                            request.url,
                            self.config.outbound_allowed_hosts,
                        )
                    except URLSafetyError:
                        # A denied main-frame document is an extraction failure,
                        # not merely a blocked optional subresource. Signal the
                        # navigation task so callers receive the stable URL policy
                        # error instead of a browser-specific transport message.
                        if request.resource_type == "document" and request.frame == page.main_frame:
                            target_policy_event.set()
                        await route.abort()
                        return
                    # Rendering is observational. Never let page JavaScript turn an
                    # extraction into a state-changing same-origin request.
                    if str(getattr(request, "method", "GET")).upper() != "GET":
                        await route.abort()
                        return
                    # Media/font downloads add little extraction value and unnecessarily
                    # expand both the attack surface and bandwidth budget.
                    if request.resource_type in {"image", "media", "font"}:
                        await route.abort()
                        return
                    # Chromium's document authority is pinned to the validated IP.
                    # Cross-origin resources fail closed instead of creating another
                    # attacker-controlled DNS boundary.
                    if not _same_origin(request.url, validated):
                        await route.abort()
                        return
                    if request.resource_type == "document":
                        # Only the extraction page's main frame is useful. Blocking
                        # popup/iframe documents keeps their traffic under the page's
                        # CDP byte accounting and removes a second browsing realm.
                        if request.frame != page.main_frame:
                            await route.abort()
                            return
                        redirect_depth = 0
                        root_request = request
                        previous = getattr(request, "redirected_from", None)
                        while previous is not None:
                            redirect_depth += 1
                            root_request = previous
                            previous = getattr(previous, "redirected_from", None)
                        if main_document_root is None:
                            main_document_root = root_request
                        elif root_request is not main_document_root:
                            await route.abort()
                            return
                        if redirect_depth > self.config.max_redirects:
                            redirect_limit_exceeded.set()
                            await route.abort()
                            return
                    await route.continue_()

                # A context-wide route also covers popups and worker-owned requests;
                # the init script separately disables network-capable worker creation.
                await context.route("**/*", guard_route)

                navigation = asyncio.create_task(
                    page.goto(
                        original,
                        wait_until="domcontentloaded",
                        timeout=self.config.render_timeout_ms,
                    ),
                    name="omniscrape-browser-navigation",
                )
                budget_wait = asyncio.create_task(budget_event.wait())
                redirect_wait = asyncio.create_task(redirect_limit_exceeded.wait())
                target_policy_wait = asyncio.create_task(target_policy_event.wait())
                try:
                    await asyncio.wait(
                        {navigation, budget_wait, redirect_wait, target_policy_wait},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if target_policy_event.is_set():
                        navigation.cancel()
                        await asyncio.gather(navigation, return_exceptions=True)
                        raise _browser_target_policy_error()
                    if redirect_limit_exceeded.is_set():
                        navigation.cancel()
                        await asyncio.gather(navigation, return_exceptions=True)
                        raise FetchError("The rendered page exceeded the redirect limit.")
                    if budget_event.is_set():
                        navigation.cancel()
                        await asyncio.gather(navigation, return_exceptions=True)
                        raise ResponseTooLargeError()
                    response = await navigation
                finally:
                    for waiter in (budget_wait, redirect_wait, target_policy_wait):
                        waiter.cancel()
                        with contextlib.suppress(asyncio.CancelledError):
                            await waiter

                redirects = await _playwright_redirects(response)
                if len(redirects) > self.config.max_redirects:
                    raise FetchError("The rendered page exceeded the redirect limit.")
                # Traverse every node type from an isolated JavaScript world and
                # return only counters. Text, comments, and attribute values count
                # toward the content budget before page.content() can materialize
                # attacker-expanded markup in the driver or Python process.
                isolated = await cdp.send(
                    "Page.createIsolatedWorld",
                    {
                        "frameId": frame_id,
                        "worldName": "omniscrape-dom-budget",
                        "grantUniveralAccess": False,
                    },
                )
                try:
                    context_id = int((isolated or {}).get("executionContextId", 0))
                except (TypeError, ValueError) as exc:
                    raise FetchError("The rendered document could not be inspected.") from exc
                if context_id < 1:
                    raise FetchError("The rendered document could not be inspected.")
                try:
                    evaluation = await cdp.send(
                        "Runtime.evaluate",
                        {
                            "expression": _dom_budget_expression(
                                self.config.max_render_nodes,
                                self.config.max_response_bytes,
                            ),
                            "contextId": context_id,
                            "returnByValue": True,
                            "awaitPromise": False,
                        },
                    )
                except Exception as exc:
                    if target_policy_event.is_set():
                        raise _browser_target_policy_error() from exc
                    if budget_event.is_set():
                        raise ResponseTooLargeError() from exc
                    raise
                if target_policy_event.is_set():
                    raise _browser_target_policy_error()
                if not isinstance(evaluation, Mapping) or evaluation.get("exceptionDetails"):
                    raise FetchError("The rendered document could not be inspected.")
                budget = (evaluation.get("result") or {}).get("value") or {}
                if not isinstance(budget, Mapping):
                    raise FetchError("The rendered document could not be inspected.")
                try:
                    node_count = int(budget.get("nodeCount", 0))
                    content_bytes = int(budget.get("contentBytes", 0))
                except (TypeError, ValueError) as exc:
                    raise FetchError("The rendered document could not be inspected.") from exc
                if (
                    bool(budget.get("exceeded"))
                    or node_count > max(1, self.config.max_render_nodes)
                    or content_bytes > max(1, self.config.max_response_bytes)
                ):
                    raise ResponseTooLargeError()
                html = budget.get("html")
                if not isinstance(html, str):
                    raise FetchError("The rendered document could not be serialized safely.")
                captured_url = budget.get("documentURL")
                if not isinstance(captured_url, str) or not _same_origin(captured_url, validated):
                    raise FetchError("The rendered page crossed an unpinned origin.")
                final_validated = await validate_url_async(
                    captured_url,
                    self._resolver,
                    allowed_hosts=self.config.outbound_allowed_hosts,
                )
                if budget_event.is_set():
                    raise ResponseTooLargeError()
                # Stop the browsing context before committing a result. CDP byte
                # events may otherwise arrive after the final budget check while
                # background traffic is still in flight.
                closing_context = context
                context = None
                await await_retained_cleanup(
                    closing_context.close(),
                    tasks=_DEFERRED_SHUTDOWN_TASKS,
                    name="omniscrape-browser-context-close",
                )
                await asyncio.sleep(0)
                if target_policy_event.is_set():
                    raise _browser_target_policy_error()
                if budget_event.is_set():
                    raise ResponseTooLargeError()
                body = html.encode("utf-8")
                if len(body) > self.config.max_response_bytes:
                    raise ResponseTooLargeError()
                status = response.status if response is not None else 200
                if status < 200 or status >= 300:
                    raise FetchError(f"The rendered page returned HTTP {status}.")
                return FetchResult.model_validate(
                    {
                        "requested_url": original,
                        "final_url": final_validated.url,
                        "status_code": status,
                        "html": html,
                        "content_type": "text/html",
                        "encoding": "utf-8",
                        "byte_count": len(body),
                        "redirects": redirects,
                        "elapsed_ms": (time.perf_counter() - started) * 1000,
                        "rendered": True,
                    }
                )
            except ResponseTooLargeError:
                raise
            except URLSafetyError:
                raise
            except FetchError as exc:
                if target_policy_denied is not None and target_policy_denied.is_set():
                    raise _browser_target_policy_error() from exc
                raise
            except Exception as exc:
                if target_policy_denied is not None and target_policy_denied.is_set():
                    raise _browser_target_policy_error() from exc
                if resource_budget_exceeded is not None and resource_budget_exceeded.is_set():
                    raise ResponseTooLargeError() from exc
                raise FetchError("The browser could not render the remote page.") from exc
            finally:
                closing_budget_watchdog, budget_watchdog = budget_watchdog, None
                closing_policy_watchdog, policy_watchdog = policy_watchdog, None
                closing_watchdogs = tuple(
                    watchdog
                    for watchdog in (closing_budget_watchdog, closing_policy_watchdog)
                    if watchdog is not None
                )
                if closing_watchdogs:
                    await await_retained_cleanup(
                        _cancel_tasks(closing_watchdogs),
                        tasks=_DEFERRED_SHUTDOWN_TASKS,
                        name="omniscrape-browser-watchdogs-stop",
                    )
                closing_context, context = context, None
                closing_browser, browser = browser, None
                await await_retained_cleanup(
                    _close_browser_resources(closing_context, closing_browser),
                    tasks=_DEFERRED_SHUTDOWN_TASKS,
                    name="omniscrape-browser-resources-close",
                )
        finally:
            await await_retained_cleanup(
                _stop_playwright(manager),
                tasks=_DEFERRED_SHUTDOWN_TASKS,
                name="omniscrape-browser-driver-stop",
            )
