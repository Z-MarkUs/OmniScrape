"""Deterministic extractor behavior on original fixture documents."""

from __future__ import annotations

import json
from typing import Any

from bs4.element import Tag

from omniscrape.extractors import extract_heuristic, extract_readability, extract_structured
from omniscrape.extractors import structured as structured_module
from omniscrape.extractors.common import (
    author_name,
    clean_inline,
    clean_text,
    dedupe_strings,
    image_urls,
    itemprop_content,
    public_web_url,
    soup_for,
)
from omniscrape.extractors.heuristic import _best_content_node
from omniscrape.models import ContentKind

ARTICLE_URL = "https://news.example.test/stories/solar-workshop"
PRODUCT_URL = "https://shop.example.test/products/field-notes-lamp"


def test_json_ld_article_is_extracted_deterministically(article_html: str) -> None:
    candidate = extract_structured(article_html, ARTICLE_URL, ContentKind.ARTICLE)

    assert candidate is not None
    assert candidate.source == "json-ld"
    assert candidate.values == {
        "url": ARTICLE_URL,
        "title": "Harbor Lab Opens a Solar Workshop",
        "author": "Avery Chen",
        "date_published": "2026-04-12T09:30:00+08:00",
        "text": None,
        "description": "A community lab is teaching practical solar design.",
        "images": ["https://cdn.example.test/images/solar-workshop.jpg"],
    }


def test_json_ld_product_is_extracted_deterministically(product_html: str) -> None:
    candidate = extract_structured(product_html, PRODUCT_URL, ContentKind.PRODUCT)

    assert candidate is not None
    assert candidate.source == "json-ld"
    assert candidate.values == {
        "url": PRODUCT_URL,
        "name": "Field Notes Lamp",
        "price": "49.90",
        "currency": "USD",
        "sku": "FNL-2048-BLU",
        "description": "A compact, rechargeable desk lamp for field work.",
        "images": ["https://cdn.example.test/products/lamp-blue.png"],
    }


def test_heuristic_article_keeps_content_and_drops_page_chrome(article_html: str) -> None:
    candidate = extract_heuristic(article_html, ARTICLE_URL, ContentKind.ARTICLE)

    assert candidate is not None
    assert candidate.values["title"] == "Harbor Lab Opens a Solar Workshop"
    assert candidate.values["author"] == "By Avery Chen"
    assert "safe wiring" in candidate.values["text"]
    assert "Home — Weather" not in candidate.values["text"]
    assert "Copyright" not in candidate.values["text"]


def test_readability_article_text_excludes_an_exact_leading_title() -> None:
    html = """
    <html lang="zh-Hant">
      <head><title>社區天台花園迎來蜜蜂</title></head>
      <body>
        <article>
          <h1>社區天台花園迎來蜜蜂</h1>
          <p>義工在清晨安置了三個本地蜂箱, 並記錄第一批訪客。</p>
          <p>導賞資料同時提供粵語、English 與日本語版本。</p>
        </article>
      </body>
    </html>
    """

    candidate = extract_readability(html, ARTICLE_URL, ContentKind.ARTICLE)

    assert candidate is not None
    assert candidate.values["title"] == "社區天台花園迎來蜜蜂"
    assert candidate.values["text"] == (
        "義工在清晨安置了三個本地蜂箱, 並記錄第一批訪客。\n\n"
        "導賞資料同時提供粵語、English 與日本語版本。"
    )


def test_readability_excludes_a_leading_title_with_nested_inline_markup() -> None:
    html = """
    <html>
      <head><title>Island Grid Begins Trial</title></head>
      <body>
        <article>
          <h1>Island Grid <em>Begins</em> Trial</h1>
          <p>Engineers connected a tidal generator to a neighborhood battery before sunrise.</p>
          <p>The trial will publish detailed open performance notes for local schools.</p>
        </article>
      </body>
    </html>
    """

    candidate = extract_readability(html, ARTICLE_URL, ContentKind.ARTICLE)

    assert candidate is not None
    assert candidate.values["title"] == "Island Grid Begins Trial"
    assert candidate.values["text"] == (
        "Engineers connected a tidal generator to a neighborhood battery before sunrise.\n\n"
        "The trial will publish detailed open performance notes for local schools."
    )


