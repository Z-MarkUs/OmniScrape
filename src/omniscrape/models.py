"""Typed public models shared by the library, API, CLI, and MCP adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    """Return a timezone-aware timestamp (kept injectable in higher layers)."""

    return datetime.now(timezone.utc)


class ContentKind(str, Enum):
    ARTICLE = "article"
    PRODUCT = "product"


class ExtractionMode(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    AUTO = "auto"

    @classmethod
    def _missing_(cls, value: object) -> ExtractionMode | None:
        # `none` was the original API's spelling for local-only extraction.
        if isinstance(value, str) and value.strip().lower() in {"none", "sd", "local"}:
            return cls.DETERMINISTIC
        return None


class Article(BaseModel):
    """Normalized article fields. Missing source data remains ``None``."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[ContentKind.ARTICLE] = ContentKind.ARTICLE
    url: AnyHttpUrl
    title: str | None = None
    author: str | None = None
    date_published: str | None = Field(default=None, description="ISO-8601 preferred")
    text: str | None = None
    description: str | None = None
    images: list[AnyHttpUrl] = Field(default_factory=list)

    @field_validator("title", "author", "date_published", "text", "description")
    @classmethod
    def empty_strings_are_missing(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split()) if value and "\n" not in value else value.strip()
        return cleaned or None


class Product(BaseModel):
    """Normalized product fields while preserving the source's raw price string."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal[ContentKind.PRODUCT] = ContentKind.PRODUCT
    url: AnyHttpUrl
    name: str | None = None
    price: str | None = None
    currency: str | None = None
    sku: str | None = None
    description: str | None = None
    images: list[AnyHttpUrl] = Field(default_factory=list)

    @field_validator("name", "price", "currency", "sku", "description")
    @classmethod
    def empty_strings_are_missing(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


ExtractedData = Annotated[Article | Product, Field(discriminator="kind")]


class TokenUsage(BaseModel):
    """Provider-reported usage only; OmniScrape never estimates these values."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def total_matches_components(self) -> TokenUsage:
        if self.total_tokens != self.input_tokens + self.output_tokens:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        return self


class ExtractionMetadata(BaseModel):
    """Auditable execution details derived from real work, never simulation."""

    model_config = ConfigDict(extra="forbid")

    sources: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=utc_now)
    http_status: int | None = None
    content_bytes: int = Field(default=0, ge=0)
    redirect_count: int = Field(default=0, ge=0)
    rendered: bool = False
    fetch_ms: float | None = Field(default=None, ge=0)
    extraction_ms: float | None = Field(default=None, ge=0)
    total_ms: float | None = Field(default=None, ge=0)
    completeness_score: float = Field(default=0.0, ge=0.0, le=1.0)
    provider: str | None = None
    model: str | None = None
    token_usage: TokenUsage | None = None
    warnings: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    """Successful extraction result used by every public interface."""

    model_config = ConfigDict(extra="forbid")

    success: Literal[True] = True
    url: AnyHttpUrl = Field(description="Original requested URL")
    final_url: AnyHttpUrl
    kind: ContentKind
    mode: ExtractionMode
    data: ExtractedData
    metadata: ExtractionMetadata

    @model_validator(mode="after")
    def kind_matches_payload(self) -> ExtractionResult:
        if self.kind is not self.data.kind:
            raise ValueError("result kind must match data kind")
        return self


class ProviderResult(BaseModel):
    """Validated boundary between an optional LLM provider and the pipeline."""

    model_config = ConfigDict(extra="forbid")

    data: ExtractedData
    provider: str
    model: str
    token_usage: TokenUsage | None = None
    raw_response_id: str | None = Field(default=None, exclude=True)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    deterministic: Literal[True] = True
    llm_configured: bool
    llm_available: bool
    renderer_enabled: bool = Field(description="Whether HTTP API rendering is enabled by policy")
    renderer_available: bool = Field(
        description="Effective renderer readiness; always false when API rendering is disabled"
    )


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorBody


def jsonable(model: BaseModel) -> dict[str, Any]:
    """Serialize a Pydantic model consistently across optional integrations."""

    return model.model_dump(mode="json", exclude_none=True)
