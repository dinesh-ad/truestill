"""Shared fixtures for the app's HTTP tests (audit F28).

Nine test modules each declared their own ``_TOKEN`` and an identical ``client`` fixture. The
copies had already drifted - two omitted the ``x-truestill-token`` header and leaned on the
query-parameter fallback instead - which is the failure mode a copied fixture always has: the
divergence is invisible until a test depends on it.

``TOKEN`` lives in ``app_support.py``, not here. It is a value tests **import**, and a conftest
is not an importable module - see ``test_shared_test_helpers.py``. This file holds only what
pytest injects by name.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from app_support import TOKEN
from starlette.testclient import TestClient
from truestill_app.server import create_app


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """The catalog the ``client`` fixture serves.

    A fixture rather than a repeated literal: the two used to be kept in step by writing
    ``tmp_path / "c.sqlite"`` in both places and hoping.
    """
    return tmp_path / "c.sqlite"


@pytest.fixture
def client(db_path: Path) -> Iterator[TestClient]:
    """A TestClient with the token header set, over an app on ``db_path``."""
    app = create_app(token=TOKEN, db=db_path)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as c:
        yield c
