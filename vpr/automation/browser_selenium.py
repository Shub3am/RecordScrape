"""
Browser automation controller using Selenium.

This module provides a high-level interface for browser automation,
using Selenium WebDriver for better multi-threading support.
"""

from typing import Optional, List, Literal
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.safari.service import Service as SafariService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
import logging

logger = logging.getLogger(__name__)


class BrowserController:
    """
    High-level browser automation controller using Selenium.

    Manages browser lifecycle and provides methods for navigation,
    element interaction, and page manipulation.
    """

    def __init__(
        self,
        headless: bool = False,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        timeout: int = 30,
        browser_type: Literal["chromium", "firefox", "webkit"] = "chromium",
    ):
        """
        Initialize the browser controller.

        Args:
            headless: Whether to run browser in headless mode
            viewport_width: Browser viewport width in pixels
            viewport_height: Browser viewport height in pixels
            timeout: Default timeout for operations in seconds
            browser_type: Browser engine to use
        """
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.timeout = timeout
        self.browser_type = browser_type

        self._driver: Optional[webdriver.Remote] = None

        logger.info(
            f"BrowserController initialized: {browser_type}, "
            f"headless={headless}, viewport={viewport_width}x{viewport_height}"
        )

    def launch(self) -> None:
        """Launch the browser and create a new session."""
        if self._driver is not None:
            logger.warning("Browser already launched")
            return

        logger.info(f"Launching {self.browser_type} browser...")

        try:
            if self.browser_type == "chromium":
                options = webdriver.ChromeOptions()
                if self.headless:
                    options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument(
                    f"--window-size={self.viewport_width},{self.viewport_height}"
                )

                service = ChromeService(ChromeDriverManager().install())
                self._driver = webdriver.Chrome(service=service, options=options)

            elif self.browser_type == "firefox":
                options = webdriver.FirefoxOptions()
                if self.headless:
                    options.add_argument("--headless")

                service = FirefoxService(GeckoDriverManager().install())
                self._driver = webdriver.Firefox(service=service, options=options)
                self._driver.set_window_size(self.viewport_width, self.viewport_height)

            elif self.browser_type == "webkit":
                # Use Safari on macOS
                options = webdriver.SafariOptions()
                self._driver = webdriver.Safari(options=options)
                self._driver.set_window_size(self.viewport_width, self.viewport_height)

            else:
                raise ValueError(f"Unknown browser type: {self.browser_type}")

            self._driver.implicitly_wait(self.timeout)
            logger.info("Browser launched successfully")

        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise

    def close(self) -> None:
        """Close the browser and clean up resources."""
        if self._driver is None:
            logger.warning("Browser not launched, nothing to close")
            return

        logger.info("Closing browser...")
        try:
            self._driver.quit()
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
        finally:
            self._driver = None
            logger.info("Browser closed successfully")

    def __enter__(self):
        """Context manager entry."""
        self.launch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    @property
    def driver(self):
        """Get the current driver object."""
        if self._driver is None:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return self._driver

    # Navigation methods

    def navigate_to(self, url: str, wait_until: str = "complete") -> None:
        """
        Navigate to a URL.

        Args:
            url: The URL to navigate to
            wait_until: Ignored for Selenium (kept for API compatibility)
        """
        logger.info(f"Navigating to: {url}")
        self.driver.get(url)
        logger.info(f"Navigation complete: {url}")

    def wait_for_load_state(self, state: str = "complete") -> None:
        """
        Wait for page load state.

        Args:
            state: Ignored for Selenium (kept for API compatibility)
        """
        logger.debug("Waiting for page load...")
        WebDriverWait(self.driver, self.timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

    def wait_for_timeout(self, milliseconds: int) -> None:
        """
        Wait for a specific amount of time.

        Args:
            milliseconds: Time to wait in milliseconds
        """
        import time

        logger.debug(f"Waiting for {milliseconds}ms")
        time.sleep(milliseconds / 1000.0)

    # Element interaction methods

    def click(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Click an element.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in seconds
        """
        logger.info(f"Clicking element: {selector}")
        wait_time = timeout or self.timeout
        element = WebDriverWait(self.driver, wait_time).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        element.click()
        logger.debug(f"Click successful: {selector}")

    def fill(self, selector: str, text: str, timeout: Optional[int] = None) -> None:
        """
        Fill an input field.

        Args:
            selector: CSS selector for the input element
            text: Text to fill
            timeout: Optional timeout override in seconds
        """
        logger.info(f"Filling element: {selector} with text: {text[:50]}...")
        wait_time = timeout or self.timeout
        element = WebDriverWait(self.driver, wait_time).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        element.clear()
        element.send_keys(text)
        logger.debug(f"Fill successful: {selector}")

    def select_option(
        self, selector: str, value: str, timeout: Optional[int] = None
    ) -> None:
        """
        Select an option from a dropdown.

        Args:
            selector: CSS selector for the select element
            value: Value to select
            timeout: Optional timeout override in seconds
        """
        from selenium.webdriver.support.ui import Select

        logger.info(f"Selecting option: {value} in {selector}")
        wait_time = timeout or self.timeout
        element = WebDriverWait(self.driver, wait_time).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        select = Select(element)
        select.select_by_value(value)
        logger.debug(f"Select successful: {selector}")

    def check(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Check a checkbox or radio button.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in seconds
        """
        logger.info(f"Checking element: {selector}")
        wait_time = timeout or self.timeout
        element = WebDriverWait(self.driver, wait_time).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        if not element.is_selected():
            element.click()
        logger.debug(f"Check successful: {selector}")

    def uncheck(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Uncheck a checkbox.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in seconds
        """
        logger.info(f"Unchecking element: {selector}")
        wait_time = timeout or self.timeout
        element = WebDriverWait(self.driver, wait_time).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        if element.is_selected():
            element.click()
        logger.debug(f"Uncheck successful: {selector}")

    # Element query methods

    def find_element(self, selector: str, timeout: Optional[int] = None):
        """
        Find an element on the page.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in seconds

        Returns:
            WebElement for the found element or None
        """
        logger.debug(f"Finding element: {selector}")
        try:
            return self.driver.find_element(By.CSS_SELECTOR, selector)
        except:
            return None

    def find_elements(self, selector: str) -> List:
        """
        Find all elements matching a selector.

        Args:
            selector: CSS selector for the elements

        Returns:
            List of WebElements
        """
        logger.debug(f"Finding elements: {selector}")
        return self.driver.find_elements(By.CSS_SELECTOR, selector)

    def is_visible(self, selector: str, timeout: Optional[int] = None) -> bool:
        """
        Check if an element is visible.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in seconds

        Returns:
            True if element is visible, False otherwise
        """
        logger.debug(f"Checking visibility: {selector}")
        try:
            wait_time = timeout or self.timeout
            WebDriverWait(self.driver, wait_time).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
            )
            return True
        except:
            return False

    def wait_for_selector(
        self, selector: str, timeout: Optional[int] = None, state: str = "visible"
    ) -> None:
        """
        Wait for a selector to match the specified state.

        Args:
            selector: CSS selector for the element
            timeout: Optional timeout override in seconds
            state: State to wait for (visible, present, clickable)
        """
        logger.debug(f"Waiting for selector: {selector} (state={state})")
        wait_time = timeout or self.timeout

        if state == "visible":
            WebDriverWait(self.driver, wait_time).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
            )
        elif state == "clickable":
            WebDriverWait(self.driver, wait_time).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
        else:  # present/attached
            WebDriverWait(self.driver, wait_time).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )

    def screenshot(self, path: str, full_page: bool = False) -> None:
        """
        Take a screenshot of the page.

        Args:
            path: Path to save the screenshot
            full_page: Whether to capture the full scrollable page
        """
        logger.info(f"Taking screenshot: {path} (full_page={full_page})")
        if full_page:
            # Get full page height
            total_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            self.driver.set_window_size(self.viewport_width, total_height)

        self.driver.save_screenshot(path)

        if full_page:
            # Restore original size
            self.driver.set_window_size(self.viewport_width, self.viewport_height)

        logger.debug(f"Screenshot saved: {path}")

    def screenshot_element(self, selector: str, path: str) -> None:
        """
        Take a screenshot of a specific element.

        Args:
            selector: CSS selector for the element
            path: Path to save the screenshot
        """
        logger.info(f"Taking element screenshot: {selector} -> {path}")
        element = self.find_element(selector)
        if element:
            element.screenshot(path)
            logger.debug(f"Element screenshot saved: {path}")
        else:
            raise ValueError(f"Element not found: {selector}")

    @property
    def page(self):
        """Compatibility property for Playwright-style API."""
        return self

    @property
    def url(self):
        """Get current URL."""
        return self.driver.current_url
