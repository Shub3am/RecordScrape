"""
Reads where the dashboard server listens, where it keeps its database and the token its API
requires, from the environment, refusing a server reachable from other machines without a token.
Must not import Flask or the server, and must not read anything but the environment it is given.
"""

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001
DEFAULT_DATA_DIR = "."


@dataclass(frozen=True)
class ServerSettings:
    host: str
    port: int
    data_dir: str
    # None means the API is open, which is only allowed on a loopback host.
    api_token: str | None


def is_loopback_host(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def server_settings_from_env(environ: Mapping[str, str]) -> ServerSettings:
    server_settings = ServerSettings(
        host=environ.get("RECORDSCRAPE_HOST", DEFAULT_HOST),
        port=int(environ.get("RECORDSCRAPE_PORT", DEFAULT_PORT)),
        data_dir=environ.get("RECORDSCRAPE_DATA_DIR", DEFAULT_DATA_DIR),
        api_token=environ.get("RECORDSCRAPE_TOKEN") or None,
    )
    if server_settings.api_token is None and not is_loopback_host(server_settings.host):
        raise ValueError(
            f"RECORDSCRAPE_HOST={server_settings.host} lets other machines reach the API. "
            "Set RECORDSCRAPE_TOKEN to a long random secret, or listen on 127.0.0.1."
        )
    return server_settings
