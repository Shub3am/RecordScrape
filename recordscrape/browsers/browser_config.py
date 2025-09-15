"""
Describes which browser to launch and how, so callers pick a backend by value instead of by import.
Must not import a browser library; each backend reads this config on its own.
"""

from dataclasses import dataclass
from typing import Literal

BackendName = Literal["chromium", "patchright"]


@dataclass(frozen=True)
class BrowserConfig:
    backend: BackendName
    headless: bool = True