def test_readability_keeps_first_block_when_it_is_not_the_title() -> None:
    html = """
    <html>
      <head><title>Independent heading</title></head>
      <body>
        <article>
          <h2>Introduction</h2>
          <p>The opening paragraph is meaningful body content and must remain intact.</p>
          <p>A second paragraph keeps the document long enough for readability.</p>
        </article>
      </body>
    </html>
    """

    candidate = extract_readability(html, ARTICLE_URL, ContentKind.ARTICLE)

    assert candidate is not None
    assert candidate.values["text"].startswith("Introduction\n\nThe opening paragraph")


def test_readability_keeps_no_heading_paragraph_that_matches_document_title() -> None:
    html = """
    <html>
      <head><title>A repeated opening</title></head>
      <body>
        <article>
          <p>A repeated opening</p>
          <p>This paragraph supplies the substantive article body after the repeated phrase.</p>
          <p>A final paragraph makes the intended body selection unambiguous.</p>
        </article>
      </body>
    </html>
    """

    candidate = extract_readability(html, ARTICLE_URL, ContentKind.ARTICLE)

    assert candidate is not None
    assert candidate.values["text"].startswith("A repeated opening\n\nThis paragraph")


def test_hostile_markup_is_treated_as_inert_text(hostile_html: str) -> None:
    candidate = extract_heuristic(
        hostile_html,
        "https://safe.example.test/security",
        ContentKind.ARTICLE,
    )

    assert candidate is not None
    assert "Ordinary visible text remains extractable" in candidate.values["text"]
    assert "globalThis.fixtureScriptExecuted" not in candidate.values["text"]
    assert "globalThis.fixtureOnloadExecuted" not in candidate.values["text"]


def test_requested_article_kind_can_use_generic_metadata_fallback(
    product_html: str,
) -> None:
    candidate = extract_structured(product_html, PRODUCT_URL, ContentKind.ARTICLE)
    assert candidate is not None
    assert candidate.source == "metadata"
    assert candidate.values["title"] == "Field Notes Lamp"


def test_json_ld_graph_and_offer_list_select_matching_nodes() -> None:
    html = """
    <script type="Application/LD+JSON"><!--
    {"@context":"https://schema.org","@graph":[
      {"@type":"BreadcrumbList","name":"Ignore me"},
      {"@type":["Thing","Product"],"name":"Graph product","image":{"url":"/p.jpg"},
       "offers":[{"@type":"Offer"},{"@type":"Offer","lowPrice":"12.50",
                  "priceCurrency":"EUR"}]}
    ]};
    --></script>
    """
    candidate = extract_structured(html, "https://shop.example.test/item", ContentKind.PRODUCT)
    assert candidate is not None
    assert candidate.source == "json-ld"
    assert candidate.values["name"] == "Graph product"
    assert candidate.values["price"] == "12.50"
    assert candidate.values["currency"] == "EUR"
    assert candidate.values["images"] == ["https://shop.example.test/p.jpg"]


def test_malformed_json_ld_falls_back_to_metadata() -> None:
    html = """
    <meta property="og:title" content="Metadata title">
    <script type="application/ld+json"></script>
    <script type="application/ld+json">{not-json</script>
    """
    candidate = extract_structured(html, "https://news.example.test/item", ContentKind.ARTICLE)
    assert candidate is not None
    assert candidate.source == "metadata"
    assert candidate.values["title"] == "Metadata title"


def test_json_ld_huge_integer_falls_back_to_metadata() -> None:
    html = (
        '<meta property="og:title" content="Metadata title">'
        f'<script type="application/ld+json">{"9" * 50_000}</script>'
    )

    candidate = extract_structured(html, ARTICLE_URL, ContentKind.ARTICLE)

    assert candidate is not None
    assert candidate.source == "metadata"
    assert candidate.values["title"] == "Metadata title"


