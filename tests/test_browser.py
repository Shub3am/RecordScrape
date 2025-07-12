"""
Unit tests for BrowserController.
"""

import pytest
from vpr.automation.browser import BrowserController


class TestBrowserController:
    """Test suite for BrowserController class."""

    def test_initialization(self):
        """Test browser controller initialization."""
        controller = BrowserController(
            headless=True, viewport_width=1280, viewport_height=720, timeout=10000
        )

        assert controller.headless is True
        assert controller.viewport_width == 1280
        assert controller.viewport_height == 720
        assert controller.timeout == 10000
        assert controller.browser_type == "chromium"

    def test_context_manager(self):
        """Test browser controller as context manager."""
        with BrowserController(headless=True) as controller:
            assert controller._browser is not None
            assert controller._page is not None

        # After context exit, browser should be closed
        assert controller._browser is None
        assert controller._page is None

    def test_launch_and_close(self):
        """Test manual browser launch and close."""
        controller = BrowserController(headless=True)

        # Initially not launched
        assert controller._browser is None

        # Launch
        controller.launch()
        assert controller._browser is not None
        assert controller._page is not None

        # Close
        controller.close()
        assert controller._browser is None
        assert controller._page is None

    def test_navigation(self):
        """Test basic navigation."""
        with BrowserController(headless=True) as controller:
            # Navigate to example.com
            controller.navigate_to("https://example.com")

            # Check that we're on the right page
            assert "example.com" in controller.page.url

    def test_element_interaction(self):
        """Test element interaction methods."""
        with BrowserController(headless=True) as controller:
            # Navigate to a test page
            controller.navigate_to("https://example.com")

            # Test finding elements
            h1_element = controller.find_element("h1")
            assert h1_element is not None

            # Test visibility check
            is_visible = controller.is_visible("h1")
            assert is_visible is True

    def test_screenshot(self, tmp_path):
        """Test screenshot functionality."""
        screenshot_path = tmp_path / "test_screenshot.png"

        with BrowserController(headless=True) as controller:
            controller.navigate_to("https://example.com")
            controller.screenshot(str(screenshot_path))

            # Check that screenshot was created
            assert screenshot_path.exists()
            assert screenshot_path.stat().st_size > 0

    def test_wait_for_selector(self):
        """Test waiting for selectors."""
        with BrowserController(headless=True) as controller:
            controller.navigate_to("https://example.com")

            # Wait for h1 to be visible
            controller.wait_for_selector("h1", state="visible")

            # Should not raise an exception
            assert controller.is_visible("h1")

    def test_multiple_browser_types(self):
        """Test different browser types."""
        for browser_type in ["chromium", "firefox", "webkit"]:
            with BrowserController(
                headless=True, browser_type=browser_type
            ) as controller:
                controller.navigate_to("https://example.com")
                assert "example.com" in controller.page.url


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
class TestBrowserControllerErrors:
    """Test error handling in BrowserController."""

    def test_page_access_before_launch(self):
        """Test accessing page before launch raises error."""
        controller = BrowserController(headless=True)

        with pytest.raises(RuntimeError, match="Browser not launched"):
            _ = controller.page

    def test_invalid_browser_type(self):
        """Test invalid browser type raises error."""
        controller = BrowserController(headless=True, browser_type="invalid")

        with pytest.raises(ValueError, match="Unknown browser type"):
            controller.launch()

