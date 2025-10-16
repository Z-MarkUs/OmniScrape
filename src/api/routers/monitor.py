from fastapi import APIRouter, Request
from pydantic import BaseModel, HttpUrl
from typing import Literal
from datetime import datetime

from bs4 import BeautifulSoup

from src.core.bypass import fetch_with_bypass

router = APIRouter(tags=["extraction"])


class MonitorRequest(BaseModel):
    url: HttpUrl
    mode: Literal["sd", "llm", "auto"] = "auto"


@router.post("/monitor")
async def monitor_articles(req: MonitorRequest, request: Request):
    try:
        if await request.is_disconnected():
            return {"error": "Client disconnected"}

        # SD-first: use bypass to fetch, parse minimal structured data and common patterns
        if req.mode == "sd":
            html = await fetch_with_bypass(str(req.url))
            if not html:
                return {
                    "success": True,
                    "url": str(req.url),
                    "mode": req.mode,
                    "article_count": 0,
                    "articles": [],
                    "monitored_at": datetime.now().isoformat(),
                    "extraction_method": "structured_data",
                }

            soup = BeautifulSoup(html, "lxml")
            articles = []

            # JSON-LD discovery
            for tag in soup.select("script[type='application/ld+json']"):
                try:
                    import json as _json
                    data = _json.loads(tag.get_text() or "{}")
                    seq = data if isinstance(data, list) else [data]
                    for item in seq:
                        t = item.get("@type")
                        if isinstance(t, list):
                            t = next((x for x in t if isinstance(x, str)), None)
                        if t in ("Article", "NewsArticle", "BlogPosting"):
                            articles.append({
                                "title": item.get("headline") or item.get("name"),
                                "url": item.get("url", ""),
                                "published_date": item.get("datePublished", ""),
                                "author": (item.get("author") or {}).get("name", "") if isinstance(item.get("author"), dict) else str(item.get("author", "")),
                            })
                except Exception:
                    continue

            # Common link patterns as fallback
            if not articles:
                for a in soup.select("a[href]")[:50]:
                    txt = (a.get_text() or "").strip()
                    href = a.get("href") or ""
                    if not txt or len(txt) < 10 or len(txt) > 200:
                        continue
                    low = href.lower()
                    if any(p in low for p in ("article", "post", "news", "story", "detail", "p/")):
                        if not href.startswith("http"):
                            from urllib.parse import urljoin
                            href = urljoin(str(req.url), href)
                        articles.append({
                            "title": txt,
                            "url": href,
                            "published_date": "",
                            "author": "",
                        })

            return {
                "success": True,
                "url": str(req.url),
                "mode": req.mode,
                "article_count": len(articles),
                "articles": articles[:10],
                "monitored_at": datetime.now().isoformat(),
                "extraction_method": "structured_data",
            }

        # LLM/AUTO delegate to crawler if available
        if req.mode in ("llm", "auto"):
            try:
                from src.crawlers.article_crawler import crawl_article_list
                result = crawl_article_list(str(req.url), count=100, mode=req.mode)
                articles = result.get("articles", [])
                return {
                    "success": True,
                    "url": str(req.url),
                    "mode": req.mode,
                    "article_count": len(articles),
                    "articles": articles[:10],
                    "monitored_at": datetime.now().isoformat(),
                    "extraction_method": "real_extraction",
                    "token_usage": result.get("token_usage", {}),
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "url": str(req.url),
                    "mode": req.mode,
                }

        return {"success": False, "error": "Unsupported mode", "mode": req.mode}
    except Exception as e:
        return {"success": False, "error": str(e)}


