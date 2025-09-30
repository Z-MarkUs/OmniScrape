import asyncio, contextlib, os
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

RENDER_MS = int(os.getenv("MAX_RENDER_MS", "15000"))

@contextlib.asynccontextmanager
async def _browser():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            yield browser
        finally:
            await browser.close()

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=1, max=4))
async def fetch_rendered(url: str, user_agent: str | None = None) -> str:
    async with _browser() as browser:
        ctx = await browser.new_context(user_agent=user_agent)
        page = await ctx.new_page()
        await page.route("**/*", lambda route: route.continue_())  # hook if you want to block ads/analytics
        await page.goto(url, wait_until="networkidle", timeout=RENDER_MS)
        html = await page.content()
        await ctx.close()
        return html
