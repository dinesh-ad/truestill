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

import pytest
from truestill_core.app_paths import CACHE_DIR_ENV, DATA_DIR_ENV


@pytest.fixture(scope="session", autouse=True)
def _isolate_app_dirs() -> Iterator[None]:
    with tempfile.TemporaryDirectory(prefix="truestill-test-home-") as home:
        previous = {key: os.environ.get(key) for key in (DATA_DIR_ENV, CACHE_DIR_ENV)}
        os.environ[DATA_DIR_ENV] = f"{home}/data"
        os.environ[CACHE_DIR_ENV] = f"{home}/cache"
        try:
            yield
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
