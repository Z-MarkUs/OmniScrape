"""Real-Chromium regressions for browser network controls."""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
from collections.abc import Callable
from typing import Any

import pytest

from omniscrape.errors import ResponseTooLargeError
from omniscrape.extractors import extract_structured
from omniscrape.extractors.common import soup_for
from omniscrape.fetcher import (
    FetcherConfig,
    PlaywrightRenderer,
    _chromium_launch_args,
    _dom_budget_expression,
)
from omniscrape.models import ContentKind
from omniscrape.security import ValidatedURL


async def _http_server(
    responder: Callable[[str], bytes],
) -> tuple[asyncio.Server, int, list[str]]:
    hits: list[str] = []

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=2)
            first_line = request.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
            path = first_line.split(" ", 2)[1]
            hits.append(path)
            body = responder(path)
            writer.write(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html; charset=utf-8\r\n"
                + f"Content-Length: {len(body)}\r\n".encode()
                + b"Connection: close\r\n\r\n"
                + body
            )
            await writer.drain()
        except (asyncio.IncompleteReadError, asyncio.TimeoutError, IndexError):
            pass
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    socket = server.sockets[0]
    return server, int(socket.getsockname()[1]), hits


async def _launch_page(async_playwright: Any, *, url: str, args: list[str]) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True, args=args)
        try:
            context = await browser.new_context(service_workers="block", accept_downloads=False)
            try:
                await context.route_web_socket("**/*", lambda route: route.close(code=1008))
                page = await context.new_page()
                response = await page.goto(url, wait_until="domcontentloaded", timeout=10_000)
                assert response is not None and response.status == 200
                await page.wait_for_timeout(750)
            finally:
                await context.close()
        finally:
            await browser.close()


@pytest.mark.browser
@pytest.mark.asyncio
async def test_minimum_browser_contract_supports_required_context_guards() -> None:
    async_api = pytest.importorskip("playwright.async_api")
    server, port, hits = await _http_server(lambda _: b"<h1>minimum browser contract</h1>")
    validated = ValidatedURL(
        url=f"http://allowed.localhost:{port}/",
        scheme="http",
        host="allowed.localhost",
        port=port,
        addresses=(ipaddress.ip_address("127.0.0.1"),),
    )
    try:
        await _launch_page(
            async_api.async_playwright,
            url=validated.url,
            args=_chromium_launch_args(validated, validated.addresses[0]),
        )
    finally:
        server.close()
        await server.wait_closed()
    assert hits == ["/"]


@pytest.mark.browser
@pytest.mark.asyncio
async def test_dom_budget_descends_into_serialized_template_content() -> None:
    async_api = pytest.importorskip("playwright.async_api")
    async with async_api.async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True)
        try:
            page = await browser.new_page()
            await page.set_content("<template id='payload'></template>")
            await page.evaluate(
                "document.querySelector('#payload').content.textContent = 'x'.repeat(17)"
            )
            budget = await page.evaluate(_dom_budget_expression(100, 16))
        finally:
            await browser.close()

    assert budget["exceeded"] is True
    assert budget["contentBytes"] > 16


@pytest.mark.browser
@pytest.mark.asyncio
async def test_controlled_dom_serializer_is_bounded_and_preserves_json_ld() -> None:
    async_api = pytest.importorskip("playwright.async_api")
    async with async_api.async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True)
        try:
            page = await browser.new_page()
            for script_type, wrapped in (
                ("application/ld+json", False),
                ("Application/LD+JSON; charset=utf-8", False),
                ("application/ld+json", True),
            ):
                await page.set_content(f'<script id="payload" type="{script_type}"></script>')
                raw = (
                    '{"@type":"Product","name":"Rendered Lamp",'
                    '"description":"safe </script marker"}'
                )
                if wrapped:
                    raw = f"<!--{raw}-->"
                await page.evaluate(
                    "([id, value]) => { document.querySelector(id).textContent = value; }",
                    ["#payload", raw],
                )
                budget = await page.evaluate(_dom_budget_expression(1_000, 100_000))
                assert budget["exceeded"] is False
                assert budget["contentBytes"] == len(budget["html"].encode("utf-8"))
                candidate = extract_structured(
                    budget["html"],
                    "https://render.example.test/product",
                    ContentKind.PRODUCT,
                )
                assert candidate is not None
                assert candidate.values["name"] == "Rendered Lamp"

            await page.set_content('<script id="payload" type="application/ld+json"></script>')
            await page.evaluate(
                "() => { const root = document.querySelector('#payload'); "
                'root.append(document.createTextNode(\'{"@type":"Product",\' + '
                '\'"name":"Split Marker","description":"</scr\')); '
                "root.append(document.createTextNode('ipt> remains data\"}')); }"
            )
            split_budget = await page.evaluate(_dom_budget_expression(1_000, 100_000))
            split_candidate = extract_structured(
                split_budget["html"],
                "https://render.example.test/product",
                ContentKind.PRODUCT,
            )
            assert split_candidate is not None
            assert split_candidate.values["name"] == "Split Marker"
            split_script = soup_for(split_budget["html"]).find("script")
            assert split_script is not None and split_script.string is not None
            split_data = json.loads(str(split_script.string))
            assert split_data["description"] == "</script> remains data"

            for tag in ("script", "style"):
                await page.set_content(f"<{tag} id='payload'></{tag}>")
                baseline = await page.evaluate(_dom_budget_expression(1_000, 100_000))
                await page.evaluate(
                    "([id, count]) => { const root = document.querySelector(id); "
                    "for (let i = 0; i < count; i++) root.append(document.createTextNode('')); }",
                    ["#payload", 20],
                )
                capped = await page.evaluate(
                    _dom_budget_expression(baseline["nodeCount"] + 5, 100_000)
                )
                assert capped["exceeded"] is True
                assert "html" not in capped

            await page.set_content("<body></body>")
            await page.evaluate(
                "() => { const node = document.createElementNS('urn:test', "
                "'longprefix:item'); node.setAttributeNS('urn:attr', "
                "'attrprefix:value', '<>&\\u00a0'); document.body.append(node); }"
            )
            namespaced = await page.evaluate(_dom_budget_expression(1_000, 100_000))
            assert namespaced["exceeded"] is False
            assert namespaced["contentBytes"] == len(namespaced["html"].encode("utf-8"))
            assert "longprefix:item" in namespaced["html"]

            await page.set_content("<body></body>")
            await page.evaluate(
                "value => { document.body.textContent = value; }",
                '\0\\"\u00a0\u2028\u2029漢🙂' * 10,
            )
            wire = await page.evaluate(_dom_budget_expression(1_000, 100_000))
            assert wire["wireBytes"] > wire["contentBytes"]
            wire_capped = await page.evaluate(_dom_budget_expression(1_000, wire["contentBytes"]))
            assert wire_capped["exceeded"] is True
            assert "html" not in wire_capped
        finally:
            await browser.close()


