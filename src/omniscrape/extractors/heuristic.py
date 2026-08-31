"""Portable DOM heuristics for pages without machine-readable metadata."""

from __future__ import annotations

import re
from typing import Any

from bs4.element import NavigableString, Tag

from ..models import ContentKind
from .common import (
    ExtractionCandidate,
    clean_inline,
    clean_text,
    first,
    image_urls,
    itemprop_content,
    meta_values,
    soup_for,
)

_PRICE_RE = re.compile(
    r"(?:(?P<currency>USD|EUR|GBP|HKD|CNY|RMB|JPY|CAD|AUD|[$€£¥]))\s*"
    r"(?P<amount>\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)",
    re.IGNORECASE,
)
_SKU_RE = re.compile(r"\b(?:SKU|MPN|Item\s*(?:No\.?|#))\s*[:#-]?\s*([A-Z0-9][A-Z0-9._-]{2,})", re.I)


def _body_text(node: Any) -> str | None:
    if node is None:
        return None
    clone = soup_for(str(node))
    for unwanted in clone.select(
        "script,style,noscript,template,svg,nav,footer,header,aside,form,[aria-hidden='true']"
    ):
        unwanted.decompose()
    paragraphs: list[str] = []
    for item in clone.select("p"):
        paragraph = clean_text(item.get_text(" ", strip=True))
        if paragraph and len(paragraph) >= 35:
            paragraphs.append(paragraph)
    if paragraphs:
        return "\n\n".join(paragraphs)
    return clean_text(clone.get_text("\n", strip=True))


def _best_content_node(soup: Any) -> Any:
    preferred = soup.select_one("article") or soup.select_one("main")
    if preferred is not None:
        return preferred
    candidates = soup.select("section,div")
    if not candidates:
        return soup.body

    # Score every candidate in one bottom-up pass. Calling ``find_all`` for each
    # nested container repeatedly scans the same descendants and is quadratic on
    # attacker-controlled markup.
    # Values are paragraph characters, link characters, paragraph count, and
    # normalized subtree text characters.
    metrics: dict[int, tuple[int, int, int, int]] = {}
    for node in reversed(list(soup.descendants)):
        if isinstance(node, NavigableString):
            metrics[id(node)] = (0, 0, 0, len(" ".join(str(node).split())))
            continue
        if not isinstance(node, Tag):
            continue
        paragraph_text = 0
        link_text = 0
        paragraph_count = 0
        text_parts: list[int] = []
        for child in node.children:
            child_metrics = metrics.get(id(child))
            if child_metrics is None:
                continue
            child_paragraphs, child_links, child_count, child_text = child_metrics
            paragraph_text += child_paragraphs
            link_text += child_links
            paragraph_count += child_count
            if child_text:
                text_parts.append(child_text)
        text_length = sum(text_parts) + max(0, len(text_parts) - 1)
        if node.name == "p":
            paragraph_text += text_length
            paragraph_count += 1
        elif node.name == "a":
            link_text += text_length
        metrics[id(node)] = (paragraph_text, link_text, paragraph_count, text_length)

    def score(node: Any) -> tuple[int, int]:
        paragraph_text, link_text, paragraph_count, _ = metrics.get(id(node), (0, 0, 0, 0))
        return paragraph_text - link_text, paragraph_count

    return max(candidates, key=score)


def _article(html: str, url: str) -> ExtractionCandidate | None:
    soup = soup_for(html)
    meta = meta_values(soup)
    heading = soup.select_one("h1")
    title_node = soup.select_one("title")
    content = _best_content_node(soup)
    text = _body_text(content)
    images = []
    if content is not None:
        images = [
            img.get("src") or img.get("data-src")
            for img in content.find_all("img")
            if img.get("src") or img.get("data-src")
        ]
    time_node = soup.select_one("time[datetime]")
    byline = soup.select_one('[rel="author"], .byline, .author, [class*="author" i]')
    values = {
        "url": url,
        "title": clean_inline(
            first(
                heading.get_text(" ", strip=True) if heading else None,
                meta.get("og:title"),
                title_node.get_text(" ", strip=True) if title_node else None,
            )
        ),
        "author": clean_inline(
            first(
                meta.get("author"),
                byline.get_text(" ", strip=True) if byline else None,
            )
        ),
        "date_published": clean_inline(
            first(
                meta.get("article:published_time"),
                time_node.get("datetime") if time_node else None,
            )
        ),
        "text": text,
        "description": clean_text(first(meta.get("description"), meta.get("og:description"))),
        "images": image_urls(images, url),
    }
    if not values["title"] and not values["text"]:
        return None
    return ExtractionCandidate(ContentKind.ARTICLE, "heuristic", values)


def _product(html: str, url: str) -> ExtractionCandidate | None:
    soup = soup_for(html)
    meta = meta_values(soup)
    heading = soup.select_one("h1")
    page_text = soup.get_text(" ", strip=True)
    price_node = soup.select_one(
        '[itemprop="price"], [class*="price" i], [id*="price" i], [data-price]'
    )
    raw_price = first(
        meta.get("product:price:amount"),
        meta.get("og:price:amount"),
        itemprop_content(soup, "price"),
        price_node.get("content") if price_node else None,
        price_node.get("data-price") if price_node else None,
        price_node.get_text(" ", strip=True) if price_node else None,
    )
    price_match = _PRICE_RE.search(str(raw_price or "")) or _PRICE_RE.search(page_text[:20_000])
    price = clean_inline(price_match.group("amount")) if price_match else clean_inline(raw_price)
    currency = clean_inline(
        first(
            meta.get("product:price:currency"),
            meta.get("og:price:currency"),
            itemprop_content(soup, "priceCurrency"),
            price_match.group("currency") if price_match else None,
        )
    )
    sku_match = _SKU_RE.search(page_text[:30_000])
    sku_node = soup.select_one('[itemprop="sku"], [data-sku]')
    image_nodes = soup.select(
        '[itemprop="image"], main img, [class*="product" i] img, [id*="product" i] img'
    )
    raw_images = [
        node.get("content") or node.get("src") or node.get("data-src") for node in image_nodes
    ]
    description_node = soup.select_one(
        '[itemprop="description"], [class*="description" i], #description'
    )
    values = {
        "url": url,
        "name": clean_inline(
            first(
                heading.get_text(" ", strip=True) if heading else None,
                meta.get("og:title"),
                itemprop_content(soup, "name"),
            )
        ),
        "price": price,
        "currency": currency,
        "sku": clean_inline(
            first(
                itemprop_content(soup, "sku"),
                sku_node.get("data-sku") if sku_node else None,
                sku_node.get_text(" ", strip=True) if sku_node else None,
                sku_match.group(1) if sku_match else None,
            )
        ),
        "description": clean_text(
            first(
                meta.get("description"),
                meta.get("og:description"),
                description_node.get_text(" ", strip=True) if description_node else None,
            )
        ),
        "images": image_urls(raw_images, url),
    }
    if not values["name"] and not values["price"]:
        return None
    return ExtractionCandidate(ContentKind.PRODUCT, "heuristic", values)


def extract_heuristic(html: str, url: str, kind: ContentKind) -> ExtractionCandidate | None:
    return _article(html, url) if kind is ContentKind.ARTICLE else _product(html, url)
