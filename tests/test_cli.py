"""CLI smoke tests avoid DNS and HTTP by replacing the one-shot boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import pytest
from click.utils import strip_ansi
from typer.testing import CliRunner

from omniscrape.cli import app
from omniscrape.errors import URLSafetyError
from omniscrape.models import Article, ExtractionMetadata, ExtractionResult

runner = CliRunner()
URL = "https://news.example.test/story"


def result_fixture() -> ExtractionResult:
    return ExtractionResult(
        url=URL,
        final_url=URL,
        kind="article",
        mode="deterministic",
        data=Article(url=URL, title="Fixture title", text="Fixture body"),
        metadata=ExtractionMetadata(sources=["heuristic"], completeness_score=0.4),
    )


def test_module_entrypoint_help_smoke() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "omniscrape", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "extract" in completed.stdout
    assert "serve" in completed.stdout
    assert "mcp" in completed.stdout


def test_extract_help_documents_safe_modes() -> None:
    result = runner.invoke(app, ["extract", "--help"], color=False)
    assert result.exit_code == 0
    help_text = strip_ansi(result.stdout)
    assert "--kind" in help_text
    assert "--mode" in help_text
    assert "--render" in help_text


def test_extract_command_outputs_compact_json_without_network(monkeypatch: Any) -> None:
    calls: list[tuple[Any, ...]] = []

    async def fake_extract(*args: Any, **kwargs: Any) -> ExtractionResult:
        calls.append((*args, kwargs))
        return result_fixture()

    monkeypatch.setattr("omniscrape.cli.extract_once", fake_extract)
    result = runner.invoke(
        app,
        [
            "extract",
            URL,
            "--kind",
            "article",
            "--mode",
            "deterministic",
            "--compact",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["data"]["title"] == "Fixture title"
    assert calls[0][0] == URL


def test_extract_command_defaults_to_deterministic_mode(monkeypatch: Any) -> None:
    calls: list[tuple[Any, ...]] = []

    async def fake_extract(*args: Any, **kwargs: Any) -> ExtractionResult:
        calls.append((*args, kwargs))
        return result_fixture()

    monkeypatch.setattr("omniscrape.cli.extract_once", fake_extract)
    result = runner.invoke(app, ["extract", URL, "--compact"])

    assert result.exit_code == 0
    assert calls[0][2].value == "deterministic"


@pytest.mark.parametrize("legacy_mode", ["none", "sd"])
def test_extract_command_accepts_legacy_local_mode_aliases(
    monkeypatch: Any, legacy_mode: str
) -> None:
    calls: list[tuple[Any, ...]] = []

    async def fake_extract(*args: Any, **kwargs: Any) -> ExtractionResult:
        calls.append((*args, kwargs))
        return result_fixture()

    monkeypatch.setattr("omniscrape.cli.extract_once", fake_extract)
    result = runner.invoke(app, ["extract", URL, "--mode", legacy_mode, "--compact"])
    assert result.exit_code == 0
    assert calls[0][2].value == "deterministic"


def test_extract_command_rejects_unknown_mode_before_network(monkeypatch: Any) -> None:
    async def should_not_run(*_args: Any, **_kwargs: Any) -> ExtractionResult:
        raise AssertionError("invalid CLI mode reached extraction")

    monkeypatch.setattr("omniscrape.cli.extract_once", should_not_run)
    result = runner.invoke(app, ["extract", URL, "--mode", "surprise"])
    assert result.exit_code != 0
    assert "deterministic, auto, or llm" in result.output


def test_cli_errors_are_machine_readable_and_hide_internal_detail(monkeypatch: Any) -> None:
    async def fail(*_args: Any, **_kwargs: Any) -> ExtractionResult:
        raise URLSafetyError("internal resolver result 10.0.0.1")

    monkeypatch.setattr("omniscrape.cli.extract_once", fail)
    result = runner.invoke(app, ["extract", URL, "--mode", "deterministic"])

    assert result.exit_code == 1
    payload = json.loads(result.stderr)
    assert payload["error"]["code"] == "unsafe_url"
    assert "10.0.0.1" not in result.stderr


def test_serve_refuses_public_bind_without_authentication(monkeypatch: Any) -> None:
    monkeypatch.delenv("OMNISCRAPE_API_KEY", raising=False)
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code != 0
    assert "OMNISCRAPE_API_KEY" in result.output


def test_serve_invokes_uvicorn_for_loopback(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(application: Any, **kwargs: Any) -> None:
        calls.append({"application": application, **kwargs})

    monkeypatch.delenv("OMNISCRAPE_API_KEY", raising=False)
    monkeypatch.setattr("uvicorn.run", fake_run)
    result = runner.invoke(app, ["serve", "--host", "127.0.0.1", "--port", "8123"])
    assert result.exit_code == 0
    assert calls[0]["host"] == "127.0.0.1"
    assert calls[0]["port"] == 8123
    assert calls[0]["limit_concurrency"] == 16
    assert calls[0]["application"].title == "OmniScrape"


def test_serve_allows_authenticated_public_bind(monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setenv("OMNISCRAPE_API_KEY", "fixture-service-key")
    monkeypatch.setenv("OMNISCRAPE_ALLOWED_HOSTS", "api.example.test")
    monkeypatch.setattr("uvicorn.run", lambda application, **kwargs: calls.append(kwargs))
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code == 0
    assert calls[0]["host"] == "0.0.0.0"


def test_serve_refuses_public_bind_without_explicit_allowed_hosts(monkeypatch: Any) -> None:
    monkeypatch.setenv("OMNISCRAPE_API_KEY", "fixture-service-key")
    monkeypatch.delenv("OMNISCRAPE_ALLOWED_HOSTS", raising=False)
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code != 0
    assert "OMNISCRAPE_ALLOWED_HOSTS" in result.output


def test_mcp_command_runs_stdio_transport(monkeypatch: Any) -> None:
    class FakeServer:
        def __init__(self) -> None:
            self.transports: list[str] = []

        def run(self, *, transport: str) -> None:
            self.transports.append(transport)

    server = FakeServer()
    monkeypatch.setattr("omniscrape.mcp.create_mcp_server", lambda: server)
    result = runner.invoke(app, ["mcp"])
    assert result.exit_code == 0
    assert server.transports == ["stdio"]


def test_mcp_command_surfaces_missing_extra(monkeypatch: Any) -> None:
    def missing() -> Any:
        raise RuntimeError("install the fixture extra")

    monkeypatch.setattr("omniscrape.mcp.create_mcp_server", missing)
    result = runner.invoke(app, ["mcp"])
    assert result.exit_code != 0
    assert "install the fixture extra" in result.output
