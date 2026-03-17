"""
Describes which browser to launch and how, so callers pick a backend by value instead of by import.
Must not import a browser library; each backend reads this config on its own.
"""

from dataclasses import dataclass
from typing import Literal

from recordscrape.proxies import proxy_settings_from_url

BackendName = Literal["chromium", "patchright", "cloakbrowser"]
BACKENDS_WITH_NATIVE_HUMANIZE = ("cloakbrowser",)
# CloakBrowser's binary drops expose_binding and expose_function on purpose, because anti-bot
# scripts detect the CDP binding they use (CloakBrowser#340). Page code cannot call back on it.
BACKENDS_WITHOUT_BINDINGS = ("cloakbrowser",)


@dataclass(frozen=True)
class BrowserConfig:
    backend: BackendName
    headless: bool = True
    # The URL as stored, ${ENV} references included; they expand on every launch.
    proxy: str | None = None
    humanize: bool = False

    def __post_init__(self):
        if self.humanize and self.backend not in BACKENDS_WITH_NATIVE_HUMANIZE:
            raise ValueError(
                f"Human-like input needs one of these backends: "
                f"{', '.join(BACKENDS_WITH_NATIVE_HUMANIZE)}"
            )

    def launch_proxy_settings(self) -> dict[str, str] | None:
        return proxy_settings_from_url(self.proxy) if self.proxy else None
