"""
Opens a browser context for whichever backend a BrowserConfig names.
Must not contain launch logic of its own; each backend file owns how its library starts.
"""

from contextlib import AbstractAsyncContextManager

import patchright.async_api
import playwright.async_api

from recordscrape.browsers.browser_config import BrowserConfig
from recordscrape.browsers.chromium_backend import open_chromium_context
from recordscrape.browsers.patchright_backend import open_patchright_context

OpenedBrowserContext = playwright.async_api.BrowserContext | patchright.async_api.BrowserContext
# Each library raises its own Error class, so catching a browser failure must name both.
BROWSER_ERRORS = (playwright.async_api.Error, patchright.async_api.Error)

BACKEND_OPENERS = {
    "chromium": open_chromium_context,
    "patchright": open_patchright_context,
}


def open_browser_context(
    browser_config: BrowserConfig,
) -> AbstractAsyncContextManager[OpenedBrowserContext]:
    """Use as `async with open_browser_context(config) as context:`; leaving it closes the browser."""
    return BACKEND_OPENERS[browser_config.backend](browser_config)