def test_json_ld_object_and_candidate_work_is_bounded(monkeypatch: Any) -> None:
    visited = 0
    original = structured_module._product_from_json

    def counted(node: dict[str, Any], url: str) -> dict[str, Any]:
        nonlocal visited
        visited += 1
        return original(node, url)

    monkeypatch.setattr(structured_module, "_product_from_json", counted)
    objects = [
        {"@type": "Product", "name": f"Product {index}"}
        for index in range(structured_module._MAX_JSON_LD_OBJECTS + 50)
    ]
    html = f'<script type="application/ld+json">{json.dumps(objects)}</script>'

    candidate = extract_structured(html, PRODUCT_URL, ContentKind.PRODUCT)

    assert candidate is not None
    assert candidate.source == "json-ld"
    assert candidate.values["name"] == "Product 0"
    assert visited == structured_module._MAX_JSON_LD_OBJECTS


def test_json_ld_total_character_budget_falls_back_without_copying_text() -> None:
    oversized = " " * (structured_module._MAX_JSON_LD_TOTAL_CHARS + 1)
    html = (
        '<meta property="og:title" content="Bounded metadata">'
        f'<script type="application/ld+json">{oversized}</script>'
    )

    candidate = extract_structured(html, PRODUCT_URL, ContentKind.PRODUCT)

    assert candidate is not None
    assert candidate.source == "metadata"
    assert candidate.values["name"] == "Bounded metadata"


def test_json_ld_node_budget_is_shared_across_scripts() -> None:
    first_values = json.dumps([None] * 3_000)
    second_values = json.dumps([None] * 2_000 + [{"@type": "Product", "name": "Too late"}])
    html = (
        '<meta property="og:title" content="Bounded metadata">'
        f'<script type="application/ld+json">{first_values}</script>'
        f'<script type="application/ld+json">{second_values}</script>'
    )

    candidate = extract_structured(html, PRODUCT_URL, ContentKind.PRODUCT)

    assert candidate is not None
    assert candidate.source == "metadata"
    assert candidate.values["name"] == "Bounded metadata"


def test_json_ld_script_count_is_bounded_per_document() -> None:
    empty_scripts = '<script type="application/ld+json">null</script>' * (
        structured_module._MAX_JSON_LD_SCRIPTS
    )
    late_product = (
        '<script type="application/ld+json">{"@type":"Product","name":"Too late"}</script>'
    )
    html = '<meta property="og:title" content="Bounded metadata">' + empty_scripts + late_product

    candidate = extract_structured(html, PRODUCT_URL, ContentKind.PRODUCT)

    assert candidate is not None
    assert candidate.source == "metadata"


def test_structured_collection_helpers_limit_untrusted_arrays() -> None:
    images = [f"https://cdn.example.test/{index}.jpg" for index in range(40)]
    authors = [f"Author {index}" for index in range(40)]
    offers = [{"price": None} for _ in range(40)] + [{"price": "999"}]

    assert len(image_urls(images, ARTICLE_URL)) == structured_module._MAX_COLLECTION_ITEMS
    normalized_authors = author_name(authors)
    assert normalized_authors is not None
    assert "Author 31" in normalized_authors
    assert "Author 32" not in normalized_authors
    assert structured_module._offer(offers).get("price") is None

    types = ["Thing"] * structured_module._MAX_COLLECTION_ITEMS + ["Product"]
    assert structured_module._types({"@type": types}) == {"thing"}
    assert structured_module._types({"@type": [{"name": "Product"}, ["Article"]]}) == set()


def test_article_microdata_is_supported() -> None:
    html = """
    <article itemscope itemtype="https://schema.org/NewsArticle">
      <meta itemprop="headline" content="Microdata headline">
      <span itemprop="author">Taylor Example</span>
      <time itemprop="datePublished" datetime="2026-08-01"></time>
      <div itemprop="articleBody"><p>Microdata body paragraph.</p></div>
      <meta itemprop="description" content="Microdata summary">
      <img itemprop="image" src="/microdata.jpg">
    </article>
    """
    candidate = extract_structured(html, "https://news.example.test/microdata", ContentKind.ARTICLE)
    assert candidate is not None
    assert candidate.source == "microdata"
    assert candidate.values["title"] == "Microdata headline"
    assert candidate.values["author"] == "Taylor Example"
    assert candidate.values["date_published"] == "2026-08-01"
    assert candidate.values["images"] == ["https://news.example.test/microdata.jpg"]


