"""OmniScrape: safe, typed web extraction for Python, HTTP, CLI, and MCP."""

from __future__ import annotations

__version__ = "0.2.1"

from .api import create_app
from .config import Settings
from .errors import (
    BusyError,
    ExtractionError,
    FetchError,
    OmniScrapeError,
    ProviderError,
    ProviderUnavailableError,
    RenderingDisabledError,
    ResponseTooLargeError,
    UnsupportedContentError,
    URLSafetyError,
)
from .fetcher import AsyncFetcher, FetcherConfig, FetchResult, PlaywrightRenderer
from .mcp import create_mcp_server
from .models import (
    Article,
    ContentKind,
    ExtractionMetadata,
    ExtractionMode,
    ExtractionResult,
    Product,
    ProviderResult,
    TokenUsage,
)
from .pipeline import LLMProvider, OmniScrape, extract
from .security import ValidatedURL, validate_url, validate_url_async

__all__ = [
    "Article",
    "AsyncFetcher",
    "BusyError",
    "ContentKind",
    "ExtractionError",
    "ExtractionMetadata",
    "ExtractionMode",
    "ExtractionResult",
    "FetchError",
    "FetchResult",
    "FetcherConfig",
    "LLMProvider",
    "OmniScrape",
    "OmniScrapeError",
    "PlaywrightRenderer",
    "Product",
    "ProviderError",
    "ProviderResult",
    "ProviderUnavailableError",
    "RenderingDisabledError",
    "ResponseTooLargeError",
    "Settings",
    "TokenUsage",
    "URLSafetyError",
    "UnsupportedContentError",
    "ValidatedURL",
    "__version__",
    "create_app",
    "create_mcp_server",
    "extract",
    "validate_url",
    "validate_url_async",
]
