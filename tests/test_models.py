"""Public schema contracts shared by the API, CLI, and adapters."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from omniscrape.models import (
    Article,
    ContentKind,
    ExtractionMetadata,
    ExtractionMode,
    ExtractionResult,
    Product,
    TokenUsage,
    jsonable,
)


def test_legacy_local_modes_normalize_to_deterministic() -> None:
    for legacy in ("none", "sd", "local"):
        assert ExtractionMode(legacy) is ExtractionMode.DETERMINISTIC


def test_article_normalizes_whitespace_and_empty_values() -> None:
    article = Article(
        url="https://news.example.test/story",
        title="  A   useful   title  ",
        author="   ",
        text="  first line\n\nsecond line  ",
    )

    assert article.kind is ContentKind.ARTICLE
    assert article.title == "A useful title"
    assert article.author is None
    assert article.text == "first line\n\nsecond line"


def test_models_forbid_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Product(
            url="https://shop.example.test/item",
            name="Fixture",
            invented_field="must not silently pass",  # type: ignore[call-arg]
        )


def test_token_usage_is_non_negative_and_immutable() -> None:
    usage = TokenUsage(input_tokens=12, output_tokens=4, total_tokens=16)
    with pytest.raises(ValidationError):
        usage.input_tokens = 99
    with pytest.raises(ValidationError):
        TokenUsage(input_tokens=-1, output_tokens=0, total_tokens=0)


def test_extraction_result_round_trips_as_json_data() -> None:
    fetched_at = datetime(2026, 4, 12, 1, 30, tzinfo=timezone.utc)
    data = Article(
        url="https://news.example.test/story",
        title="Harbor Lab Opens a Solar Workshop",
        images=["https://cdn.example.test/story.jpg"],
    )
    result = ExtractionResult(
        url="https://news.example.test/story",
        final_url="https://news.example.test/story",
        kind="article",
        mode="deterministic",
        data=data,
        metadata=ExtractionMetadata(
            sources=["json_ld"],
            fetched_at=fetched_at,
            http_status=200,
            content_bytes=1234,
            completeness_score=0.8,
        ),
    )

    payload = jsonable(result)
    assert payload["success"] is True
    assert payload["kind"] == "article"
    assert payload["mode"] == "deterministic"
    assert payload["data"]["kind"] == "article"
    assert payload["metadata"]["fetched_at"] == "2026-04-12T01:30:00Z"


def test_discriminated_data_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(
            {
                "url": "https://example.test/",
                "final_url": "https://example.test/",
                "kind": "article",
                "mode": "deterministic",
                "data": {"kind": "video", "url": "https://example.test/"},
                "metadata": {},
            }
        )


def test_metadata_rejects_impossible_completeness() -> None:
    with pytest.raises(ValidationError):
        ExtractionMetadata(completeness_score=1.01)
