"""Typer command-line interface for local use and service operation."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated

import typer

from . import __version__
from .config import Settings
from .errors import OmniScrapeError
from .models import ContentKind, ExtractionMode, jsonable
from .pipeline import extract as extract_once

app = typer.Typer(
    name="omniscrape",
    help="Safe, typed article and product extraction.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the installed OmniScrape version and exit.",
        ),
    ] = False,
) -> None:
    """Safe, typed article and product extraction."""


def _fail(exc: OmniScrapeError) -> None:
    typer.echo(
        json.dumps(
            {"success": False, "error": {"code": exc.code, "message": exc.public_message}},
            separators=(",", ":"),
        ),
        err=True,
    )
    raise typer.Exit(code=1)


@app.command("extract")
def extract_command(
    url: Annotated[str, typer.Argument(help="Public HTTP(S) page URL.")],
    kind: Annotated[
        ContentKind, typer.Option("--kind", "-k", help="Typed output schema.")
    ] = ContentKind.ARTICLE,
    mode: Annotated[
        str,
        typer.Option(
            "--mode",
            "-m",
            metavar="MODE",
            help=(
                "Extraction mode: deterministic, auto, or llm. "
                "Legacy none/sd/local aliases are accepted."
            ),
        ),
    ] = ExtractionMode.DETERMINISTIC.value,
    render: Annotated[
        bool,
        typer.Option("--render", help="Use the optional JavaScript renderer."),
    ] = False,
    pretty: Annotated[
        bool, typer.Option("--pretty/--compact", help="JSON output formatting.")
    ] = True,
) -> None:
    """Extract one page and write the typed JSON result to stdout."""

    try:
        resolved_mode = ExtractionMode(mode.strip().lower())
    except ValueError as exc:
        raise typer.BadParameter(
            "Choose deterministic, auto, or llm (legacy: none, sd, local).",
            param_hint="--mode",
        ) from exc
    try:
        result = asyncio.run(extract_once(url, kind, resolved_mode, render=render))
    except OmniScrapeError as exc:
        _fail(exc)
        return
    typer.echo(
        json.dumps(
            jsonable(result),
            ensure_ascii=False,
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        )
    )


@app.command("serve")
def serve_command(
    host: Annotated[
        str, typer.Option("--host", help="Bind host. Defaults to loopback.")
    ] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535, help="Bind port.")] = 8000,
) -> None:
    """Run the API and bundled showcase UI."""

    settings = Settings.from_env()
    if host not in {"127.0.0.1", "localhost", "::1"} and not settings.api_key:
        raise typer.BadParameter(
            "Set OMNISCRAPE_API_KEY before binding to a non-loopback host.",
            param_hint="--host",
        )
    if host not in {"127.0.0.1", "localhost", "::1"} and settings.allowed_hosts is None:
        raise typer.BadParameter(
            "Set OMNISCRAPE_ALLOWED_HOSTS to the expected public Host authorities.",
            param_hint="--host",
        )
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - packaging failure
        raise typer.BadParameter("The server dependencies are not installed.") from exc
    from .api import create_app

    uvicorn.run(
        create_app(settings),
        host=host,
        port=port,
        log_level="info",
        limit_concurrency=max(16, settings.max_concurrency + 8),
    )


@app.command("mcp")
def mcp_command() -> None:
    """Run the optional MCP server over stdio."""

    from .mcp import create_mcp_server

    try:
        server = create_mcp_server()
    except RuntimeError as exc:
        raise typer.BadParameter(str(exc)) from exc
    server.run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    app()
