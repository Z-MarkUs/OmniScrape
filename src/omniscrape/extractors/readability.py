"""Article extraction backed by Mozilla Readability's Python port."""

from __future__ import annotations

from ..models import ContentKind
from .common import (
    ExtractionCandidate,
    clean_inline,
    clean_text,
    first,
    image_urls,
    meta_values,
    soup_for,
)


def extract_readability(html: str, url: str, kind: ContentKind) -> ExtractionCandidate | None:
    if kind is not ContentKind.ARTICLE:
        return None
    try:
        from readability import Document  # type: ignore[import-untyped]
    except ImportError:  # pragma: no cover - packaging optionality
        return None
    try:
        document = Document(html)
        summary = document.summary(html_partial=True)
        text = clean_text(summary)
        title = clean_inline(document.short_title())
    except Exception:
        return None
    if not text:
        return None
    soup = soup_for(html)
    meta = meta_values(soup)
    summary_soup = soup_for(summary)
    raw_images = [node.get("src") for node in summary_soup.find_all("img") if node.get("src")]
    return ExtractionCandidate(
        kind=kind,
        source="readability",
        values={
            "url": url,
            "title": first(title, meta.get("og:title")),
            "author": clean_inline(first(meta.get("author"), meta.get("article:author"))),
            "date_published": clean_inline(
                first(meta.get("article:published_time"), meta.get("date"))
            ),
            "text": text,
            "description": clean_text(first(meta.get("description"), meta.get("og:description"))),
            "images": image_urls(raw_images, url),
        },
    )
