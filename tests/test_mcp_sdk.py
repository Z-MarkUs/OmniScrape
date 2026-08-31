"""Compatibility smoke against the real optional MCP SDK."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("mcp.server.fastmcp", reason="requires the optional MCP SDK")

from omniscrape.config import Settings
from omniscrape.mcp import create_mcp_server
from omniscrape.models import (
    Article,
    ExtractionMetadata,
    ExtractionResult,
)

URL = "https://news.example.test/story"


class StubService:
    async def extract(self, *args: Any, **kwargs: Any) -> ExtractionResult:
        return ExtractionResult(
            url=URL,
            final_url=URL,
            kind="article",
            mode="deterministic",
            data=Article(url=URL, title="Fixture title"),
            metadata=ExtractionMetadata(sources=["heuristic"], completeness_score=0.2),
        )


@pytest.mark.asyncio
@pytest.mark.filterwarnings(
    "ignore:Field 'lifespan' has an incomplete definition:"
    "pydantic_settings.exceptions.IncompleteFieldDefinitionWarning"
)
async def test_minimum_supported_mcp_sdk_preserves_the_public_contract() -> None:
    server = create_mcp_server(StubService(), settings=Settings())

    tools = await server.list_tools()
    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "extract"
    assert tool.inputSchema["$defs"]["ContentKind"]["enum"] == ["article", "product"]
    assert tool.inputSchema["$defs"]["ExtractionMode"]["enum"] == [
        "deterministic",
        "llm",
        "auto",
    ]
    assert tool.outputSchema is not None
    assert tool.outputSchema["discriminator"]["propertyName"] == "success"
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.idempotentHint is True
    assert tool.annotations.openWorldHint is True

    content, structured = await server.call_tool(
        "extract",
        {
            "url": URL,
            "kind": "article",
            "mode": "deterministic",
            "render": False,
        },
    )

    assert structured["success"] is True
    assert structured["data"]["title"] == "Fixture title"
    assert content
    assert '"success": true' in content[0].text
