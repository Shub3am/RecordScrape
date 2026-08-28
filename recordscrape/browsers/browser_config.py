"""
Describes which browser to launch and how, so callers pick a backend by value instead of by import.
Must not import a browser library; each backend reads this config on its own.
"""

from dataclasses import dataclass
from typing import Literal

from recordscrape.proxies import proxy_settings_from_url

BackendName = Literal["chromium", "patchright"]


@dataclass(frozen=True)
class BrowserConfig:
    backend: BackendName
    headless: bool = True
    # The URL as stored, ${ENV} references included; they expand on every launch.
    proxy: str | None = None

    def launch_proxy_settings(self) -> dict[str, str] | None:
        return proxy_settings_from_url(self.proxy) if self.proxy else None
