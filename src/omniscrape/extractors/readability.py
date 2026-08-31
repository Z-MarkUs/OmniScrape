"""Article extraction backed by Mozilla Readability's Python port."""

from __future__ import annotations

import unicodedata

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

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


def _comparison_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _is_first_text_element(soup: BeautifulSoup, element: Tag) -> bool:
    """Return whether ``element`` precedes every meaningful text node."""

    for descendant in soup.descendants:
        if descendant is element:
            return True
        if (
            isinstance(descendant, NavigableString)
            and not isinstance(descendant, Comment)
            and descendant.strip()
        ):
            return False
    return False


def _without_leading_title(soup: BeautifulSoup, title: str | None) -> str | None:
    """Drop a qualifying first heading from Readability's parsed article body."""

    text = clean_text(str(soup))
    if not text:
        return None
    heading = soup.select_one("h1, h2, h3, h4, h5, h6")
    heading_text = clean_inline(heading.get_text(" ", strip=True)) if heading else None
    if (
        heading is None
        or not heading_text
        or not _is_first_text_element(soup, heading)
        or (
            heading.name != "h1"
            and (title is None or _comparison_key(heading_text) != _comparison_key(title))
        )
    ):
        return text
    heading.extract()
    return clean_text(str(soup)) or text


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
        summary_soup = soup_for(summary)
        title = clean_inline(document.short_title())
        raw_images = [node.get("src") for node in summary_soup.find_all("img") if node.get("src")]
        text = _without_leading_title(summary_soup, title)
    except Exception:
        return None
    if not text:
        return None
    soup = soup_for(html)
    meta = meta_values(soup)
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
