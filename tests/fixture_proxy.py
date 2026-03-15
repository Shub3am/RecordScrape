"""
Gives browser tests a local HTTP proxy that demands credentials and serves made-up hosts from a
local site, so a page on such a host can only load if the browser really went through the proxy.
Must not hold any test's pages or know which backend is under test.
"""

import base64
import contextlib
import http.server
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# An opener with no proxy handler, so fetching the upstream site ignores any HTTP_PROXY of the host.
DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass
class FixtureProxy:
    url_without_credentials: str
    authenticated_urls: list[str] = field(default_factory=list)


@contextlib.contextmanager
def serve_authenticating_proxy(
    username: str, password: str, upstream_by_host: dict[str, str]
) -> Iterator[FixtureProxy]:
    """Yields the running proxy. A request for a host in upstream_by_host is served from that base
    URL once it carries the credentials; before that it gets a 407 challenge, as real proxies do."""
    expected_authorization = "Basic " + base64.b64encode(f"{username}:{password}".encode()).decode()
    fixture_proxy = FixtureProxy(url_without_credentials="")

    class AuthenticatingProxyHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.headers.get("Proxy-Authorization") != expected_authorization:
                self.send_response(407)
                self.send_header("Proxy-Authenticate", 'Basic realm="fixture"')
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            requested_url = urlsplit(self.path)
            if requested_url.hostname not in upstream_by_host:
                self.send_error(502)
                return
            fixture_proxy.authenticated_urls.append(self.path)
            upstream_url = upstream_by_host[requested_url.hostname] + requested_url.path
            try:
                upstream_response = DIRECT_OPENER.open(upstream_url)
            except urllib.error.HTTPError as upstream_error:
                upstream_response = upstream_error
            with upstream_response:
                response_body = upstream_response.read()
                self.send_response(upstream_response.status)
                self.send_header("Content-Type", upstream_response.headers["Content-Type"])
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)

    proxy_server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), AuthenticatingProxyHandler)
    fixture_proxy.url_without_credentials = f"http://127.0.0.1:{proxy_server.server_address[1]}"
    threading.Thread(target=proxy_server.serve_forever, daemon=True).start()
    try:
        yield fixture_proxy
    finally:
        proxy_server.shutdown()
        proxy_server.server_close()