@pytest.mark.browser
@pytest.mark.asyncio
async def test_full_renderer_caps_history_expanded_document_url(monkeypatch: Any) -> None:
    pytest.importorskip("playwright.async_api")
    body = b"""
        <!doctype html><h1>small document</h1>
        <script>history.replaceState(null, '', '/' + 'x'.repeat(1000000));</script>
    """
    server, port, hits = await _http_server(lambda _: body)
    original = f"http://allowed.localhost:{port}/"
    validated = ValidatedURL(
        url=original,
        scheme="http",
        host="allowed.localhost",
        port=port,
        addresses=(ipaddress.ip_address("127.0.0.1"),),
    )

    async def trusted_validation(
        _url: str,
        _resolver: Any,
        *,
        allowed_hosts: tuple[str, ...] | None = None,
    ) -> ValidatedURL:
        assert allowed_hosts is None
        return validated

    monkeypatch.setattr("omniscrape.fetcher.validate_url_async", trusted_validation)
    try:
        with pytest.raises(ResponseTooLargeError):
            await PlaywrightRenderer(
                FetcherConfig(max_response_bytes=512, render_timeout_ms=10_000)
            ).fetch(original)
    finally:
        server.close()
        await server.wait_closed()

    assert hits == ["/"]


@pytest.mark.browser
@pytest.mark.asyncio
async def test_chromium_policy_blocks_speculation_rules_route_bypass() -> None:
    async_api = pytest.importorskip("playwright.async_api")
    blocked_server, blocked_port, blocked_hits = await _http_server(lambda _: b"blocked")

    def main_response(_: str) -> bytes:
        return f"""
            <!doctype html>
            <script type="speculationrules">
              {{"prefetch":[{{"source":"list","urls":[
                "http://127.0.0.1:{blocked_port}/spec"
              ],"eagerness":"immediate"}}]}}
            </script>
            <h1>speculation fixture</h1>
        """.encode()

    main_server, main_port, main_hits = await _http_server(main_response)
    validated = ValidatedURL(
        url=f"http://allowed.localhost:{main_port}/",
        scheme="http",
        host="allowed.localhost",
        port=main_port,
        addresses=(ipaddress.ip_address("127.0.0.1"),),
    )
    production_args = _chromium_launch_args(validated, validated.addresses[0])
    control_args = [
        arg
        for arg in production_args
        if not arg.startswith(
            ("--enable-features=", "--disable-features=", "--disable-blink-features=")
        )
    ]
    control_args = [
        (
            f"--host-resolver-rules=MAP {validated.host} 127.0.0.1"
            if arg.startswith("--host-resolver-rules=")
            else arg
        )
        for arg in control_args
    ]

    try:
        # Prove the installed Chromium exercises the vulnerable path; otherwise a
        # passing block assertion would not be a meaningful regression.
        await _launch_page(
            async_api.async_playwright,
            url=validated.url,
            args=control_args,
        )
        assert blocked_hits == ["/spec"]

        blocked_hits.clear()
        main_hits.clear()
        await _launch_page(
            async_api.async_playwright,
            url=validated.url,
            args=production_args,
        )
        assert main_hits == ["/"]
        assert blocked_hits == []
    finally:
        main_server.close()
        blocked_server.close()
        await main_server.wait_closed()
        await blocked_server.wait_closed()
