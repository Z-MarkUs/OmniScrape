"""
Enhanced Anti-Bot Bypass Module
Universal bypass strategies for all scraping functions
"""
import asyncio
import contextlib
import os
import random
import time
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential
import requests
from bs4 import BeautifulSoup

RENDER_MS = int(os.getenv("MAX_RENDER_MS", "20000"))

# Proxy rotation support
_DOMAIN_PROXY_CACHE: dict[str, str] = {}

def _get_proxy_pool() -> list[str]:
    raw = os.getenv("PROXY_URLS", "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]

def _choose_proxy(url: str) -> str | None:
    pool = _get_proxy_pool()
    if not pool:
        return None
    strategy = os.getenv("PROXY_ROTATION", "per_request").strip().lower()
    if strategy == "per_domain":
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            host = ""
        if host in _DOMAIN_PROXY_CACHE and _DOMAIN_PROXY_CACHE[host] in pool:
            return _DOMAIN_PROXY_CACHE[host]
        proxy = random.choice(pool)
        _DOMAIN_PROXY_CACHE[host] = proxy
        return proxy
    return random.choice(pool)

def _format_proxy(proxy_url: str | None):
    if not proxy_url:
        return None
    try:
        parsed = urlparse(proxy_url)
        server = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}" if parsed.hostname and parsed.port else proxy_url
        proxy_conf = {"server": server}
        if parsed.username:
            proxy_conf["username"] = parsed.username
        if parsed.password:
            proxy_conf["password"] = parsed.password
        proxy_conf.setdefault("username", os.getenv("PROXY_USERNAME") or None)
        proxy_conf.setdefault("password", os.getenv("PROXY_PASSWORD") or None)
        return {k: v for k, v in proxy_conf.items() if v}
    except Exception:
        username = os.getenv("PROXY_USERNAME")
        password = os.getenv("PROXY_PASSWORD")
        if username or password:
            return {"server": proxy_url, "username": username, "password": password}
        return {"server": proxy_url}

def _get_random_user_agent():
    """Get a random realistic user agent"""
    user_agents = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Android 14; Mobile; rv:109.0) Gecko/121.0 Firefox/121.0",
        "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ]
    return random.choice(user_agents)

def _get_mobile_user_agent():
    """Get mobile user agent"""
    mobile_agents = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Android 14; Mobile; rv:109.0) Gecko/121.0 Firefox/121.0",
        "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    ]
    return random.choice(mobile_agents)

@contextlib.asynccontextmanager
async def _browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, 
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-extensions",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--disable-ipc-flooding-protection",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-client-side-phishing-detection",
                "--disable-sync",
                "--disable-default-apps",
                "--disable-hang-monitor",
                "--disable-prompt-on-repost",
                "--disable-domain-reliability",
                "--disable-component-extensions-with-background-pages",
                "--disable-background-timer-throttling",
                "--disable-background-networking",
                "--disable-breakpad",
                "--disable-component-update",
                "--disable-features=TranslateUI",
                "--disable-features=BlinkGenPropertyTrees",
                "--no-first-run",
                "--no-default-browser-check",
                "--no-pings",
                "--password-store=basic",
                "--use-mock-keychain",
                "--disable-logging",
                "--disable-permissions-api",
                "--disable-presentation-api",
                "--disable-print-preview",
                "--disable-speech-api",
                "--hide-scrollbars",
                "--mute-audio",
                "--no-zygote",
                "--single-process",
                "--disable-background-mode",
                "--disable-plugins-discovery",
                "--disable-preconnect",
                "--disable-translate",
                "--disable-web-resources",
                "--aggressive-cache-discard",
                "--memory-pressure-off",
                "--max_old_space_size=4096",
                "--disable-features=site-per-process",
                "--disable-site-isolation-trials",
                "--disable-features=VizDisplayCompositor",
                "--disable-features=AudioServiceOutOfProcess",
                "--disable-features=MediaRouter",
                "--disable-features=OptimizationHints",
                "--disable-features=Translate",
                "--disable-features=BlinkGenPropertyTrees",
                "--disable-features=CalculateNativeWinOcclusion",
                "--disable-features=VaapiVideoDecoder",
                "--disable-features=VaapiVideoEncoder"
            ]
        )
        try:
            yield browser
        finally:
            await browser.close()

async def _simulate_human_behavior(page):
    """Enhanced human behavior simulation"""
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(random.randint(3000, 6000))
        
        # More realistic mouse movements
        for _ in range(random.randint(8, 15)):
            start_x = random.randint(100, 1800)
            start_y = random.randint(100, 1000)
            end_x = random.randint(100, 1800)
            end_y = random.randint(100, 1000)
            
            steps = random.randint(10, 25)
            for i in range(steps):
                progress = i / steps
                curve_offset = random.randint(-80, 80) * (progress * (1 - progress))
                x = start_x + (end_x - start_x) * progress + curve_offset
                y = start_y + (end_y - start_y) * progress + curve_offset
                await page.mouse.move(x, y)
                await page.wait_for_timeout(random.randint(50, 150))
        
        # Enhanced scrolling with reading pauses
        await page.wait_for_timeout(random.randint(2000, 4000))
        
        for _ in range(random.randint(8, 15)):
            scroll_amount = random.randint(100, 300)
            await page.evaluate(f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}})")
            await page.wait_for_timeout(random.randint(1500, 3000))
        
        # Random interactions
        try:
            await page.click("body", timeout=2000)
            await page.wait_for_timeout(random.randint(500, 1000))
        except:
            pass
        
        # Keyboard simulation
        for _ in range(random.randint(3, 6)):
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(random.randint(300, 700))
        
        # Final pause
        await page.wait_for_timeout(random.randint(2000, 4000))
        
    except Exception as e:
        print(f"Human behavior simulation failed: {e}")

