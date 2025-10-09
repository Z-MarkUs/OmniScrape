import asyncio, contextlib, os
import random
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

RENDER_MS = int(os.getenv("MAX_RENDER_MS", "15000"))

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
    # default per_request
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
        # Fallback to global credentials if set
        proxy_conf.setdefault("username", os.getenv("PROXY_USERNAME") or None)
        proxy_conf.setdefault("password", os.getenv("PROXY_PASSWORD") or None)
        # Remove Nones
        return {k: v for k, v in proxy_conf.items() if v}
    except Exception:
        # Best-effort
        username = os.getenv("PROXY_USERNAME")
        password = os.getenv("PROXY_PASSWORD")
        if username or password:
            return {"server": proxy_url, "username": username, "password": password}
        return {"server": proxy_url}

@contextlib.asynccontextmanager
async def _browser():
    async with async_playwright() as p:
        # Enhanced browser launch with more stealth options
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
                "--max_old_space_size=4096"
            ]
        )
        try:
            yield browser
        finally:
            await browser.close()

def _get_random_user_agent():
    """Get a random realistic user agent"""
    import random
    user_agents = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    ]
    return random.choice(user_agents)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
async def fetch_rendered(url: str, user_agent: str | None = None) -> str:
    async with _browser() as browser:
        # Use random user agent if not provided
        if not user_agent:
            user_agent = _get_random_user_agent()

        # Pick proxy for this primary attempt
        primary_proxy = _choose_proxy(url)

        ctx = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            # Add more realistic browser settings
            locale="en-US",
            timezone_id="America/New_York",
            proxy=_format_proxy(primary_proxy),
            # Disable automation detection
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
                "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"'
            }
        )
        page = await ctx.new_page()
        
        # Add comprehensive stealth measures
        await page.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock plugins with realistic data
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    return [
                        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                        { name: 'Native Client', filename: 'internal-nacl-plugin' }
                    ];
                },
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Mock chrome runtime
            if (!window.chrome) {
                window.chrome = {
                    runtime: {
                        onConnect: undefined,
                        onMessage: undefined
                    }
                };
            }
            
            // Mock screen properties
            Object.defineProperty(screen, 'availHeight', {
                get: () => 1055,
            });
            Object.defineProperty(screen, 'availWidth', {
                get: () => 1920,
            });
            
            // Mock timezone
            Object.defineProperty(Intl.DateTimeFormat.prototype, 'resolvedOptions', {
                value: function() {
                    return { timeZone: 'America/New_York' };
                }
            });
            
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Mock realistic hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
            });
            
            // Mock realistic memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
            });
            
            // Mock realistic connection
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                }),
            });
            
            // Override getParameter to hide automation
            const originalGetParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return originalGetParameter.call(this, parameter);
            };
            
            // Mock realistic canvas fingerprint
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {
                const context = this.getContext('2d');
                context.fillStyle = 'rgba(255, 0, 0, 0.1)';
                context.fillRect(0, 0, 1, 1);
                return originalToDataURL.apply(this, arguments);
            };
            
            // Mock realistic WebRTC
            if (window.RTCPeerConnection) {
                const originalCreateDataChannel = RTCPeerConnection.prototype.createDataChannel;
                RTCPeerConnection.prototype.createDataChannel = function() {
                    return originalCreateDataChannel.apply(this, arguments);
                };
            }
            
            // Remove automation from window
            Object.defineProperty(window, 'outerHeight', {
                get: () => 1080,
            });
            Object.defineProperty(window, 'outerWidth', {
                get: () => 1920,
            });
        """)
        
        # Block unnecessary resources to speed up loading
        await page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}", lambda route: route.abort())
        await page.route("**/analytics/**", lambda route: route.abort())
        await page.route("**/tracking/**", lambda route: route.abort())
        await page.route("**/ads/**", lambda route: route.abort())
        
        try:
            # Simulate human-like navigation
            await page.goto(url, wait_until="domcontentloaded", timeout=RENDER_MS)
            
            # Simulate human behavior
            await _simulate_human_behavior(page)
            
            # Wait for dynamic content
            await page.wait_for_timeout(2000)
            
        except Exception:
            try:
                # Fallback: try with networkidle
                await page.goto(url, wait_until="networkidle", timeout=RENDER_MS)
                await _simulate_human_behavior(page)
            except Exception:
                try:
                    # Last resort: basic load
                    await page.goto(url, timeout=RENDER_MS)
                    await page.wait_for_timeout(3000)
                except Exception as e:
                    print(f"Failed to load {url}: {e}")
                    return ""
        
        html = await page.content()
        await ctx.close()

        # Generic mobile retry for all pages if content is empty or too short
        try:
            if not html or len(html.strip()) < 3000:
                async with _browser() as browser_m:
                    mobile_ua = (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
                    )
                    # If we have proxies, try a different one than primary for the retry
                    retry_proxy = None
                    pool = _get_proxy_pool()
                    if pool:
                        candidates = [p for p in pool if p != primary_proxy]
                        retry_proxy = random.choice(candidates) if candidates else primary_proxy
                    ctx_m = await browser_m.new_context(
                        user_agent=mobile_ua,
                        viewport={"width": 390, "height": 844},
                        locale="zh-CN",
                        timezone_id="Asia/Shanghai",
                        proxy=_format_proxy(retry_proxy),
                        extra_http_headers={
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                            "Cache-Control": "max-age=0",
                            "Upgrade-Insecure-Requests": "1",
                            "sec-ch-ua-mobile": "?1",
                            "sec-ch-ua-platform": '"iOS"'
                        }
                    )
                    page_m = await ctx_m.new_page()
                    await page_m.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}", lambda route: route.abort())
                    try:
                        await page_m.goto(url, wait_until="domcontentloaded", timeout=RENDER_MS)
                        await page_m.wait_for_timeout(1200)
                        await page_m.evaluate("window.scrollBy({top: 400, behavior: 'smooth'})")
                        await page_m.wait_for_timeout(1200)
                        await page_m.evaluate("window.scrollBy({top: 800, behavior: 'smooth'})")
                        await page_m.wait_for_timeout(1200)
                    except Exception:
                        try:
                            await page_m.goto(url, wait_until="networkidle", timeout=RENDER_MS)
                        except Exception:
                            pass
                    mobile_same_html = await page_m.content()
                    await ctx_m.close()
                    if mobile_same_html and len(mobile_same_html.strip()) > len(html.strip()):
                        html = mobile_same_html
        except Exception:
            pass

        # Targeted fallback: 36kr article pages often block desktop scraping.
        # If URL matches 36kr article pattern and content still seems too short, retry mobile article page.
        try:
            import re
            m = re.match(r"https?://(?:www\.)?36kr\.com/p/(\d+)", url)
            if m and (not html or len(html.strip()) < 3000):
                article_id = m.group(1)
                mobile_url = f"https://m.36kr.com/p/{article_id}"

                async with _browser() as browser2:
                    # iPhone Safari UA and mobile headers
                    mobile_ua = (
                        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
                        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
                    )
                    ctx2 = await browser2.new_context(
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
                    page2 = await ctx2.new_page()

                    # Lighter resource blocking
                    await page2.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf,eot}", lambda route: route.abort())

                    try:
                        await page2.goto(mobile_url, wait_until="domcontentloaded", timeout=RENDER_MS)
                        # Minimal human-like behavior for mobile
                        await page2.wait_for_timeout(1200)
                        await page2.evaluate("window.scrollBy({top: 400, behavior: 'smooth'})")
                        await page2.wait_for_timeout(1200)
                        await page2.evaluate("window.scrollBy({top: 800, behavior: 'smooth'})")
                        await page2.wait_for_timeout(1200)
                    except Exception:
                        try:
                            await page2.goto(mobile_url, wait_until="networkidle", timeout=RENDER_MS)
                        except Exception:
                            pass

                    mobile_html = await page2.content()
                    await ctx2.close()

                    if mobile_html and len(mobile_html.strip()) > len(html.strip()):
                        return mobile_html
        except Exception:
            # If anything goes wrong in fallback, return original html
            pass

        return html

async def _simulate_human_behavior(page):
    """Simulate sophisticated human-like behavior to avoid detection"""
    import random
    import asyncio
    
    try:
        # Wait for page to be fully loaded with longer timeout
        await page.wait_for_load_state("networkidle", timeout=10000)
        
        # Initial reading pause - humans don't immediately interact
        await page.wait_for_timeout(random.randint(2000, 4000))
        
        # Simulate realistic mouse movements with bezier-like curves
        for _ in range(random.randint(5, 10)):
            start_x = random.randint(100, 1800)
            start_y = random.randint(100, 1000)
            end_x = random.randint(100, 1800)
            end_y = random.randint(100, 1000)
            
            # Move mouse in realistic steps with slight curves
            steps = random.randint(8, 20)
            for i in range(steps):
                progress = i / steps
                # Add slight curve to movement
                curve_offset = random.randint(-50, 50) * (progress * (1 - progress))
                x = start_x + (end_x - start_x) * progress + curve_offset
                y = start_y + (end_y - start_y) * progress + curve_offset
                await page.mouse.move(x, y)
                await page.wait_for_timeout(random.randint(30, 120))
        
        # Simulate reading behavior with realistic scroll patterns
        await page.wait_for_timeout(random.randint(1000, 2000))
        
        # Gradual scroll down with pauses (like reading)
        for _ in range(random.randint(5, 12)):
            scroll_amount = random.randint(80, 250)
            await page.evaluate(f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}})")
            # Pause to simulate reading
            await page.wait_for_timeout(random.randint(1200, 2500))
        
        # Scroll back up a bit (like re-reading or checking something)
        await page.evaluate("window.scrollBy({top: -300, behavior: 'smooth'})")
        await page.wait_for_timeout(random.randint(800, 1500))
        
        # More scrolling down
        for _ in range(random.randint(2, 5)):
            scroll_amount = random.randint(100, 200)
            await page.evaluate(f"window.scrollBy({{top: {scroll_amount}, behavior: 'smooth'}})")
            await page.wait_for_timeout(random.randint(1000, 2000))
        
        # Random clicks on safe areas (like focusing on content)
        try:
            # Click on a non-interactive area
            await page.click("body", timeout=2000)
            await page.wait_for_timeout(random.randint(300, 800))
        except:
            pass
        
        # Simulate keyboard activity (like using tab navigation)
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(random.randint(200, 500))
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(random.randint(200, 500))
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(random.randint(200, 500))
        
        # Random focus changes
        try:
            await page.evaluate("document.activeElement.blur()")
            await page.wait_for_timeout(random.randint(200, 500))
        except:
            pass
        
        # Simulate mouse hover over elements
        try:
            # Hover over some common elements
            elements = await page.query_selector_all("a, button, input")
            if elements:
                element = random.choice(elements[:5])  # Only first 5 to avoid errors
                await element.hover()
                await page.wait_for_timeout(random.randint(500, 1000))
        except:
            pass
        
        # Final reading pause
        await page.wait_for_timeout(random.randint(2000, 4000))
        
        # Simulate closing behavior - scroll to top
        await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        await page.wait_for_timeout(random.randint(1000, 2000))
        
    except Exception as e:
        # If simulation fails, just continue
        print(f"Human behavior simulation failed: {e}")
        pass
