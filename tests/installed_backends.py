"""
Names the browser backends every backend test runs on: the two always installed, plus CloakBrowser
when its optional extra is. CI installs no extras, so it never downloads the CloakBrowser binary.
Recording needs exposed bindings, so it runs on the shorter list of backends that keep them.
Must not hold any test.
"""

import importlib.util
from typing import get_args

from recordscrape.browsers import BACKENDS_WITHOUT_BINDINGS, BackendName

OPTIONAL_BACKENDS = ("cloakbrowser",)

ALL_BACKENDS = [
    backend
    for backend in get_args(BackendName)
    if backend not in OPTIONAL_BACKENDS or importlib.util.find_spec(backend)
]

RECORDING_BACKENDS = [
    backend for backend in ALL_BACKENDS if backend not in BACKENDS_WITHOUT_BINDINGS
]
