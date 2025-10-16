from fastapi import APIRouter, Request
from pydantic import BaseModel, HttpUrl
from typing import Literal
from datetime import datetime
import asyncio
import os

from bs4 import BeautifulSoup

from src.core.bypass import fetch_with_bypass
import requests
from urllib.parse import urljoin

router = APIRouter(tags=["extraction"])


def _robust_fetch_with_timeout(url: str) -> str:
    """
    Robust fetch with multiple fallback strategies and strict timeouts
    Enhanced version with ETNet-specific strategies from old scrapers
    """
    import time
    import os
    
    # Strategy 1: Try requests with mobile headers (fastest)
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://www.google.com/',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200 and len(response.text) > 1000:
            print(f"✅ Mobile requests strategy succeeded: {len(response.text)} chars")
            return response.text
    except Exception as e:
        print(f"Mobile requests strategy failed: {e}")
    
    # Strategy 2: Try requests with desktop headers
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://www.google.com/',
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200 and len(response.text) > 1000:
            print(f"✅ Desktop requests strategy succeeded: {len(response.text)} chars")
            return response.text
    except Exception as e:
        print(f"Desktop requests strategy failed: {e}")
    
    # Strategy 3: ETNet-specific mobile requests (from old scrapers)
    if 'etnetchina.cn' in url:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Referer': 'https://www.etnetchina.cn/',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
            }
            
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code == 200 and len(response.text) > 1000:
                print(f"✅ ETNet mobile strategy succeeded: {len(response.text)} chars")
                return response.text
        except Exception as e:
            print(f"ETNet mobile strategy failed: {e}")
    
    # Strategy 4: Try Jina Reader proxy (from old scrapers)
    try:
        proxy_url = f"https://r.jina.ai/{url}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(proxy_url, headers=headers, timeout=20)
        if response.status_code == 200 and len(response.text) > 1000:
            print(f"✅ Jina Reader proxy succeeded: {len(response.text)} chars")
            return response.text
    except Exception as e:
        print(f"Jina Reader proxy failed: {e}")
    
    # Strategy 5: Try bypass with Playwright (last resort, with longer timeout)
    try:
        import asyncio
        # Set longer timeout for Playwright RPA/human simulation
        os.environ['STRATEGY_HARD_TIMEOUT_MS'] = '120000'  # 2 minutes
        os.environ['MAX_RENDER_MS'] = '60000'  # 1 minute
        
        html = asyncio.run(fetch_with_bypass(url))
        if html and len(html) > 1000:
            print(f"✅ Playwright bypass succeeded: {len(html)} chars")
            return html
    except Exception as e:
        print(f"Playwright bypass failed: {e}")
    
    print("❌ All strategies failed")
    return ""


def _is_valid_article(title: str, url: str) -> bool:
    """
    Universal validation for article titles and URLs
    """
    # Basic validation
    if not title or not url or len(title) < 3:
        return False
    
    # Skip invalid URLs
    if any(skip in url.lower() for skip in ['javascript:', 'mailto:', '#', 'void(0)', 'void(', 'tel:', 'sms:']):
        return False
    
    # Skip navigation and footer links (English)
    nav_words_en = ['home', 'about', 'contact', 'privacy', 'terms', 'login', 'register', 'search', 'menu', 'nav', 'footer', 'header']
    if any(skip in title.lower() for skip in nav_words_en):
        return False
    
    # Skip navigation and footer links (Chinese)
    nav_words_cn = ['首页', '关于', '联系', '隐私', '条款', '登录', '注册', '搜索', '菜单', '导航', '页脚', '页头']
    if any(skip in title for skip in nav_words_cn):
        return False
    
    # Skip if title is just numbers or very short
    if title.isdigit() or len(title.strip()) < 3:
        return False
    
    # Skip common non-article patterns
    if title.lower() in ['read more', 'continue reading', 'more', 'less', 'show', 'hide']:
        return False
    
    return True


