"""
Turns the proxy URL a session stores into the proxy settings Playwright's launch call takes, so a
secret can live in an environment variable instead of in the database or a flow file.
Must not import a browser library or know which backend will use the settings.
"""

import os
import re
from urllib.parse import unquote, urlsplit

ENV_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
SUPPORTED_SCHEMES = ("http", "https", "socks5")


def expand_env_references(proxy_url: str) -> str:
    """Replaces each ${NAME} with that environment variable, refusing a name that is not set."""

    def env_value(reference_match: re.Match) -> str:
        env_name = reference_match.group(1)
        referenced_value = os.environ.get(env_name)
        if referenced_value is None:
            raise ValueError(
                f"Proxy URL needs the environment variable {env_name}, which is not set"
            )
        return referenced_value

    return ENV_REFERENCE.sub(env_value, proxy_url)


def proxy_settings_from_url(proxy_url: str) -> dict[str, str]:
    """Returns {server, username?, password?}. Credentials with reserved characters such as @ or :
    must be percent-encoded, in the URL or in the environment variable, as in any URL."""
    split_url = urlsplit(expand_env_references(proxy_url))
    if split_url.scheme not in SUPPORTED_SCHEMES:
        raise ValueError(f"Proxy URL must start with one of: {', '.join(SUPPORTED_SCHEMES)}://")
    if not split_url.hostname:
        raise ValueError("Proxy URL has no host")
    # Playwright only sends credentials to HTTP proxies (playwright#10567), and CloakBrowser falls
    # back to a direct connection when SOCKS5 auth fails (CloakBrowser#157), which leaks the real IP.
    if split_url.scheme == "socks5" and split_url.username:
        raise ValueError("SOCKS5 proxies with a username and password are not supported")

    host_and_port = split_url.netloc.rpartition("@")[2]
    proxy_settings = {"server": f"{split_url.scheme}://{host_and_port}"}
    if split_url.username:
        proxy_settings["username"] = unquote(split_url.username)
        proxy_settings["password"] = unquote(split_url.password or "")
    return proxy_settings
