"""Small normalization helpers shared by deterministic extractors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import islice
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from ..models import ContentKind

_SPACE_RE = re.compile(r"[\t\r\f\v ]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_MAX_COLLECTION_ITEMS = 32


@dataclass(frozen=True, slots=True)
class ExtractionCandidate:
    kind: ContentKind
    source: str
    values: dict[str, Any]


def soup_for(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean_inline(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list, tuple)):
        return None
    text = _SPACE_RE.sub(" ", str(value)).strip()
    return text or None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    soup = BeautifulSoup(value, "html.parser") if "<" in value and ">" in value else None
    text = soup.get_text("\n", strip=True) if soup is not None else value
    lines = [_SPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    text = "\n\n".join(line for line in lines if line)
    text = _BLANK_LINES_RE.sub("\n\n", text).strip()
    return text or None


def first(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "" and value != []:
            return value
    return None


def dedupe_strings(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        marker = normalized.casefold()
        if normalized and marker not in seen:
            seen.add(marker)
            output.append(normalized)
    return output


def public_web_url(value: Any, base_url: str) -> str | None:
    raw = clean_inline(value)
    if not raw:
        return None
    try:
        absolute = urljoin(base_url, raw)
        parts = urlsplit(absolute)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return None
        if parts.username is not None or parts.password is not None or "@" in parts.netloc:
            return None
        return urlunsplit((parts.scheme.lower(), parts.netloc, parts.path or "/", parts.query, ""))
    except ValueError:
        return None


def image_urls(value: Any, base_url: str) -> list[str]:
    raw_values: list[Any]
    if isinstance(value, list):
        raw_values = value
    elif value is None:
        raw_values = []
    else:
        raw_values = [value]

    urls: list[str] = []
    for item in islice(raw_values, _MAX_COLLECTION_ITEMS):
        if isinstance(item, dict):
            item = first(item.get("url"), item.get("contentUrl"), item.get("@id"))
        url = public_web_url(item, base_url)
        if url:
            urls.append(url)
    return dedupe_strings(urls)


def meta_values(soup: BeautifulSoup) -> dict[str, str]:
    values: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        key = tag.get("property") or tag.get("name") or tag.get("itemprop")
        content = tag.get("content")
        if key and content:
            values.setdefault(str(key).strip().lower(), str(content).strip())
    return values


def author_name(value: Any) -> str | None:
    values = value if isinstance(value, list) else [value]
    names: list[str] = []
    for item in islice(values, _MAX_COLLECTION_ITEMS):
        if isinstance(item, dict):
            item = first(item.get("name"), item.get("alternateName"))
        name = clean_inline(item)
        if name:
            names.append(name)
    names = dedupe_strings(names)
    return ", ".join(names) if names else None


def itemprop_content(node: Any, name: str) -> str | None:
    found = node.select_one(f'[itemprop="{name}"]') if node is not None else None
    if found is None:
        return None
    return clean_inline(
        found.get("content") or found.get("datetime") or found.get_text(" ", strip=True)
    )
