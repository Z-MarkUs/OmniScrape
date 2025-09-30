from typing import Literal, Dict, Any
from .fetcher import fetch_rendered
from .extract_structured import extract_structured
from .extract_readable import readable_article
from .extract_patterns import find_prices
from .extract_scrapegraph import scrapegraph_article, scrapegraph_product
from .schemas import Article, Product
from bs4 import BeautifulSoup

def _first(*vals): 
    return next((v for v in vals if v), None)

async def extract(url: str, kind: Literal["article","product"]) -> Dict[str, Any]:
    # 1) Render
    html = await fetch_rendered(url)

    # 2) Structured data
    sd = extract_structured(html, base_url=url)
    if kind == "article":
        article = Article(url=url)
        # naive mapping from JSON-LD if available
        for item in sd["ld"]:
            t = item.get("@type") or item.get("type")
            if isinstance(t, list): t = next((x for x in t if isinstance(x, str)), None)
            if t in ("NewsArticle","Article","BlogPosting"):
                article.title = _first(article.title, item.get("headline"), item.get("name"))
                article.author = _first(article.author, (item.get("author") or {}).get("name") if isinstance(item.get("author"), dict) else None)
                article.date_published = _first(article.date_published, item.get("datePublished"))
                if item.get("articleBody"): article.text = _first(article.text, item["articleBody"])
        if article.title and article.text:
            return article.model_dump()

        # 3) Readability fallback
        r = readable_article(html)
        if r.get("title") and r.get("text"):
            article.title = _first(article.title, r["title"])
            article.text  = _first(article.text,  r["text"])

        # 4) ScrapeGraph fallback (LLM)
        if not article.text:
            sg = scrapegraph_article(url)
            article.title = _first(article.title, sg.get("title"))
            article.author = _first(article.author, sg.get("author"))
            article.date_published = _first(article.date_published, sg.get("date_published") or sg.get("date"))
            article.text = _first(article.text, sg.get("text") or sg.get("content"))
            imgs = sg.get("images") or []
            if isinstance(imgs, list): article.images = imgs

        return article.model_dump()

    if kind == "product":
        product = Product(url=url)
        # JSON-LD mapping
        for item in sd["ld"]:
            t = item.get("@type") or item.get("type")
            if isinstance(t, list): t = next((x for x in t if isinstance(x, str)), None)
            if t in ("Product",):
                product.name = _first(product.name, item.get("name"))
                offers = item.get("offers") or {}
                if isinstance(offers, dict):
                    product.price = _first(product.price, offers.get("price"))
                    product.currency = _first(product.currency, offers.get("priceCurrency"))
                product.description = _first(product.description, item.get("description"))
        if product.name and product.price:
            return product.model_dump()

        # Heuristic: parse visible text for prices
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(" ", strip=True)
        prices = find_prices(text)
        if prices and not product.price:
            product.price = prices[0]

        # ScrapeGraph fallback
        sg = scrapegraph_product(url)
        product.name = _first(product.name, sg.get("name") or sg.get("title"))
        product.price = _first(product.price, sg.get("price"))
        product.currency = _first(product.currency, sg.get("currency"))
        product.description = _first(product.description, sg.get("description"))
        imgs = sg.get("images") or []
        if isinstance(imgs, list): product.images = imgs

        return product.model_dump()

    raise ValueError("Unknown kind")
