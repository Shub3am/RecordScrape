"""
Names the browser backends every backend test runs on: the two always installed, plus CloakBrowser
when its optional extra is. CI installs no extras, so it never downloads the CloakBrowser binary.
Recording needs exposed bindings, so it runs on the shorter list of backends that keep them.
Must not hold any test.
"""

import importlib.util

from recordscrape.browsers import BACKENDS_WITHOUT_BINDINGS

ALL_BACKENDS = ["chromium", "patchright"]
if importlib.util.find_spec("cloakbrowser"):
    ALL_BACKENDS.append("cloakbrowser")

RECORDING_BACKENDS = [
    backend for backend in ALL_BACKENDS if backend not in BACKENDS_WITHOUT_BINDINGS
]
