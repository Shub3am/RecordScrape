"""
Launches Patchright, the stealth Chromium backend, and makes its exposed bindings reachable from pages.
Must not know about the recorder, the runner or other backends, so page scripts learn that bindings
are ready from a DOM event rather than from a recorder-specific call.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from patchright.async_api import BrowserContext, Error, Page, async_playwright

from recordscrape.browsers.browser_config import BrowserConfig

BINDINGS_READY_EVENT = "recordscrape:bindings-ready"

ANNOUNCE_BINDINGS_READY_SCRIPT = f"() => window.dispatchEvent(new Event('{BINDINGS_READY_EVENT}'))"

HARMLESS_ANNOUNCE_ERROR_MESSAGES = (
    "Execution context was destroyed",
    "Target page, context or browser has been closed",
)


@asynccontextmanager
async def open_patchright_context(browser_config: BrowserConfig) -> AsyncIterator[BrowserContext]:
    async with async_playwright() as patchright_driver:
        browser = await patchright_driver.chromium.launch(headless=browser_config.headless)
        try:
            browser_context = await browser.new_context()
            browser_context.on("page", announce_bindings_on_every_document)
            yield browser_context
        finally:
            await browser.close()


async def announce_bindings_on_every_document(page: Page) -> None:
    page.on("domcontentloaded", announce_bindings_ready)
    # A popup can reach Patchright's "page" event after its first document has already loaded,
    # so domcontentloaded never fires for that document and it is announced here instead.
    await announce_bindings_ready(page)


async def announce_bindings_ready(page: Page) -> None:
    # Patchright hides exposed bindings from a document's main world until a main-world evaluate
    # has run on that document (patchright#207). Evaluating here installs them, and the event tells
    # page scripts that were loaded earlier by add_init_script that the bindings now exist.
    try:
        await page.evaluate(ANNOUNCE_BINDINGS_READY_SCRIPT, isolated_context=False)
    except Error as evaluate_error:
        # Two races leave nothing to announce. A navigation replaced the document mid-evaluate,
        # typically a new tab's about:blank being replaced by its first goto, and the new document
        # is announced on its own domcontentloaded. Or the browser closed mid-evaluate, as when a
        # caller leaves the context right after a failed goto. Patchright exports no error type for
        # either, so the message is the only signal.
        if not any(
            harmless_message in evaluate_error.message
            for harmless_message in HARMLESS_ANNOUNCE_ERROR_MESSAGES
        ):
            raise
