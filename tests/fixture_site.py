"""
Serves in-memory HTML pages over local HTTP so browser tests never need the internet.
Must not hold any test's pages; each test module passes its own.
"""

import contextlib
import http.server
import threading
from collections.abc import Iterator


@contextlib.contextmanager
def serve_fixture_pages(fixture_pages: dict[str, str]) -> Iterator[str]:
    """Yields the site's base URL. Each key is a path and each value is the HTML inside <html>."""

    class FixturePageHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path not in fixture_pages:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(f"<!doctype html><html>{fixture_pages[self.path]}</html>".encode())

    fixture_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FixturePageHandler)
    threading.Thread(target=fixture_server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{fixture_server.server_address[1]}"
    finally:
        fixture_server.shutdown()
        fixture_server.server_close()
