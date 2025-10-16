#!/usr/bin/env python3
"""
Generic Crawler with Anti-Bot Bypass and Semantic Filtering
Originally optimized for ETNet China, now generalized
"""

import asyncio
import logging
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Tuple
from urllib.parse import urljoin
import json
import os

# Load env
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# Import the bypass module
from bypass import fetch_with_bypass

# Import semantic matching dependencies
try:
    from sentence_transformers import SentenceTransformer
    from sentence_transformers.util import cos_sim
    import torch
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    print("Warning: sentence-transformers not available. Semantic filtering disabled.")

# Import content extraction libraries
try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    print("Warning: trafilatura not available. Using basic extraction.")

from bs4 import BeautifulSoup

DEFAULT_KEYWORDS = [
    "中國", "財經", "經濟", "金融", "投資", "股市", "港股", "A股",
    "人民幣", "央行", "政策", "貿易", "出口", "進口", "GDP", "通脹",
    "房地產", "科技", "互聯網", "人工智能", "新能源", "環保"
]

class Crawler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.semantic_model = None
        # Persistent session for cookie reuse
        try:
            import requests
            self.session = requests.Session()
        except Exception:
            self.session = None
        
        # Configurable params
        try:
            self.semantic_threshold = float(os.getenv("SEMANTIC_THRESHOLD", "0.3"))
        except Exception:
            self.semantic_threshold = 0.3
        try:
            self.env_max_articles = int(os.getenv("MAX_ARTICLES", "30"))
        except Exception:
            self.env_max_articles = 30
        
        if SEMANTIC_AVAILABLE:
            try:
                self.semantic_model = SentenceTransformer('all-MiniLM-L6-v2')
                self.logger.info("Semantic model loaded successfully")
            except Exception as e:
                self.logger.warning(f"Failed to load semantic model: {e}")
                self.semantic_model = None
        
        # Load target keywords from env; fallback to default if empty/invalid
        env_keywords = os.getenv("KEYWORDS", "").strip()
        parsed_keywords: List[str] = []
        if env_keywords:
            if env_keywords.startswith("["):
                try:
                    parsed = json.loads(env_keywords)
                    if isinstance(parsed, list):
                        parsed_keywords = [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    parsed_keywords = []
            else:
                parsed_keywords = [k.strip() for k in env_keywords.split(",") if k.strip()]
        self.target_keywords = parsed_keywords if parsed_keywords else DEFAULT_KEYWORDS
        if not parsed_keywords:
            self.logger.info("KEYWORDS not set or empty; using default keyword list")
        
        self.logger.info("Crawler initialized")

    async def discover_articles(self, base_url: str, max_articles: int = 50) -> List[Dict[str, Any]]:
        try:
            # Requests-first fast path for list pages with strict timeout
            import requests
            cache_path = os.path.join(os.path.dirname(__file__), '.cache')
            os.makedirs(cache_path, exist_ok=True)
            cache_file = os.path.join(cache_path, 'etnet_list.html')
            try:
                # Prefer mobile UA + referer for ETNet (try multiple pages) with session
                import requests
                sess = self.session or requests.Session()
                mobile_headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Referer': f"{base_url.rsplit('/', 1)[0]}/",
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                }
                desktop_headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Referer': f"{base_url.rsplit('/', 1)[0]}/",
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                }
                html = ""
                candidates = [base_url, f"{base_url}?page=2", f"{base_url}?page=3"]
                # Warm up homepage to get cookies
                home_url = f"{base_url.split('/list/')[0]}/"
                try:
                    sess.get(home_url, headers=mobile_headers, timeout=6)
                except Exception:
                    pass
                for u in candidates:
                    for hdr in (mobile_headers, desktop_headers):
                        try:
                            resp = sess.get(u, headers=hdr, timeout=10)
                            if resp.status_code == 200 and len(resp.text) > 5000 and "loading" not in resp.text.lower():
                                html = resp.text
                                self.logger.info(f"[discover] fetched {u} len={len(html)} with headers={'mobile' if hdr is mobile_headers else 'desktop'}")
                                try:
                                    with open(cache_file, 'w', encoding='utf-8') as f:
                                        f.write(html)
                                except Exception:
                                    pass
                                break
                        except Exception:
                            continue
                    if html:
                        break
                # If still too small, fallback to readable proxy for discovery
                if not html or len(html) < 5000:
                    # Try cache first
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                cached = f.read()
                            if len(cached) > 5000:
                                html = cached
                                self.logger.info(f"[discover] using cached list html len={len(html)}")
                        except Exception:
                            pass
                if not html or len(html) < 5000:
                    # One-time lightweight Playwright capture to seed cache
                    try:
                        from playwright.async_api import async_playwright
                        async with async_playwright() as p:
                            browser = await p.chromium.launch(headless=True)
                            ctx = await browser.new_context(user_agent=desktop_headers['User-Agent'])
                            page = await ctx.new_page()
                            try:
                                await page.goto(base_url, wait_until='domcontentloaded', timeout=7000)
                            except Exception:
                                try:
                                    await page.goto(base_url, wait_until='networkidle', timeout=7000)
                                except Exception:
                                    pass
                            try:
                                content = await page.content()
                            finally:
                                await ctx.close()
                                await browser.close()
                            if content and len(content) > 5000:
                                html = content
                                self.logger.info(f"[discover] playwright list capture len={len(html)}")
                                try:
                                    with open(cache_file, 'w', encoding='utf-8') as f:
                                        f.write(html)
                                except Exception:
                                    pass
                    except Exception:
                        pass
                if not html or len(html) < 5000:
                    try:
                        from urllib.parse import urlparse
                        host = urlparse(base_url).hostname or ""
                        proxy_url = f"https://r.jina.ai/http://{host}{urlparse(base_url).path}"
                        pr = sess.get(proxy_url, headers=desktop_headers, timeout=10)
                        if pr.status_code == 200 and len(pr.text) > 5000:
                            html = pr.text
                            self.logger.info(f"[discover] fetched via proxy len={len(html)}")
                    except Exception:
                        pass
            except Exception:
                html = ""
            if not html:
                # Fallback to bypass with overall timeout as last resort
                try:
                    html = await asyncio.wait_for(fetch_with_bypass(base_url), timeout=15)
                except Exception:
                    html = ""
            if not html:
                import requests
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                }
                try:
                    resp = requests.get(base_url, headers=headers, timeout=15)
                    html = resp.text if resp.status_code == 200 else ""
                except Exception:
                    return []
            if not html:
                return []
            soup = BeautifulSoup(html, 'html.parser')
            articles = []
            # Site-specific selectors for ETNet China
            selectors = [
                'div.list-title a',              # primary title links on ETNet list
                'ul.column-list li a',           # alternate list layout
                'a[href*="/content/"], a[href*="/list/"]',
                'a[href*="article"], a[href*="news"]',
                '.article-item a', '.news-item a', 'li a[href*="http"]'
            ]
            self.logger.info(f"[discover] Trying selectors: {selectors}")
            for sel_idx, sel in enumerate(selectors):
                found = soup.select(sel)
                self.logger.info(f"[discover] Selector '{sel}' found {len(found)} links")
                if sel_idx == 0 and found:
                    try:
                        sample = [getattr(l, 'get')("href", "") if hasattr(l, 'get') else "" for l in found[:50]]
                        self.logger.info(f"[discover] sample hrefs (first 50): {sample}")
                    except Exception:
                        pass
                kept = 0
                for idx_link, link in enumerate(found[:max_articles*3]):
                    href = link.get('href', '')
                    title = link.get_text(strip=True) or link.get('title', '').strip()
                    if not title:
                        # fallback: derive from URL slug
                        try:
                            slug = href.rstrip('/').split('/')[-1]
                            title = re.sub(r'[-_]+', ' ', slug)
                        except Exception:
                            title = ''
                    # Prefer ETNet article detail pages; exclude list/category pages
                    if "etnetchina.cn" in base_url:
                        if "/list/" in href:
                            # skip list pages
                            self.logger.debug(f"[discover] skip list href={href} title='{title}'")
                            continue
                        # accept common detail patterns
                        detail_ok = any(p in href for p in ["/content/", "/article/", "/blog/"])
                        if not detail_ok:
                            self.logger.debug(f"[discover] skip non-detail href={href} title='{title}'")
                            continue
                    if self._is_valid_article(title, href):
                        if href.startswith('/') or not href.startswith('http'):
                            href = urljoin(base_url, href)
                        articles.append({'title': title, 'url': href, 'published_date': '', 'author': ''})
                        kept += 1
                        if kept >= max_articles:
                            break
            seen, uniq = set(), []
            for a in articles:
                if a['url'] not in seen:
                    seen.add(a['url'])
                    uniq.append(a)
            # JSON/XHR probe: look for API endpoints in inline scripts
            if not uniq:
                try:
                    scripts = soup.find_all('script')
                    api_urls = []
                    for sc in scripts:
                        txt = sc.string or sc.get_text() or ""
                        for m in re.findall(r'https?://[^\s\"\']+(?:api|list|article)[^\s\"\']*', txt):
                            if 'etnetchina.cn' in m:
                                api_urls.append(m)
                        for m in re.findall(r'/(?:api|list|article)[^\s\"\']+', txt):
                            api_urls.append(urljoin(base_url, m))
                    api_urls = [u for u in api_urls if any(k in u.lower() for k in ['api', 'list', 'article'])]
                    api_urls = list(dict.fromkeys(api_urls))
                    self.logger.info(f"[discover] XHR probe candidates: {len(api_urls)}")
                    import requests
                    sess = self.session or requests.Session()
                    for u in api_urls[:5]:
                        try:
                            r = sess.get(u, timeout=8)
                            if r.status_code == 200 and 'application/json' in r.headers.get('Content-Type',''):
                                data = r.json()
                                # naive scan for URLs
                                urls = re.findall(r'https?://column\.etnetchina\.cn/[A-Za-z0-9_\-/]+', json.dumps(data, ensure_ascii=False))
                                detail = [x for x in urls if any(p in x for p in ['/content/', '/article/', '/blog/'])]
                                self.logger.info(f"[discover] XHR json yielded {len(detail)} detail urls")
                                for x in detail:
                                    if x not in seen:
                                        seen.add(x)
                                        uniq.append({'title': '', 'url': x, 'published_date': '', 'author': ''})
                                        if len(uniq) >= max_articles:
                                            break
                            if len(uniq) >= max_articles:
                                break
                        except Exception:
                            continue
                except Exception:
                    pass
            if not uniq:
                # Regex fallback: extract likely detail URLs directly from HTML
                try:
                    detail_paths = re.findall(r'href="((?:https?:\/\/[^\"]+)?\/[^"]*(?:content|article|blog)[^\"]*)"', html)
                    self.logger.info(f"[discover] regex detail paths found: {len(detail_paths)}")
                    for path in detail_paths:
                        full = urljoin(base_url, path)
                        if full not in seen:
                            seen.add(full)
                            uniq.append({
                                'title': '',
                                'url': full,
                                'published_date': '',
                                'author': ''
                            })
                            if len(uniq) >= max_articles:
                                break
                    if not uniq:
                        # Absolute URL scan as last resort
                        abs_urls = set(re.findall(r'https?://column\.etnetchina\.cn/(?:content|article|blog)/[A-Za-z0-9_\-/]+', html))
                        self.logger.info(f"[discover] absolute url scan found: {len(abs_urls)}")
                        for u in abs_urls:
                            if u not in seen:
                                seen.add(u)
                                uniq.append({'title': '', 'url': u, 'published_date': '', 'author': ''})
                                if len(uniq) >= max_articles:
                                    break
                except Exception:
                    pass
            if not uniq and "etnetchina.cn" in base_url:
                # Search engine fallback: Bing site search for recent content links
                try:
                    import requests
                    q = "site:column.etnetchina.cn content"
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    }
                    resp = requests.get("https://www.bing.com/search", params={"q": q}, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        bs = BeautifulSoup(resp.text, 'html.parser')
                        links = []
                        for a in bs.select('li.b_algo h2 a, a[href]'):
                            href = a.get('href', '')
                            if 'column.etnetchina.cn' in href and any(p in href for p in ['/content/', '/article/', '/blog/']):
                                links.append(href)
                        self.logger.info(f"[discover] bing fallback links: {len(links)}")
                        for u in links:
                            if u not in seen:
                                seen.add(u)
                                uniq.append({'title': '', 'url': u, 'published_date': '', 'author': ''})
                                if len(uniq) >= max_articles:
                                    break
                except Exception as e:
                    self.logger.warning(f"[discover] bing fallback failed: {e}")
            return uniq[:max_articles]
        except Exception:
            return []

    def _is_valid_article(self, title: str, url: str) -> bool:
        if not title or len(title) < 4:  # relax for Chinese short titles
            return False
        for pat in ['javascript:', 'mailto:', '#', 'tel:', 'ftp:', 'login', 'register', 'about', 'contact', 'privacy', 'terms', 'cookie', 'sitemap', 'rss', 'feed']:
            if pat in url.lower():
                return False
        if title.lower() in ['more', 'read more', 'continue', 'next', 'previous']:
            return False
        return True

    async def fetch_article_content(self, article_url: str) -> str:
        try:
            # Cap overall fetch time per article
            try:
                html = await asyncio.wait_for(fetch_with_bypass(article_url), timeout=20)
            except Exception:
                html = ""
            if not html:
                # Fallback: try readable proxy for content pages
                try:
                    from urllib.parse import urlparse
                    host = urlparse(article_url).hostname or ""
                    proxy_url = f"https://r.jina.ai/http://{host}{urlparse(article_url).path}"
                    import requests
                    resp = requests.get(proxy_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/plain,*/*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    }, timeout=10)
                    if resp.status_code == 200 and len(resp.text) > 100:
                        # Treat as already extracted text
                        text_only = self._clean(resp.text)
                        return text_only
                except Exception:
                    pass
                return ""
            if TRAFILATURA_AVAILABLE:
                try:
                    content = trafilatura.extract(html)
                    if content and len(content) > 100:
                        return self._clean(content)
                except Exception:
                    pass
            soup = BeautifulSoup(html, 'html.parser')
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()
            candidates = [
                'article', '.article-content', '.content', '.main-content',
                '.post-content', '.entry-content', '.article-body', '.news-content',
                'main', '.main', '#content', '#main'
            ]
            text = ""
            for sel in candidates:
                el = soup.select_one(sel)
                if el:
                    text = el.get_text(separator=' ', strip=True)
                    if len(text) > 200:
                        break
            if len(text) < 200:
                text = soup.get_text(separator=' ', strip=True)
            return self._clean(text)
        except Exception:
            return ""

    async def fetch_article_detail(self, article_url: str) -> Tuple[str, str]:
        """Fetch full content and try to derive a meaningful title from the page.
        Returns (content, derived_title). derived_title may be empty if unavailable.
        """
        content = ""
        derived_title = ""
        try:
            # Try normal rendered fetch first
            try:
                html = await asyncio.wait_for(fetch_with_bypass(article_url), timeout=20)
            except Exception:
                html = ""
            if html:
                try:
                    soup = BeautifulSoup(html, 'html.parser')
                    # Prefer common title sources
                    t_el = soup.find('meta', attrs={'property': 'og:title'}) or soup.find('meta', attrs={'name': 'og:title'})
                    if t_el and t_el.get('content'):
                        derived_title = (t_el.get('content') or '').strip()
                    if not derived_title and soup.title and soup.title.string:
                        derived_title = (soup.title.string or '').strip()
                    if not derived_title:
                        h_el = soup.find(['h1', 'h2'])
                        if h_el:
                            derived_title = h_el.get_text(strip=True)
                except Exception:
                    pass
                # Extract content via trafilatura or fallback selectors
                if TRAFILATURA_AVAILABLE:
                    try:
                        extracted = trafilatura.extract(html)
                        if extracted and len(extracted) > 100:
                            content = self._clean(extracted)
                    except Exception:
                        pass
                if not content:
                    try:
                        soup = BeautifulSoup(html, 'html.parser')
                        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                            tag.decompose()
                        candidates = [
                            'article', '.article-content', '.content', '.main-content',
                            '.post-content', '.entry-content', '.article-body', '.news-content',
                            'main', '.main', '#content', '#main'
                        ]
                        text = ""
                        for sel in candidates:
                            el = soup.select_one(sel)
                            if el:
                                text = el.get_text(separator=' ', strip=True)
                                if len(text) > 200:
                                    break
                        if len(text) < 200:
                            text = soup.get_text(separator=' ', strip=True)
                        content = self._clean(text)
                    except Exception:
                        pass
            # Proxy text-only fallback
            if not content:
                try:
                    from urllib.parse import urlparse
                    host = urlparse(article_url).hostname or ""
                    proxy_url = f"https://r.jina.ai/http://{host}{urlparse(article_url).path}"
                    import requests
                    resp = requests.get(proxy_url, headers={
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/plain,*/*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    }, timeout=10)
                    if resp.status_code == 200 and len(resp.text) > 50:
                        text_only = self._clean(resp.text)
                        content = text_only
                        # Derive a simple title from first line if missing
                        if not derived_title:
                            first_line = text_only.split("\n", 1)[0].strip()
                            derived_title = first_line[:80]
                except Exception:
                    pass
        except Exception:
            pass
        return content, (derived_title or "")

    def _clean(self, content: str) -> str:
        content = re.sub(r'\s+', ' ', content or '').strip()
        if len(content) > 2000:
            content = content[:2000] + "..."
        return content

    def semantic_keyword_matching(self, title: str, content: str, target_keywords: List[str]) -> Tuple[str, float] | None:
        if not self.semantic_model or not target_keywords:
            return None
        try:
            base_text = (title or "") + " " + (content or "")
            text_to_match = base_text[:1000]
            text_emb = self.semantic_model.encode([text_to_match], normalize_embeddings=True, convert_to_tensor=True)
            kw_embs = self.semantic_model.encode(target_keywords, normalize_embeddings=True, convert_to_tensor=True)
            if kw_embs.numel() == 0:
                return None
            sims = cos_sim(text_emb, kw_embs).squeeze(0)
            if sims.numel() == 0:
                return None
            best_val, best_idx = sims.max(dim=0)
            best_kw = target_keywords[int(best_idx)]
            score = float(best_val.item())
            return (best_kw, score)
        except Exception as e:
            self.logger.error(f"Semantic matching failed: {e}")
            return None

    def detect_words(self, word_groups: List[str], title: str, content: str) -> str | None:
        hay = (title or "") + " " + (content or "")
        hay = hay.lower()
        for word in word_groups:
            parts = [p.strip().lower() for p in word.split("+") if p.strip()]
            if parts and all(p in hay for p in parts):
                return word
        return None

    def hybrid_keyword_matching(self, title: str, content: str, word_groups: List[str]) -> Dict[str, Any] | None:
        regex_match = self.detect_words(word_groups, title, content)
        sem = self.semantic_keyword_matching(title, content, self.target_keywords)
        sem_score = sem[1] if sem else 0.0
        if regex_match:
            return {"keyword": regex_match, "similarity": sem_score}
        if sem and sem_score >= self.semantic_threshold:
            return {"keyword": sem[0], "similarity": sem_score}
        return None

    async def run(self, target_url: str, max_articles: int | None = None):
        if max_articles is None:
            max_articles = self.env_max_articles
        articles = await self.discover_articles(target_url, max_articles)
        enriched = []
        for a in articles:
            content, derived_title = await self.fetch_article_detail(a['url'])
            a['content'] = content
            if (not a.get('title')) or len(a.get('title','').strip()) < 4:
                if derived_title:
                    a['title'] = derived_title
            a['preview'] = content[:200] + "..." if len(content) > 200 else content
            sem = self.semantic_keyword_matching(a['title'], a['content'] or a['preview'], self.target_keywords)
            a['similarity'] = sem[1] if sem else 0.0
            match = self.hybrid_keyword_matching(a['title'], a['content'], self.target_keywords)
            if match:
                a['matched'] = True
                a['matched_keywords'] = match['keyword']
            else:
                a['matched'] = False
            enriched.append(a)
        return enriched

# Test function remains usable
async def test_crawler():
    logging.basicConfig(level=logging.INFO)
    c = Crawler()
    results = await c.run("https://column.etnetchina.cn/list/article-latest", None)
    print(f"Total: {len(results)} matched: {sum(1 for r in results if r.get('matched'))}")

if __name__ == "__main__":
    asyncio.run(test_crawler())
