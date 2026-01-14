"""
Browser automation controller using Playwright.

This module provides a high-level interface for browser automation,
abstracting Playwright's API for easier use in video recording workflows.
"""

from typing import Optional, List, Literal
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
import logging

logger = logging.getLogger(__name__)


class BrowserController:
    """
    High-level browser automation controller.

    Manages browser lifecycle and provides methods for navigation,
    element interaction, and page manipulation.
    """

    def __init__(
        self,
        headless: bool = False,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        timeout: int = 30000,
        browser_type: Literal["chromium", "firefox", "webkit"] = "chromium",
    ):
        """
        Initialize the browser controller.

        Args:
            headless: Whether to run browser in headless mode
            viewport_width: Browser viewport width in pixels
            viewport_height: Browser viewport height in pixels
            timeout: Default timeout for operations in milliseconds
            browser_type: Browser engine to use
        """
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.timeout = timeout
        self.browser_type = browser_type

        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

        logger.info(
            f"BrowserController initialized: {browser_type}, "
            f"headless={headless}, viewport={viewport_width}x{viewport_height}"
        )

    def launch(self) -> None:
        """Launch the browser and create a new page."""
        if self._browser is not None:
            logger.warning("Browser already launched")
            return

        logger.info(f"Launching {self.browser_type} browser...")
        self._playwright = sync_playwright().start()

        # Get the appropriate browser
        if self.browser_type == "chromium":
            browser_engine = self._playwright.chromium
        elif self.browser_type == "firefox":
            browser_engine = self._playwright.firefox
        elif self.browser_type == "webkit":
            browser_engine = self._playwright.webkit
        else:
            raise ValueError(f"Unknown browser type: {self.browser_type}")

        self._browser = browser_engine.launch(headless=self.headless)
        self._context = self._browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height}
        )
        self._page = self._context.new_page()
        self._page.set_default_timeout(self.timeout)

        logger.info("Browser launched successfully")

    def close(self) -> None:
        """Close the browser and clean up resources."""
        if self._browser is None:
            logger.warning("Browser not launched, nothing to close")
            return

        logger.info("Closing browser...")
        if self._page:
            self._page.close()
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

        logger.info("Browser closed successfully")

    def __enter__(self):
        """Context manager entry."""
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    @property
    def page(self) -> Page:
        """Get the current page object."""
        if self._page is None:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return self._page

    # Navigation methods

    def navigate_to(
        self,
        url: str,
        wait_until: Literal[
            "load", "domcontentloaded", "networkidle", "commit"
        ] = "networkidle",
    ) -> None:
        """
        Navigate to a URL.

        Args:
            url: The URL to navigate to
            wait_until: When to consider navigation succeeded
        """
        logger.info(f"Navigating to: {url} (wait_until={wait_until})")
        self.page.goto(url, wait_until=wait_until)
        logger.info(f"Navigation complete: {url}")

    def wait_for_load_state(
        self, state: Literal["load", "domcontentloaded", "networkidle"] = "load"
    ) -> None:
        """
        Wait for a specific load state.

        Args:
            state: The load state to wait for
        """
        logger.debug(f"Waiting for load state: {state}")
        self.page.wait_for_load_state(state)

    def wait_for_timeout(self, milliseconds: int) -> None:
        """
        Wait for a specific amount of time.

        Args:
            milliseconds: Time to wait in milliseconds
        """
        logger.debug(f"Waiting for {milliseconds}ms")
        self.page.wait_for_timeout(milliseconds)

    # Element interaction methods

    def click(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Click an element.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in milliseconds
        """
        logger.info(f"Clicking element: {selector}")
        self.page.click(selector, timeout=timeout or self.timeout)
        logger.debug(f"Click successful: {selector}")

    def fill(self, selector: str, text: str, timeout: Optional[int] = None) -> None:
        """
        Fill an input field.

        Args:
            selector: CSS selector for the input element
            text: Text to fill
            timeout: Optional timeout override in milliseconds
        """
        logger.info(f"Filling element: {selector} with text: {text[:50]}...")
        self.page.fill(selector, text, timeout=timeout or self.timeout)
        logger.debug(f"Fill successful: {selector}")

    def select_option(
        self, selector: str, value: str, timeout: Optional[int] = None
    ) -> None:
        """
        Select an option from a dropdown.

        Args:
            selector: CSS selector for the select element
            value: Value to select
            timeout: Optional timeout override in milliseconds
        """
        logger.info(f"Selecting option: {value} in {selector}")
        self.page.select_option(selector, value, timeout=timeout or self.timeout)
        logger.debug(f"Select successful: {selector}")

    def check(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Check a checkbox or radio button.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in milliseconds
        """
        logger.info(f"Checking element: {selector}")
        self.page.check(selector, timeout=timeout or self.timeout)
        logger.debug(f"Check successful: {selector}")

    def uncheck(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Uncheck a checkbox.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in milliseconds
        """
        logger.info(f"Unchecking element: {selector}")
        self.page.uncheck(selector, timeout=timeout or self.timeout)
        logger.debug(f"Uncheck successful: {selector}")

    # Element query methods

    def find_element(self, selector: str, timeout: Optional[int] = None):
        """
        Find an element on the page.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in milliseconds

        Returns:
            ElementHandle for the found element
        """
        logger.debug(f"Finding element: {selector}")
        return self.page.query_selector(selector)

    def find_elements(self, selector: str) -> List:
        """
        Find all elements matching a selector.

        Args:
            selector: CSS selector for the elements

        Returns:
            List of ElementHandles
        """
        logger.debug(f"Finding elements: {selector}")
        return self.page.query_selector_all(selector)

    def is_visible(self, selector: str, timeout: Optional[int] = None) -> bool:
        """
        Check if an element is visible.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in milliseconds

        Returns:
            True if element is visible, False otherwise
        """
        logger.debug(f"Checking visibility: {selector}")
        try:
            return self.page.is_visible(selector, timeout=timeout or self.timeout)
        except Exception:
            return False

    def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[int] = None,
        state: Literal["attached", "detached", "visible", "hidden"] = "visible",
    ) -> None:
        """
        Wait for a selector to match the specified state.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in milliseconds
            state: State to wait for
        """
        logger.debug(f"Waiting for selector: {selector} (state={state})")
        self.page.wait_for_selector(
            selector, timeout=timeout or self.timeout, state=state
        )

    def screenshot(self, path: str, full_page: bool = False) -> None:
        """
        Take a screenshot of the page.

        Args:
            path: Path to save the screenshot
            full_page: Whether to capture the full scrollable page
        """
        logger.info(f"Taking screenshot: {path} (full_page={full_page})")
        self.page.screenshot(path=path, full_page=full_page)
        logger.debug(f"Screenshot saved: {path}")

    def screenshot_element(self, selector: str, path: str) -> None:
        """
        Take a screenshot of a specific element.

        Args:
            selector: CSS selector for the element
            path: Path to save the screenshot
        """
        logger.info(f"Taking element screenshot: {selector} -> {path}")
        element = self.page.query_selector(selector)
        if element:
            element.screenshot(path=path)
            logger.debug(f"Element screenshot saved: {path}")
        else:
            raise ValueError(f"Element not found: {selector}")
