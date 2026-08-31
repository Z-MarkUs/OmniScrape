"""Outbound URL validation designed to make SSRF unsafe by default."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import islice
from typing import Any, TypeAlias
from urllib.parse import SplitResult, urlsplit, urlunsplit

from .errors import BusyError, URLSafetyError

Resolver: TypeAlias = Callable[[str, int], Iterable[Any]]
_MAX_RESOLVED_ADDRESSES = 8
_MAX_RESOLVER_WORKERS = 8
_RESOLVER_EXECUTOR = ThreadPoolExecutor(
    max_workers=_MAX_RESOLVER_WORKERS,
    thread_name_prefix="omniscrape-resolver",
)
_RESOLVER_SLOTS = threading.BoundedSemaphore(_MAX_RESOLVER_WORKERS)


@dataclass(frozen=True, slots=True)
class ValidatedURL:
    """A normalized URL and all public addresses observed during validation."""

    url: str
    scheme: str
    host: str
    port: int
    addresses: tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]


def default_resolver(host: str, port: int) -> Iterable[Any]:
    """Resolve a hostname using stream-socket semantics."""

    return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)


def _safe_address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError as exc:
        raise URLSafetyError("The hostname resolved to an invalid address.") from exc

    # Be explicit rather than relying only on `is_global`, whose treatment of
    # registry special-use ranges has changed across Python releases.
    if (
        not address.is_global
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    ):
        raise URLSafetyError("The hostname resolves to a non-public address.")
    return address


def validate_peer_address(value: str) -> None:
    """Validate a connected peer to reduce DNS-rebinding exposure."""

    _safe_address(value)


def _addresses_from_resolution(
    records: Iterable[Any],
) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for record in islice(records, _MAX_RESOLVED_ADDRESSES):
        raw: Any = record
        if isinstance(record, tuple) and len(record) >= 5:
            sockaddr = record[4]
            raw = sockaddr[0] if isinstance(sockaddr, tuple) and sockaddr else sockaddr
        elif isinstance(record, tuple) and record:
            raw = record[0]
        if isinstance(raw, (ipaddress.IPv4Address, ipaddress.IPv6Address)):
            address = _safe_address(str(raw))
        elif isinstance(raw, str):
            address = _safe_address(raw)
        else:
            raise URLSafetyError("The hostname resolver returned an invalid address.")
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise URLSafetyError("The hostname did not resolve to an address.")
    return tuple(addresses)


def _normalize_parts(parts: SplitResult, host: str, port: int) -> str:
    default_port = 80 if parts.scheme.lower() == "http" else 443
    display_host = f"[{host}]" if ":" in host else host
    netloc = display_host if port == default_port else f"{display_host}:{port}"
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))


def validate_url(url: str, resolver: Resolver = default_resolver) -> ValidatedURL:
    """Normalize and validate a public HTTP(S) URL.

    ``resolver`` receives ``(host, port)`` and may return either normal
    ``socket.getaddrinfo`` records or a simple iterable of address strings, which
    makes the security policy straightforward to unit test.
    """

    if not isinstance(url, str) or not url.strip():
        raise URLSafetyError("A non-empty URL is required.")
    if any(char in url for char in ("\r", "\n", "\x00")):
        raise URLSafetyError("Control characters are not permitted in URLs.")

    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError as exc:
        raise URLSafetyError("The URL is malformed.") from exc

    scheme = parts.scheme.lower()
    if scheme not in {"http", "https"}:
        raise URLSafetyError("Only HTTP and HTTPS URLs are permitted.")
    if not parts.netloc or parts.hostname is None:
        raise URLSafetyError("The URL must include a hostname.")
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise URLSafetyError("Credentials are not permitted in outbound URLs.")

    raw_host = parts.hostname.rstrip(".")
    if not raw_host or "%" in raw_host:
        raise URLSafetyError("The hostname is malformed.")
    try:
        host = raw_host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise URLSafetyError("The hostname is malformed.") from exc
    if host == "localhost" or host.endswith(".localhost"):
        raise URLSafetyError("Local hostnames are not permitted.")

    effective_port = port if port is not None else (80 if scheme == "http" else 443)
    if effective_port == 0:
        raise URLSafetyError("Port zero is not permitted in outbound URLs.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            records = resolver(host, effective_port)
            addresses = _addresses_from_resolution(records)
        except URLSafetyError:
            raise
        except (OSError, socket.gaierror) as exc:
            raise URLSafetyError("The hostname could not be resolved safely.") from exc
        except Exception as exc:
            raise URLSafetyError("The hostname resolver failed.") from exc
    else:
        addresses = (_safe_address(str(literal)),)

    normalized = _normalize_parts(parts, host, effective_port)
    return ValidatedURL(normalized, scheme, host, effective_port, addresses)


async def validate_url_async(url: str, resolver: Resolver = default_resolver) -> ValidatedURL:
    """Run URL validation in a process-wide bounded resolver worker pool."""

    if not _RESOLVER_SLOTS.acquire(blocking=False):
        raise BusyError("Hostname resolution capacity is temporarily unavailable.")

    def run() -> ValidatedURL:
        try:
            return validate_url(url, resolver)
        finally:
            _RESOLVER_SLOTS.release()

    loop = asyncio.get_running_loop()
    try:
        future = loop.run_in_executor(_RESOLVER_EXECUTOR, run)
    except Exception:
        _RESOLVER_SLOTS.release()
        raise

    # A caller deadline may cancel its await, but the worker and its capacity slot
    # remain owned until the resolver actually returns. Consume a late exception
    # so an abandoned future never creates an event-loop warning.
    def consume_exception(done: asyncio.Future[ValidatedURL]) -> None:
        if not done.cancelled():
            done.exception()

    future.add_done_callback(consume_exception)
    return await asyncio.shield(future)