def test_product_microdata_is_supported() -> None:
    html = """
    <main itemscope itemtype="https://schema.org/Product">
      <span itemprop="name">Microdata product</span>
      <meta itemprop="price" content="88.00">
      <meta itemprop="priceCurrency" content="HKD">
      <span itemprop="mpn">MD-88</span>
      <div itemprop="description">Microdata product summary</div>
      <a itemprop="image" href="/product.jpg">image</a>
    </main>
    """
    candidate = extract_structured(html, "https://shop.example.test/microdata", ContentKind.PRODUCT)
    assert candidate is not None
    assert candidate.source == "microdata"
    assert candidate.values["name"] == "Microdata product"
    assert candidate.values["price"] == "88.00"
    assert candidate.values["currency"] == "HKD"
    assert candidate.values["sku"] == "MD-88"


def test_empty_structured_page_returns_no_candidate() -> None:
    assert (
        extract_structured(
            "<html><body></body></html>",
            "https://safe.example.test/empty",
            ContentKind.PRODUCT,
        )
        is None
    )


def test_extractor_normalization_helpers_cover_edge_shapes() -> None:
    assert clean_inline(None) is None
    assert clean_inline({"not": "scalar"}) is None
    assert clean_text(123) == "123"
    assert clean_text("<p>One</p><p>Two</p>") == "One\n\nTwo"
    assert dedupe_strings([" One ", "one", "", "Two"]) == ["One", "Two"]
    assert public_web_url(None, ARTICLE_URL) is None
    assert public_web_url("file:///etc/passwd", ARTICLE_URL) is None
    assert public_web_url("https://user:pass@example.test", ARTICLE_URL) is None
    assert public_web_url("http://[broken", ARTICLE_URL) is None
    assert image_urls(
        [
            {"contentUrl": "/image.jpg"},
            {"@id": "https://cdn.example.test/two.jpg"},
            None,
        ],
        ARTICLE_URL,
    ) == [
        "https://news.example.test/image.jpg",
        "https://cdn.example.test/two.jpg",
    ]
    assert author_name([{"alternateName": "A. Example"}, "B. Example"]) == (
        "A. Example, B. Example"
    )
    assert itemprop_content(None, "name") is None
    assert itemprop_content(soup_for("<span itemprop='name'> Fixture </span>"), "name") == (
        "Fixture"
    )


def test_heuristics_handle_sparse_and_nested_documents() -> None:
    sparse = extract_heuristic(
        "<html><body><div>tiny body</div></body></html>",
        "https://safe.example.test/sparse",
        ContentKind.ARTICLE,
    )
    assert sparse is not None
    assert sparse.values["text"] == "tiny body"

    nested = extract_heuristic(
        """
        <div><p>This paragraph is deliberately long enough to be selected as content.</p></div>
        <div><p>Short</p><a>very long navigation link that lowers this block score</a></div>
        """,
        "https://safe.example.test/nested",
        ContentKind.ARTICLE,
    )
    assert nested is not None
    assert "deliberately long enough" in nested.values["text"]

    assert (
        extract_heuristic(
            "<html><body></body></html>",
            "https://safe.example.test/empty",
            ContentKind.PRODUCT,
        )
        is None
    )


def test_nested_content_scoring_never_rescans_descendants(monkeypatch: Any) -> None:
    html = "<div>" * 2_000 + ("<p>" + "content " * 20 + "</p>") + "</div>" * 2_000
    soup = soup_for(html)
    get_text_calls = 0
    original_get_text = Tag.get_text

    def counted_get_text(self: Tag, *args: Any, **kwargs: Any) -> str:
        nonlocal get_text_calls
        get_text_calls += 1
        return original_get_text(self, *args, **kwargs)

    monkeypatch.setattr(Tag, "get_text", counted_get_text)
    selected = _best_content_node(soup)

    assert selected is not None
    assert get_text_calls == 0
