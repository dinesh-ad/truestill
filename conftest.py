"""Session-wide isolation for the OS-conventional data and cache directories.

Without this, `app_paths.default_catalog_path` resolves into the **developer's real home**, so
any test that runs a default-``--db`` command writes a catalog there. That is not hypothetical:
when `(aae)` first landed, both CI runners and a local run each created a real
``catalog.sqlite`` under the user's data directory before anyone noticed.

Set once for the whole session, before any test imports a surface that reads them.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from truestill_core.app_paths import CACHE_DIR_ENV, DATA_DIR_ENV


@pytest.fixture(scope="session", autouse=True)
def _isolate_app_dirs() -> Iterator[None]:
    with tempfile.TemporaryDirectory(prefix="truestill-test-home-") as home:
        # resolve() matters on Windows: GitHub's runners hand out TEMP in 8.3 short form
        # (C:\Users\RUNNER~1\...), and anything that resolves the path for display gets the long
        # form (C:\Users\runneradmin\...), so the two never compare equal. Known pytest issue
        # #11895. resolve() expands the short name, so the roots are canonical from the start.
        root = Path(home).resolve()
        previous = {key: os.environ.get(key) for key in (DATA_DIR_ENV, CACHE_DIR_ENV)}
        os.environ[DATA_DIR_ENV] = str(root / "data")
        os.environ[CACHE_DIR_ENV] = str(root / "cache")
        try:
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
