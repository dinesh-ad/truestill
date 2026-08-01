"""PyInstaller runtime hook: install the perceptual-algorithm shim before the app starts.

Passed to PyInstaller with ``--runtime-hook``. Runtime hooks execute inside the frozen process
before the entry point, which is the only moment that works: earlier does not exist, and later
means the app may already have taken a reference to `imagehash.phash`.

Kept to one call so there is nothing to get wrong here; the substance lives in the package
beside it, where it is unit-testable without freezing anything.
"""

from __future__ import annotations

from truestill_freeze import install

install()
