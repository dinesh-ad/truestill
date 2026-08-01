"""`create_app` resolves its default catalog when it is called, not when it is imported.

**The defect.** `server.py` held `_DEFAULT_DB = default_catalog_path()` at module scope and used
it as `create_app`'s default argument - frozen twice over, since a default argument binds once at
def-time too. `app_paths.default_catalog_path` states the opposite contract in its own docstring:
resolved on every call, never cached in a module constant, because "an override set after import
must still be honoured, and a constant computed at import time is unpatchable by a test and
therefore un-isolatable". That is `(aae)`'s rule, and this file was the last place breaking it.

**Why the obvious test would not have worked, recorded so nobody rewrites it that way.** The
natural check is to set `TRUESTILL_DATA_DIR` after import and watch the app follow it. It does
not discriminate here: `default_catalog_path` prefers an existing `reports/catalog.sqlite`
whenever a working directory was deliberately chosen, and under pytest `sys.stdout` is not None,
so that branch wins and the env var is never consulted. The repo has such a file. A test written
that way would fail against the fix as readily as against the defect - and if the developer's
`reports/` were ever cleaned, it would start passing against both.

**So the property is tested directly instead:** patch the resolver and see whether calling
`create_app` consults it. Frozen, the patch cannot be seen - the value was taken at import. Per
call, it is. The patch targets `truestill_app.server.default_catalog_path`, the binding
`create_app` actually calls (`from truestill_core.app_paths import default_catalog_path`), which
is the aiming rule `test_patch_targets_stay_aimed.py` enforces - patching the core module would
not reach the name this file already bound.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from app_support import TOKEN
from starlette.testclient import TestClient
from truestill_app import server


def test_create_app_resolves_its_default_catalog_at_call_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resolver patched after import must reach a `create_app()` that names no catalog."""
    sentinel = tmp_path / "resolved-at-call-time.sqlite"
    monkeypatch.setattr(server, "default_catalog_path", lambda: sentinel)

    app = server.create_app(token=TOKEN)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        reported = client.get("/api/library/status").json()["catalog_path"]

    assert reported == str(sentinel), (
        "create_app used a catalog resolved before the patch, so the default is frozen at "
        "import - the exact shape (aae) forbids."
    )


def test_an_explicit_db_still_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cry-wolf half: the fix must not start ignoring a caller that names its own catalog.

    `__main__.py` passes `db` explicitly on every real launch, so a regression here would reach
    every user while the test above stayed green.
    """
    monkeypatch.setattr(server, "default_catalog_path", lambda: tmp_path / "never-used.sqlite")
    chosen = tmp_path / "chosen.sqlite"

    app = server.create_app(token=TOKEN, db=chosen)
    with TestClient(app, headers={"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}) as client:
        reported = client.get("/api/library/status").json()["catalog_path"]

    assert reported == str(chosen), "an explicitly named catalog was overridden by the default"
