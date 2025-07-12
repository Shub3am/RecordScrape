"""
Example demonstrating basic browser automation usage.
"""

from vpr.automation.browser import BrowserController
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    """Demonstrate basic browser automation."""

    # Example 1: Using context manager (recommended)
    print("Example 1: Basic navigation with context manager")
    with BrowserController(headless=False) as browser:
        # Navigate to a website
        browser.navigate_to("https://example.com")

        # Wait for page to be fully loaded
        browser.wait_for_load_state("networkidle")

        # Take a screenshot
        browser.screenshot("example_screenshot.png")

        # Find and interact with elements
        if browser.is_visible("h1"):
            print("Found h1 element!")

        # Wait a bit to see the browser
        browser.wait_for_timeout(2000)

    print("\nExample 2: Form interaction")
    with BrowserController(headless=False) as browser:
        # Navigate to a form page (using a test form)
        browser.navigate_to("https://www.w3schools.com/html/html_forms.asp")

        # Wait for page load
        browser.wait_for_load_state("networkidle")

        # Find input fields and interact
        # Note: This is just an example, actual selectors may vary
        try:
            # Wait for form elements
            browser.wait_for_timeout(2000)

            # Take a screenshot
            browser.screenshot("form_example.png")

        except Exception as e:
            print(f"Error during form interaction: {e}")

    print("\nExample 3: Multiple page navigation")
    with BrowserController(
        headless=False, viewport_width=1280, viewport_height=720
    ) as browser:
        pages = [
            "https://example.com",
            "https://www.wikipedia.org",
            "https://github.com",
        ]

        for i, url in enumerate(pages):
            print(f"Navigating to: {url}")
            browser.navigate_to(url)
            browser.wait_for_load_state("networkidle")
            browser.screenshot(f"page_{i+1}.png")
            browser.wait_for_timeout(1000)

    print("\nExample 4: Manual launch and close")
    browser = BrowserController(headless=True)
    browser.launch()

    try:
        browser.navigate_to("https://example.com")
        browser.wait_for_load_state("networkidle")

        # Get all links on the page
        links = browser.find_elements("a")
        print(f"Found {len(links)} links on the page")

    finally:
        browser.close()

    print("\nAll examples completed!")


if __name__ == "__main__":
    main()
