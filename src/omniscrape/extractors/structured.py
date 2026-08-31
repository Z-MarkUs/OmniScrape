"""Schema.org JSON-LD, microdata, and metadata extraction."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from itertools import islice
from typing import Any

from ..models import ContentKind
from .common import (
    ExtractionCandidate,
    author_name,
    clean_inline,
    clean_text,
    first,
    image_urls,
    itemprop_content,
    meta_values,
    public_web_url,
    soup_for,
)

_ARTICLE_TYPES = {
    "article",
    "newsarticle",
    "blogposting",
    "techarticle",
    "report",
    "scholarlyarticle",
    "analysisnewsarticle",
}

# JSON-LD is untrusted input. These limits keep a compact HTML document from
# expanding into an unbounded number of Python objects and candidates.
_MAX_JSON_LD_SCRIPTS = 64
_MAX_JSON_LD_TOTAL_CHARS = 256 * 1024
_MAX_JSON_LD_OBJECTS = 512
_MAX_JSON_LD_NODE_VISITS = 4_096
_MAX_JSON_LD_NESTING = 64
_MAX_COLLECTION_ITEMS = 32


@dataclass(slots=True)
class _JsonWalkBudget:
    remaining_objects: int
    remaining_nodes: int


def _json_objects(value: Any, *, budget: _JsonWalkBudget) -> Iterator[dict[str, Any]]:
    """Yield a bounded prefix of root/``@graph`` objects without recursion."""

    stack: list[tuple[Iterator[Any], int]] = [(iter((value,)), 0)]
    while stack and budget.remaining_objects > 0 and budget.remaining_nodes > 0:
        iterator, depth = stack[-1]
        try:
            current = next(iterator)
        except StopIteration:
            stack.pop()
            continue
        budget.remaining_nodes -= 1
        if isinstance(current, dict):
            budget.remaining_objects -= 1
            yield current
            graph = current.get("@graph")
            if graph is not None and depth < _MAX_JSON_LD_NESTING:
                stack.append((iter((graph,)), depth + 1))
        elif isinstance(current, list) and depth < _MAX_JSON_LD_NESTING:
            stack.append((iter(current), depth + 1))


def _types(value: dict[str, Any]) -> set[str]:
    raw = value.get("@type") or value.get("type") or []
    items: Iterator[Any]
    if isinstance(raw, str):
        items = iter((raw,))
    elif isinstance(raw, list):
        items = islice(raw, _MAX_COLLECTION_ITEMS)
    else:
        return set()
    return {item.rsplit("/", 1)[-1].lower() for item in items if isinstance(item, str) and item}


def _parse_json_ld(raw: str) -> Any | None:
    cleaned = raw.strip().removeprefix("<!--").removesuffix("-->").strip().rstrip(";")
    if not cleaned:
        return None
    try:
        return json.loads(cleaned)
    except (RecursionError, TypeError, ValueError):
        return None


def _is_json_ld_type(value: str | None) -> bool:
    return bool(value and "ld+json" in value.lower())


def _offer(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        candidates = islice(value, _MAX_COLLECTION_ITEMS)
        fallback: dict[str, Any] | None = None
        for candidate in candidates:
            if fallback is None and isinstance(candidate, dict):
                fallback = candidate
            if isinstance(candidate, dict) and first(
                candidate.get("price"), candidate.get("lowPrice")
            ):
                return candidate
        return fallback or {}
    return value if isinstance(value, dict) else {}


def _article_from_json(node: dict[str, Any], url: str) -> dict[str, Any]:
    return {
        "url": url,
        "title": clean_inline(first(node.get("headline"), node.get("name"))),
        "author": author_name(node.get("author")),
        "date_published": clean_inline(
            first(node.get("datePublished"), node.get("dateCreated"), node.get("uploadDate"))
        ),
        "text": clean_text(first(node.get("articleBody"), node.get("text"))),
        "description": clean_text(node.get("description")),
        "images": image_urls(first(node.get("image"), node.get("thumbnailUrl")), url),
    }


def _product_from_json(node: dict[str, Any], url: str) -> dict[str, Any]:
    offer = _offer(node.get("offers"))
    return {
        "url": url,
        "name": clean_inline(node.get("name")),
        "price": clean_inline(first(offer.get("price"), offer.get("lowPrice"), node.get("price"))),
        "currency": clean_inline(first(offer.get("priceCurrency"), node.get("priceCurrency"))),
        "sku": clean_inline(first(node.get("sku"), node.get("mpn"), node.get("productID"))),
        "description": clean_text(node.get("description")),
        "images": image_urls(first(node.get("image"), node.get("thumbnailUrl")), url),
    }


def _signal_count(values: dict[str, Any]) -> tuple[int, int]:
    present = sum(bool(value) for key, value in values.items() if key not in {"url", "images"})
    return present, len(values.get("images") or [])


def _microdata(soup: Any, url: str, kind: ContentKind) -> dict[str, Any] | None:
    needle = "Product" if kind is ContentKind.PRODUCT else "Article"
    nodes = soup.select(f'[itemtype*="{needle}" i]')
    if not nodes:
        return None
    node = nodes[0]
    image_node = node.select_one('[itemprop="image"]')
    raw_image = None
    if image_node is not None:
        raw_image = image_node.get("content") or image_node.get("src") or image_node.get("href")
    if kind is ContentKind.ARTICLE:
        return {
            "url": url,
            "title": first(itemprop_content(node, "headline"), itemprop_content(node, "name")),
            "author": itemprop_content(node, "author"),
            "date_published": first(
                itemprop_content(node, "datePublished"), itemprop_content(node, "dateCreated")
            ),
            "text": clean_text(
                first(itemprop_content(node, "articleBody"), itemprop_content(node, "text"))
            ),
            "description": clean_text(itemprop_content(node, "description")),
            "images": image_urls(raw_image, url),
        }
    return {
        "url": url,
        "name": itemprop_content(node, "name"),
        "price": first(itemprop_content(node, "price"), itemprop_content(node, "lowPrice")),
        "currency": itemprop_content(node, "priceCurrency"),
        "sku": first(itemprop_content(node, "sku"), itemprop_content(node, "mpn")),
        "description": clean_text(itemprop_content(node, "description")),
        "images": image_urls(raw_image, url),
    }


def _metadata(soup: Any, url: str, kind: ContentKind) -> dict[str, Any]:
    meta = meta_values(soup)
    images = image_urls(
        first(meta.get("og:image"), meta.get("twitter:image"), meta.get("twitter:image:src")),
        url,
    )
    canonical_node = soup.select_one('link[rel="canonical"]')
    canonical = public_web_url(canonical_node.get("href"), url) if canonical_node else None
    output_url = canonical or url
    if kind is ContentKind.ARTICLE:
        return {
            "url": output_url,
            "title": clean_inline(
                first(meta.get("og:title"), meta.get("twitter:title"), meta.get("title"))
            ),
            "author": clean_inline(first(meta.get("author"), meta.get("article:author"))),
            "date_published": clean_inline(
                first(
                    meta.get("article:published_time"), meta.get("date"), meta.get("datepublished")
                )
            ),
            "text": None,
            "description": clean_text(
                first(
                    meta.get("og:description"),
                    meta.get("description"),
                    meta.get("twitter:description"),
                )
            ),
            "images": images,
        }
    return {
        "url": output_url,
        "name": clean_inline(first(meta.get("og:title"), meta.get("twitter:title"))),
        "price": clean_inline(
            first(
                meta.get("product:price:amount"),
                meta.get("og:price:amount"),
                meta.get("product:price"),
            )
        ),
        "currency": clean_inline(
            first(meta.get("product:price:currency"), meta.get("og:price:currency"))
        ),
        "sku": clean_inline(first(meta.get("product:retailer_item_id"), meta.get("sku"))),
        "description": clean_text(
            first(
                meta.get("og:description"), meta.get("description"), meta.get("twitter:description")
            )
        ),
        "images": images,
    }


def extract_structured(html: str, url: str, kind: ContentKind) -> ExtractionCandidate | None:
    soup = soup_for(html)
    best: tuple[str, dict[str, Any]] | None = None
    best_signal = (-1, -1)

    def consider(source: str, values: dict[str, Any]) -> None:
        nonlocal best, best_signal
        signal = _signal_count(values)
        if signal > best_signal:
            best = source, values
            best_signal = signal

    remaining_chars = _MAX_JSON_LD_TOTAL_CHARS
    walk_budget = _JsonWalkBudget(
        remaining_objects=_MAX_JSON_LD_OBJECTS,
        remaining_nodes=_MAX_JSON_LD_NODE_VISITS,
    )
    scripts = soup.find_all(
        "script",
        attrs={"type": _is_json_ld_type},
        limit=_MAX_JSON_LD_SCRIPTS,
    )
    for script in scripts:
        raw_node = script.string
        if raw_node is None:
            continue
        raw_length = len(raw_node)
        if raw_length > remaining_chars:
            break
        remaining_chars -= raw_length
        parsed = _parse_json_ld(str(raw_node))
        if parsed is None:
            continue
        for node in _json_objects(parsed, budget=walk_budget):
            node_types = _types(node)
            if kind is ContentKind.ARTICLE and node_types & _ARTICLE_TYPES:
                consider("json-ld", _article_from_json(node, url))
            elif kind is ContentKind.PRODUCT and "product" in node_types:
                consider("json-ld", _product_from_json(node, url))
        if walk_budget.remaining_objects == 0 or walk_budget.remaining_nodes == 0:
            break

    microdata = _microdata(soup, url, kind)
    if microdata:
        consider("microdata", microdata)
    metadata = _metadata(soup, url, kind)
    consider("metadata", metadata)

    if best is None or best_signal == (0, 0):
        return None
    source, values = best
    return ExtractionCandidate(kind=kind, source=source, values=values)
