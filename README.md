# Video Product Recording Tool

An automated tool for creating product demonstration videos using browser automation, screen recording, and text-to-speech.

## 🚀 Quick Start

### Setup

1. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install flask flask-cors
   ```

3. Install Playwright browsers:
   ```bash
   playwright install
   ```

## 🎨 Web UI

Launch the visual web interface:

```bash
source .venv/bin/activate
python run_ui.py
```

Then open http://localhost:5000 in your browser.

### Features:
- 🌐 Browser control (Chromium, Firefox, WebKit)
- 🎯 Navigate to URLs
- 👆 Click elements
- ✍️ Fill forms
- 📸 Take screenshots
- 📊 Real-time activity logging

## 🧪 Testing

Run the test suite:

```bash
pytest tests/test_browser.py -v
```

## 💻 Programmatic Usage

```python
from vpr.automation.browser import BrowserController

with BrowserController(headless=False) as browser:
    browser.navigate_to("https://example.com")
    browser.screenshot("example.png")
```

## 📚 Examples

See `examples/basic_browser_usage.py` for more examples.

## Development

- Run tests: `pytest`
- Format code: `black vpr/`
- Lint code: `flake8 vpr/`