async def fetch_with_bypass(url: str, max_retries: int = 3) -> str:
    """
    Universal bypass function with multiple strategies
    """
    strategies = [
        _try_playwright_desktop,
        _try_playwright_mobile,
        _try_requests_fallback,
        _try_site_specific_fallback
    ]
    
    for attempt in range(max_retries):
        for strategy in strategies:
            try:
                result = await strategy(url)
                if result and len(result.strip()) > 1000:
                    return result
            except Exception as e:
                print(f"Strategy {strategy.__name__} failed: {e}")
                continue
        
        if attempt < max_retries - 1:
            await asyncio.sleep(random.randint(2, 5))
    
    return ""

async def _try_playwright_desktop(url: str) -> str:
    """Desktop Playwright with enhanced stealth"""
    async with _browser() as browser:
        user_agent = _get_random_user_agent()
        proxy = _choose_proxy(url)
        
        ctx = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            proxy=_format_proxy(proxy),
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0"
            }
        )
        
        page = await ctx.new_page()
        
        # Enhanced stealth script
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
            Object.defineProperty(navigator, 'connection', { get: () => ({ effectiveType: '4g', rtt: 50, downlink: 10 }) });
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)
        
        # Block resources
        await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}", lambda route: route.abort())
        await page.route("**/analytics/**", lambda route: route.abort())
        await page.route("**/tracking/**", lambda route: route.abort())
        await page.route("**/ads/**", lambda route: route.abort())
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=RENDER_MS)
            await _simulate_human_behavior(page)
            await page.wait_for_timeout(3000)
        except Exception:
            try:
                await page.goto(url, wait_until="networkidle", timeout=RENDER_MS)
                await page.wait_for_timeout(5000)
            except Exception:
                await page.goto(url, timeout=RENDER_MS)
                await page.wait_for_timeout(5000)
        
        html = await page.content()
        await ctx.close()
        return html

async def _try_playwright_mobile(url: str) -> str:
    """Mobile Playwright fallback"""
    async with _browser() as browser:
        mobile_ua = _get_mobile_user_agent()
        proxy = _choose_proxy(url)
        
        ctx = await browser.new_context(
            user_agent=mobile_ua,
            viewport={"width": 390, "height": 844},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            proxy=_format_proxy(proxy),
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "max-age=0",
                "Upgrade-Insecure-Requests": "1",
                "sec-ch-ua-mobile": "?1",
                "sec-ch-ua-platform": '"iOS"'
            }
        )
        
        page = await ctx.new_page()
        await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}", lambda route: route.abort())
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=RENDER_MS)
            await page.wait_for_timeout(2000)
            await page.evaluate("window.scrollBy({top: 400, behavior: 'smooth'})")
            await page.wait_for_timeout(2000)
            await page.evaluate("window.scrollBy({top: 800, behavior: 'smooth'})")
            await page.wait_for_timeout(2000)
        except Exception:
            try:
                await page.goto(url, wait_until="networkidle", timeout=RENDER_MS)
            except Exception:
                pass
        
        html = await page.content()
        await ctx.close()
        return html

async def _try_requests_fallback(url: str) -> str:
    """Requests-based fallback"""
    try:
        headers = {
            "User-Agent": _get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception:
        return ""

async def _try_site_specific_fallback(url: str) -> str:
    """Site-specific fallback strategies"""
    import re
    
    # 36kr mobile fallback
    m = re.match(r"https?://(?:www\.)?36kr\.com/p/(\d+)", url)
    if m:
        article_id = m.group(1)
        mobile_url = f"https://m.36kr.com/p/{article_id}"
        
        async with _browser() as browser:
            mobile_ua = _get_mobile_user_agent()
            ctx = await browser.new_context(
                user_agent=mobile_ua,
                viewport={"width": 390, "height": 844},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Cache-Control": "max-age=0",
                    "Upgrade-Insecure-Requests": "1",
                    "sec-ch-ua-mobile": "?1",
                    "sec-ch-ua-platform": '"iOS"'
                }
            )
            
            page = await ctx.new_page()
            await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}", lambda route: route.abort())
            
            try:
                await page.goto(mobile_url, wait_until="domcontentloaded", timeout=RENDER_MS)
                await page.wait_for_timeout(2000)
                await page.evaluate("window.scrollBy({top: 400, behavior: 'smooth'})")
                await page.wait_for_timeout(2000)
                await page.evaluate("window.scrollBy({top: 800, behavior: 'smooth'})")
                await page.wait_for_timeout(2000)
            except Exception:
                try:
                    await page.goto(mobile_url, wait_until="networkidle", timeout=RENDER_MS)
                except Exception:
                    pass
            
            html = await page.content()
            await ctx.close()
            return html
    
    return ""

# Legacy compatibility
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
async def fetch_rendered(url: str, user_agent: str | None = None) -> str:
    """Legacy function for backward compatibility"""
    return await fetch_with_bypass(url)