def _extract_articles_with_patterns(soup: BeautifulSoup, base_url: str) -> list:
    """
    Extract articles using universal HTML patterns with tiered fallback
    Same logic as used in old scrapers
    """
    articles = []
    
    # Universal patterns for article lists - ordered by specificity and reliability
    patterns = [
        # Tier 1: Most specific and reliable patterns
        {'selector': 'article', 'title': 'h1, h2, h3, h4, h5', 'link': 'a', 'tier': 1, 'description': 'Semantic article elements'},
        {'selector': '[itemtype*="Article"], [itemtype*="NewsArticle"]', 'title': '[itemprop="headline"], [itemprop="name"]', 'link': '[itemprop="url"], a', 'tier': 1, 'description': 'Microdata articles'},
        
        # Tier 2: Common CSS class patterns
        {'selector': '.article, .post, .news-item, .blog-post, .entry', 'title': 'h1, h2, h3, h4, a', 'link': 'a', 'tier': 2, 'description': 'Common article classes'},
        {'selector': '[class*="article"], [class*="post"], [class*="news"], [class*="blog"]', 'title': 'h1, h2, h3, h4, a', 'link': 'a', 'tier': 2, 'description': 'Article-like classes'},
        
        # Tier 3: List-based patterns
        {'selector': 'li', 'title': 'a, h1, h2, h3, h4', 'link': 'a', 'tier': 3, 'description': 'List items with links'},
        {'selector': 'ul li, ol li', 'title': 'a', 'link': 'a', 'tier': 3, 'description': 'Nested list items'},
        
        # Tier 4: Table-based patterns
        {'selector': 'tr', 'title': 'a, td', 'link': 'a', 'tier': 4, 'description': 'Table rows with links'},
        {'selector': 'tbody tr, thead tr', 'title': 'a, td', 'link': 'a', 'tier': 4, 'description': 'Table body/header rows'},
        
        # Tier 5: Generic container patterns
        {'selector': 'div', 'title': 'a, h1, h2, h3, h4', 'link': 'a', 'tier': 5, 'description': 'Generic div containers'},
        {'selector': 'section', 'title': 'h1, h2, h3, h4, a', 'link': 'a', 'tier': 5, 'description': 'Section elements'},
        {'selector': 'p', 'title': 'a', 'link': 'a', 'tier': 5, 'description': 'Paragraphs with links'},
        
        # Tier 6: Direct link patterns (most generic, lowest priority)
        {'selector': 'a[href*="/article/"], a[href*="/news/"], a[href*="/blog/"], a[href*="/post/"]', 'title': 'text', 'link': 'self', 'tier': 6, 'description': 'Direct article links'},
        {'selector': 'a', 'title': 'text', 'link': 'self', 'tier': 6, 'description': 'All links (fallback)'},
    ]
    
    # Process patterns by tier (most specific first)
    for tier in range(1, 7):  # Tiers 1-6
        tier_patterns = [p for p in patterns if p['tier'] == tier]
        print(f"🔍 Processing Tier {tier} patterns...")
        
        for i, pattern in enumerate(tier_patterns):
            containers = soup.select(pattern['selector'])
            print(f"  📋 {pattern['description']}: Found {len(containers)} containers")
            
            tier_articles = []
            
            for container in containers:
                # Handle different pattern types
                if pattern['title'] == 'text' and pattern['link'] == 'self':
                    # Direct link pattern - container is the link itself
                    title = container.get_text(strip=True)
                    url = container.get('href')
                else:
                    # Container pattern - find title and link within container
                    title_elem = container.select_one(pattern['title'])
                    if not title_elem:
                        continue
                    
                    # Find link element
                    link_elem = container.select_one(pattern['link'])
                    if not link_elem or not link_elem.get('href'):
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    url = link_elem.get('href')
                
                # Make URL absolute
                if url and not url.startswith('http'):
                    url = urljoin(base_url, url)
                
                # Universal filtering rules
                if not _is_valid_article(title, url):
                    continue
                
                # Try to find author and date in the container
                author_elem = container.select_one('.author, .byline, [class*="author"], [class*="byline"]')
                date_elem = container.select_one('.date, .time, [class*="date"], [class*="time"], time')
                
                tier_articles.append({
                    'title': title,
                    'url': url,
                    'author': author_elem.get_text(strip=True) if author_elem else '',
                    'published_date': date_elem.get_text(strip=True) if date_elem else '',
                    'description': '',
                    'method': f'pattern_tier_{tier}'
                })
            
            # If this pattern found articles, add them
            if tier_articles:
                articles.extend(tier_articles)
                print(f"  ✅ Added {len(tier_articles)} articles from {pattern['description']}")
        
        # If we found enough articles in this tier, stop processing lower tiers
        if len(articles) >= 5:  # Minimum threshold for good results
            print(f"✅ Tier {tier} found {len(articles)} articles, stopping at tier {tier}")
            break
    
    print(f"📊 Pattern-based extraction completed: {len(articles)} articles found")
    return articles


class MonitorRequest(BaseModel):
    url: HttpUrl
    mode: Literal["sd", "llm", "auto"] = "auto"
    max_articles: int = 10  # Default to 10, user can specify up to 100


@router.post("/monitor")
async def monitor_articles(req: MonitorRequest, request: Request):
    try:
        if await request.is_disconnected():
            return {"error": "Client disconnected"}

        # SD-first: use bypass to fetch, parse minimal structured data and common patterns
        if req.mode == "sd":
            # Add timeout to prevent infinite hanging
            try:
                # Use the same robust bypass approach as old scrapers
                html = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: _robust_fetch_with_timeout(str(req.url))
                    ),
                    timeout=180.0  # 3 minutes timeout (allows for RPA/human simulation)
                )
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "error": "Request timeout after 3 minutes (RPA/human simulation may need more time)",
                    "url": str(req.url),
                    "mode": req.mode,
                }
            
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

            # Use the same robust pattern matching as old scrapers
            articles = _extract_articles_with_patterns(soup, str(req.url))

            return {
                "success": True,
                "url": str(req.url),
                "mode": req.mode,
                "article_count": len(articles),
                "articles": articles[:req.max_articles],
                "max_articles": req.max_articles,
                "monitored_at": datetime.now().isoformat(),
                "extraction_method": "structured_data",
            }

        # LLM/AUTO delegate to crawler if available
        if req.mode in ("llm", "auto"):
            try:
                from src.crawlers.article_crawler import crawl_article_list
                
                # Add timeout to prevent infinite hanging (longer for RPA/human simulation)
                result = await asyncio.wait_for(
                    crawl_article_list(str(req.url), count=req.max_articles, mode=req.mode),
                    timeout=300.0  # 5 minutes timeout for LLM (allows for RPA/human simulation)
                )
                
                articles = result.get("articles", [])
                return {
                    "success": True,
                    "url": str(req.url),
                    "mode": req.mode,
                    "article_count": len(articles),
                    "articles": articles[:req.max_articles],
                    "max_articles": req.max_articles,
                    "monitored_at": datetime.now().isoformat(),
                    "extraction_method": "real_extraction",
                    "token_usage": result.get("token_usage", {}),
                }
            except asyncio.TimeoutError:
                return {
                    "success": False,
                    "error": "LLM extraction timeout after 5 minutes (RPA/human simulation may need more time)",
                    "url": str(req.url),
                    "mode": req.mode,
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


