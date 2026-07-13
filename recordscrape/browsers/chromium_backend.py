"""
Launches stock Playwright Chromium, the plain backend with no stealth patches.
Must not know about the recorder, the runner or other backends.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext, async_playwright

from recordscrape.browsers.browser_config import BrowserConfig


@asynccontextmanager
async def open_chromium_context(browser_config: BrowserConfig) -> AsyncIterator[BrowserContext]:
    async with async_playwright() as playwright_driver:
        browser = await playwright_driver.chromium.launch(headless=browser_config.headless)
        try:
            yield await browser.new_context()
        finally:
            await browser.close()
