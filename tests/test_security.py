"""SSRF policy tests use injected DNS and never resolve real hosts."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterable
from typing import Any

import pytest

from omniscrape.errors import BusyError, URLSafetyError
from omniscrape.security import (
    _MAX_RESOLVER_WORKERS,
    validate_peer_address,
    validate_url,
    validate_url_async,
)

PUBLIC_V4 = "93.184.216.34"
PUBLIC_V6 = "2606:4700:4700::1111"


def resolver_with(*addresses: str):
    def resolve(_host: str, _port: int) -> Iterable[Any]:
        return addresses

    return resolve


def test_public_url_is_normalized_and_fragment_is_removed() -> None:
    validated = validate_url(
        " HTTPS://Example.TEST:443/path?q=1#private-fragment ",
        resolver=resolver_with(PUBLIC_V4),
    )

    assert validated.url == "https://example.test/path?q=1"
    assert validated.host == "example.test"
    assert validated.port == 443
    assert tuple(map(str, validated.addresses)) == (PUBLIC_V4,)


def test_unicode_hostname_is_resolved_as_idna() -> None:
    observed: list[tuple[str, int]] = []

    def resolver(host: str, port: int) -> list[str]:
        observed.append((host, port))
        return [PUBLIC_V4]

    validate_url("https://例子.test/path", resolver=resolver)
    assert observed == [("xn--fsqu00a.test", 443)]


@pytest.mark.parametrize(
    "url",
    [
        "",
        "example.test/no-scheme",
        "file:///etc/passwd",
        "ftp://example.test/file",
        "https://user:password@example.test/",
        "https://localhost/",
        "https://service.localhost/",
        "https://example.test:99999/",
        "https://example.test/\nInjected: header",
    ],
)
def test_malformed_or_credentialed_urls_are_rejected(url: str) -> None:
    with pytest.raises(URLSafetyError):
        validate_url(url, resolver=resolver_with(PUBLIC_V4))


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.20.30.40/",
        "http://169.254.169.254/latest/meta-data/",
        "http://224.0.0.1/",
        "http://0.0.0.0/",
        "http://[::1]/",
        "http://[fe80::1]/",
    ],
)
def test_non_public_ip_literals_are_rejected(url: str) -> None:
    with pytest.raises(URLSafetyError):
        validate_url(url, resolver=resolver_with(PUBLIC_V4))


def test_any_unsafe_dns_answer_rejects_the_hostname() -> None:
    with pytest.raises(URLSafetyError):
        validate_url(
            "https://mixed.example.test/",
            resolver=resolver_with(PUBLIC_V4, "127.0.0.1"),
        )


def test_empty_or_malformed_dns_answers_fail_closed() -> None:
    with pytest.raises(URLSafetyError):
        validate_url("https://empty.example.test/", resolver=resolver_with())
    with pytest.raises(URLSafetyError):
        validate_url(
            "https://broken.example.test/",
            resolver=lambda _host, _port: [object()],
        )


def test_getaddrinfo_records_are_supported_and_deduplicated() -> None:
    records = [
        (2, 1, 6, "", (PUBLIC_V4, 443)),
        (2, 1, 6, "", (PUBLIC_V4, 443)),
        (10, 1, 6, "", (PUBLIC_V6, 443, 0, 0)),
    ]
    validated = validate_url("https://records.example.test/", resolver=lambda _host, _port: records)
    assert tuple(map(str, validated.addresses)) == (PUBLIC_V4, PUBLIC_V6)


def test_dns_candidate_set_and_resolver_iteration_are_bounded() -> None:
    yielded = 0

    def many_addresses(_host: str, _port: int) -> Iterable[str]:
        nonlocal yielded
        for suffix in range(1, 100):
            yielded += 1
            yield f"93.184.216.{suffix}"

    validated = validate_url("https://many.example.test/", resolver=many_addresses)
    assert len(validated.addresses) == 8
    assert yielded == 8


def test_duplicate_dns_answers_cannot_bypass_the_record_iteration_cap() -> None:
    yielded = 0

    def duplicate_addresses(_host: str, _port: int) -> Iterable[str]:
        nonlocal yielded
        while True:
            yielded += 1
            yield PUBLIC_V4

    validated = validate_url("https://duplicates.example.test/", resolver=duplicate_addresses)
    assert [str(address) for address in validated.addresses] == [PUBLIC_V4]
    assert yielded == 8


@pytest.mark.asyncio
async def test_cancelled_resolver_workers_remain_globally_bounded() -> None:
    release = threading.Event()
    started = 0
    lock = threading.Lock()

    def blocking_resolver(_host: str, _port: int) -> list[str]:
        nonlocal started
        with lock:
            started += 1
        release.wait(timeout=5)
        return [PUBLIC_V4]

    tasks = [
        asyncio.create_task(
            validate_url_async(f"https://blocked-{index}.example.test/", blocking_resolver)
        )
        for index in range(_MAX_RESOLVER_WORKERS)
    ]
    try:
        for _ in range(100):
            with lock:
                if started == _MAX_RESOLVER_WORKERS:
                    break
            await asyncio.sleep(0.005)
        assert started == _MAX_RESOLVER_WORKERS
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        with pytest.raises(BusyError, match="capacity"):
            await validate_url_async("https://one-too-many.example.test/", resolver_with(PUBLIC_V4))
    finally:
        release.set()

    for _ in range(100):
        try:
            validated = await validate_url_async(
                "https://capacity-restored.example.test/", resolver_with(PUBLIC_V4)
            )
        except BusyError as exc:
            if "capacity" not in str(exc):
                raise
            await asyncio.sleep(0.005)
        else:
            assert str(validated.addresses[0]) == PUBLIC_V4
            break
    else:
        raise AssertionError("Resolver capacity was not released after workers completed")


def test_explicit_port_zero_is_rejected_instead_of_rewritten() -> None:
    with pytest.raises(URLSafetyError, match="Port zero"):
        validate_url("https://example.test:0/path", resolver=resolver_with(PUBLIC_V4))


@pytest.mark.asyncio
async def test_async_validation_uses_the_same_policy() -> None:
    validated = await validate_url_async(
        "https://async.example.test", resolver=resolver_with(PUBLIC_V4)
    )
    assert validated.url == "https://async.example.test/"


def test_connected_peer_is_revalidated() -> None:
    validate_peer_address(PUBLIC_V4)
    with pytest.raises(URLSafetyError):
        validate_peer_address("127.0.0.1")
