"""
Gives browser tests local HTTP addresses to load, so they never need the internet.
Must not hold any test's pages; each test module passes its own.
"""

import contextlib
import http.server
import socket
import threading
from collections.abc import Iterator


def find_closed_local_port() -> int:
    """Returns a port nothing listens on. Chromium refuses some low ports outright, so 1 won't do."""
    with socket.socket() as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        return probe_socket.getsockname()[1]


@contextlib.contextmanager
def serve_handler_on_local_port(
    request_handler_class: type[http.server.BaseHTTPRequestHandler],
) -> Iterator[str]:
    """Yields the base URL of a server running the handler on a free loopback port."""
    local_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), request_handler_class)
    threading.Thread(target=local_server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{local_server.server_address[1]}"
    finally:
        local_server.shutdown()
        local_server.server_close()


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

    with serve_handler_on_local_port(FixturePageHandler) as fixture_site_url:
        yield fixture_site_url
