"""
Launches CloakBrowser, a patched Chromium binary driven through stock Playwright, with its own
fingerprint patches and optional human-like mouse and keyboard input.
Must not know about the recorder, the runner or other backends, and must not be imported by
anything but the launcher, because the library is an optional extra.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from playwright.async_api import BrowserContext

from recordscrape.browsers.browser_config import BrowserConfig

MISSING_EXTRA_MESSAGE = (
    "The cloakbrowser backend is not installed. Run: uv sync --extra cloakbrowser, "
    "then: uv run python -m cloakbrowser install"
)


@asynccontextmanager
async def open_cloakbrowser_context(browser_config: BrowserConfig) -> AsyncIterator[BrowserContext]:
    # Imported here so the other backends work without the optional extra installed.
    try:
        from cloakbrowser import launch_async
    except ModuleNotFoundError as missing_extra:
        raise ValueError(MISSING_EXTRA_MESSAGE) from missing_extra

    # launch_async downloads the ~200MB binary on first use if `cloakbrowser install` never ran,
    # and reads CLOAKBROWSER_LICENSE_KEY itself. Its patched close() also stops the driver.
    browser = await launch_async(
        headless=browser_config.headless,
        proxy=browser_config.launch_proxy_settings(),
        humanize=browser_config.humanize,
    )
    try:
        yield await browser.new_context()
    finally:
        await browser.close()
