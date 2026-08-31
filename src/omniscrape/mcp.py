"""Lazy Model Context Protocol adapter for Codex, Claude Code, and peers."""

from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from pydantic import Field, RootModel

from ._tasking import BoundedAdmission
from .config import Settings
from .errors import OmniScrapeError
from .models import (
    ContentKind,
    ErrorBody,
    ErrorResponse,
    ExtractionMode,
    ExtractionResult,
)
from .pipeline import OmniScrape

logger = logging.getLogger(__name__)


class MCPToolResult(
    RootModel[
        Annotated[
            ExtractionResult | ErrorResponse,
            Field(discriminator="success"),
        ]
    ]
):
    """Discriminated MCP output that preserves the shared top-level contract."""


def _tool_result(result: ExtractionResult | ErrorResponse) -> MCPToolResult:
    return MCPToolResult(root=result)


def create_mcp_server(
    service: OmniScrape | Any | None = None,
    *,
    settings: Settings | None = None,
) -> Any:
    """Create, but do not start, an MCP server exposing the ``extract`` tool.

    The MCP SDK remains optional and is imported only when this callable is used.
    """

    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.types import ToolAnnotations
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("MCP support is not installed; install OmniScrape's mcp extra.") from exc

    owns_service = service is None
    resolved = settings if settings is not None else Settings.from_env()
    scraper = service if service is not None else OmniScrape.from_settings(resolved)
    admission = BoundedAdmission(resolved.max_concurrency, label="MCP extraction")

    @asynccontextmanager
    async def lifespan(_: Any) -> AsyncIterator[None]:
        try:
            yield None
        finally:
            await scraper.aclose()

    server_options: dict[str, Any] = {}
    try:
        supports_lifespan = "lifespan" in inspect.signature(FastMCP).parameters
    except (TypeError, ValueError):  # pragma: no cover - unusual third-party callable
        supports_lifespan = False
    if owns_service and supports_lifespan:
        server_options["lifespan"] = lifespan
    server = FastMCP("OmniScrape", **server_options)

    @server.tool(
        annotations=ToolAnnotations(
            title="Extract authorized web content",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        )
    )
    async def extract(
        url: str,
        kind: ContentKind = ContentKind.ARTICLE,
        mode: ExtractionMode = ExtractionMode.DETERMINISTIC,
        render: bool = False,
    ) -> MCPToolResult:
        """Extract a public web page into typed article or product data.

        Args:
            url: Public HTTP(S) page. Local, private, reserved, and credentialed
                destinations are rejected.
            kind: ``article`` or ``product``.
            mode: ``deterministic`` (the default), ``auto``, or ``llm``. Auto
                uses the LLM only when local extraction falls below the
                completeness threshold.
            render: Run the optional browser renderer for JavaScript-heavy pages.
        """

        try:
            try:
                resolved_kind = ContentKind(kind)
                resolved_mode = ExtractionMode(mode)
            except ValueError:
                return _tool_result(
                    ErrorResponse(
                        error=ErrorBody(code="invalid_request", message="kind or mode is invalid.")
                    )
                )
            await admission.acquire(timeout=resolved.queue_timeout_seconds)
            try:
                result = await scraper.extract(
                    url,
                    resolved_kind,
                    resolved_mode,
                    render=render,
                )
            finally:
                admission.release()
            return _tool_result(result)
        except (ValueError, OmniScrapeError) as exc:
            if isinstance(exc, OmniScrapeError):
                code, message = exc.code, exc.public_message
            else:
                code, message = "invalid_request", "kind or mode is invalid."
            return _tool_result(ErrorResponse(error=ErrorBody(code=code, message=message)))
        except Exception as exc:
            logger.error("Unhandled OmniScrape MCP error (%s)", type(exc).__name__)
            return _tool_result(
                ErrorResponse(
                    error=ErrorBody(
                        code="internal_error",
                        message="An unexpected server error occurred.",
                    )
                )
            )

    return server


__all__ = ["MCPToolResult", "create_mcp_server"]
