import random
import logging
from typing import Optional, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


class PlaywrightBrowser:
    def __init__(self):
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    async def setup(self):
        """Initialize browser with anti-detection settings."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=self._get_random_user_agent(),
            locale='en-US'
        )

    def _get_random_user_agent(self) -> str:
        """Generate random user agent from predefined list."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        return random.choice(user_agents)

    async def close(self):
        """Cleanup resources."""
        if self.page: await self.page.close()
        if self.context: await self.context.close()
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

    async def new_page(self) -> Page:
        """Open a new browser page in the current context."""
        self.page = await self.context.new_page()
        return self.page

    async def extract_text(self, selector: str, parent: Optional[Any] = None) -> Optional[str]:
        """Safe text extraction from selector."""
        try:
            element = await parent.query_selector(selector) if parent else await self.page.query_selector(selector)
            return (await element.text_content()).strip() if element else None
        except Exception as e:
            logging.error(f"Error extracting text: {e}")
            return None

    async def extract_number(self, selector: str, parent: Optional[Any] = None) -> Optional[float]:
        """Safe number extraction from selector."""
        try:
            text = await self.extract_text(selector, parent)
            if text:
                cleaned = ''.join(c for c in text if c.isdigit() or c in '.-')
                return float(cleaned) if cleaned else None
            return None
        except Exception as e:
            logging.error(f"Error extracting number: {e}")
            return None

    async def auto_scroll(self, delay: float = 0.1, step: int = 300, max_scrolls: int = 50):
        """Scrolls page down to force loading of all dynamic content."""
        for _ in range(max_scrolls):
            await self.page.mouse.wheel(0, step)
            await self.page.wait_for_timeout(int(delay * 100))
