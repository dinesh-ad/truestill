"""A 0-byte file at the catalog path stops the app instead of becoming an empty library. `(adr)`

**Why refusing costs a first-run user nothing.** A new user has no file; this user has a file of
zero bytes, which means something wrote there and failed. `WILL_CREATE` is `is_file()` being
false, so the two states are disjoint at the branch and no first-run path changes.

**Why the app is the surface that matters most.** `create_app` calls `prepare_catalog`, whose
`migrate_catalog` builds the schema into whatever file it is given - so on this path the evidence
is destroyed by starting up, before any user has a chance to see the file was empty. The
launcher's refusal and `prepare_catalog`'s are both asserted: the launcher is the one a person
meets, and `prepare_catalog` is the hazard site that a second entry point could reach around.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from truestill_app import __main__ as app_main
from truestill_app import service
from truestill_core.catalog_startup import CATALOG_UNUSABLE_EXIT, CatalogUnusableError


def test_the_launcher_refuses_before_it_binds_a_socket(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No socket, no URL file, no browser - nothing claims an address that was never served.

    Asserting the exit code alone would pass with the check placed after the bind, which would
    leave a listener and a session-url file behind for a process that then quits.
    """
    db = tmp_path / "catalog.sqlite"
    db.write_bytes(b"")
    bound: list[int] = []

    def _refuse_to_bind(preferred: int) -> None:
        # Recording is what the assertion below reads; raising here would only turn a clear
        # failure into a traceback from inside a monkeypatch.
        bound.append(preferred)

    monkeypatch.setattr(app_main, "bind_listening_socket", _refuse_to_bind)

    code = app_main.main(["--db", str(db), "--no-browser"])

    assert code == CATALOG_UNUSABLE_EXIT
    assert not bound
    assert db.stat().st_size == 0, "the launcher built a schema into the failed file"
    err = capsys.readouterr().err
    assert "0 bytes" in err, "the refusal must reach stderr, not stdout"


def test_prepare_catalog_refuses_rather_than_migrating_the_failed_file(tmp_path: Path) -> None:
    """THE HAZARD SITE. `migrate_catalog` is what turns 0 bytes into a valid empty catalog.

    Separate from the launcher test on purpose: this is the call that does the damage, and a
    future entry point that reaches `prepare_catalog` without going through the launcher must
    still be stopped here.
    """
    db = tmp_path / "catalog.sqlite"
    db.write_bytes(b"")

    with pytest.raises(CatalogUnusableError):
        service.prepare_catalog(db, explicit_db=True)

    assert db.stat().st_size == 0


def test_a_first_run_still_starts_and_still_says_will_create(tmp_path: Path) -> None:
    """The other direction, because a refusal that catches first runs is worse than the defect."""
    db = tmp_path / "catalog.sqlite"

    info: Any = service.prepare_catalog(db, explicit_db=True)

    assert info.presence.value == "will_create"
    assert db.is_file(), "prepare_catalog must still create and migrate a genuine first run"
