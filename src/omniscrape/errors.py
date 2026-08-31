"""Public exception hierarchy for OmniScrape.

Exceptions carry stable error codes and intentionally bland public messages so the
API can be useful without reflecting network internals or credentials to clients.
"""

from __future__ import annotations


class OmniScrapeError(Exception):
    """Base class for expected, safely reportable OmniScrape failures."""

    code = "omniscrape_error"
    public_message = "The extraction could not be completed."
    status_code = 400

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.public_message)
        self.detail = detail


class URLSafetyError(OmniScrapeError):
    """Raised when an outbound URL does not satisfy the network safety policy."""

    code = "unsafe_url"
    public_message = "The URL is not permitted by the outbound network policy."
    status_code = 400


class FetchError(OmniScrapeError):
    """Raised when a remote document cannot be fetched safely."""

    code = "fetch_failed"
    public_message = "The remote page could not be fetched."
    status_code = 502


class ResponseTooLargeError(FetchError):
    """Raised before or while a response exceeds the configured byte limit."""

    code = "response_too_large"
    public_message = "The remote page exceeds the configured size limit."
    status_code = 413


class UnsupportedContentError(FetchError):
    """Raised for responses that are not plausibly HTML or text."""

    code = "unsupported_content"
    public_message = "The remote resource is not a supported HTML document."
    status_code = 415


class ExtractionError(OmniScrapeError):
    """Raised when content was fetched but no useful result could be produced."""

    code = "extraction_failed"
    public_message = "No useful structured content could be extracted."
    status_code = 422


class RenderingDisabledError(OmniScrapeError):
    """Raised when the HTTP API renderer policy rejects a render request."""

    code = "rendering_disabled"
    public_message = "Browser rendering is disabled for this API."
    status_code = 403


class ProviderUnavailableError(OmniScrapeError):
    """Raised when LLM mode is requested without an available provider."""

    code = "provider_unavailable"
    public_message = "LLM extraction is not configured on this service."
    status_code = 503


class ProviderError(OmniScrapeError):
    """Raised for a provider failure without exposing provider response details."""

    code = "provider_failed"
    public_message = "The configured extraction provider failed."
    status_code = 502


class BusyError(OmniScrapeError):
    """Raised when the bounded API work queue cannot accept a request in time."""

    code = "service_busy"
    public_message = "The service is busy; try again shortly."
    status_code = 503
