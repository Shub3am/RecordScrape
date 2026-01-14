"""
Web UI server for Video Product Recorder.
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import logging
from vpr.automation.browser_selenium import BrowserController

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global browser instance
browser_instance = None


@app.route("/")
def index():
    """Serve the main UI."""
    return render_template("index.html")


@app.route("/api/browser/launch", methods=["POST"])
def launch_browser():
    """Launch the browser."""
    global browser_instance

    data = request.json
    headless = data.get("headless", False)
    viewport_width = data.get("viewport_width", 1920)
    viewport_height = data.get("viewport_height", 1080)
    browser_type = data.get("browser_type", "chromium")

    try:
        if browser_instance is not None:
            return jsonify({"error": "Browser already running"}), 400

        browser_instance = BrowserController(
            headless=headless,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            browser_type=browser_type,
        )
        browser_instance.launch()

        return jsonify({"status": "success", "message": "Browser launched"})
    except Exception as e:
        logger.error(f"Error launching browser: {e}")
        browser_instance = None
        return jsonify({"error": str(e)}), 500


@app.route("/api/browser/close", methods=["POST"])
def close_browser():
    """Close the browser."""
    global browser_instance

    try:
        if browser_instance is None:
            return jsonify({"error": "No browser running"}), 400

        browser_instance.close()
        browser_instance = None

        return jsonify({"status": "success", "message": "Browser closed"})
    except Exception as e:
        logger.error(f"Error closing browser: {e}")
        browser_instance = None
        return jsonify({"error": str(e)}), 500


@app.route("/api/browser/navigate", methods=["POST"])
def navigate():
    """Navigate to a URL."""
    global browser_instance

    data = request.json
    url = data.get("url")
    wait_until = data.get("wait_until", "networkidle")

    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        if browser_instance is None:
            return jsonify({"error": "Browser not running"}), 400

        browser_instance.navigate_to(url, wait_until=wait_until)

        return jsonify({"status": "success", "message": f"Navigated to {url}"})
    except Exception as e:
        logger.error(f"Error navigating: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/browser/click", methods=["POST"])
def click():
    """Click an element."""
    global browser_instance

    data = request.json
    selector = data.get("selector")

    if not selector:
        return jsonify({"error": "Selector is required"}), 400

    try:
        if browser_instance is None:
            return jsonify({"error": "Browser not running"}), 400

        browser_instance.click(selector)

        return jsonify({"status": "success", "message": f"Clicked {selector}"})
    except Exception as e:
        logger.error(f"Error clicking: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/browser/fill", methods=["POST"])
def fill():
    """Fill an input field."""
    global browser_instance

    data = request.json
    selector = data.get("selector")
    text = data.get("text")

    if not selector or text is None:
        return jsonify({"error": "Selector and text are required"}), 400

    try:
        if browser_instance is None:
            return jsonify({"error": "Browser not running"}), 400

        browser_instance.fill(selector, text)

        return jsonify({"status": "success", "message": f"Filled {selector}"})
    except Exception as e:
        logger.error(f"Error filling: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/browser/screenshot", methods=["POST"])
def screenshot():
    """Take a screenshot."""
    global browser_instance

    data = request.json
    path = data.get("path", "screenshot.png")
    full_page = data.get("full_page", False)

    try:
        with browser_lock:
            if browser_instance is None:
                return jsonify({"error": "Browser not running"}), 400

            browser_instance.screenshot(path, full_page=full_page)

        return jsonify({"status": "success", "message": f"Screenshot saved to {path}"})
    except Exception as e:
        logger.error(f"Error taking screenshot: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/browser/status", methods=["GET"])
def status():
    """Get browser status."""
    global browser_instance

    is_running = browser_instance is not None

    return jsonify({"running": is_running})


if __name__ == "__main__":
    print("🚀 Starting VPR Web UI...")
    print("📱 Open http://localhost:5000 in your browser")
    app.run(debug=True, host="0.0.0.0", port=5000)
