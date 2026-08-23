"""A busy catalog is a worded refusal on every route, never a raw 500. `(agp)` part 1.

⚠ **THE DEFECT, measured before this existed**: the settings routes had no handler at all, so a
busy settings write raised `sqlite3.OperationalError` into Starlette's default 500 and the
browser's fatal banner read *"Internal Server Error"* - SQLite's condition wearing Starlette's
prose, the exact class `(afe)` exists to keep off the screen. And it was a CLASS, not a route:
the census found **seven** direct-write service calls across four files with nothing catching
busy (`set_organize_mode`, `set_sidebar_collapsed`, `set_text_size`, `set_library_root`,
`set_layout`, `confirm_file_date`, the events family).

**So the fix is app-level** - `server.py` registers one exception handler, mirroring the CLI's
own top-level catch (`cli.py:4346`): one recognition per surface, at the top, and a new route
cannot be added outside it.

**And settings writes retry, bounded at 2** (`REQUEST_BUSY_ATTEMPTS`): each attempt already waits
the driver's 5 s `busy_timeout`, and the only measured multi-second holder is the
once-per-catalog fresh-schema build at <= 5.1 s (`(adt)` M4) - so the second attempt lands after
it, and genuine sustained contention still surfaces after ~10 s instead of hiding behind a
minute of silence.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Self

import anyio
import pytest
from starlette.testclient import TestClient
from truestill_app.server import _catalog_busy_refusal, create_app
from truestill_app.service import organize as organize_service
from truestill_core.catalog import Catalog
from truestill_core.catalog_busy import (
    CATALOG_BUSY_CODE,
    CATALOG_BUSY_REQUEST_MESSAGE,
    REQUEST_BUSY_ATTEMPTS,
)

TOKEN = "test-token"
_HEADERS = {"host": "127.0.0.1:7357", "x-truestill-token": TOKEN}


def _busy_error() -> sqlite3.OperationalError:
    """A fabricated busy, the shape `test_a_catalog_that_cannot_be_written_stops_the_run` uses."""
    exc = sqlite3.OperationalError("database is locked")
    exc.sqlite_errorcode = sqlite3.SQLITE_BUSY
    return exc


@pytest.fixture
def held_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Path, sqlite3.Connection]]:
    """A real catalog whose write lock a second connection holds, with fast timeouts.

    The holder is created FIRST, with its own explicit timeout, and then `sqlite3.connect` is
    wrapped so every later open (the service's `Catalog`) waits 0.15 s instead of the driver's
    5 s default - the same condition, at test speed. Real lock, real driver wait, no mocks in
    the decision path.
    """
    db = tmp_path / "catalog.sqlite"
    # Build the schema first so the service's open takes the (adu) fast path and it is the
    # WRITE that meets the held lock - the shape a user actually hits.
    Catalog(db).close()

    holder = sqlite3.connect(db, timeout=0.1)
    holder.execute("BEGIN IMMEDIATE")

    real_connect = sqlite3.connect

    def quick(*args: object, **kwargs: object) -> sqlite3.Connection:
        kwargs.setdefault("timeout", 0.15)
        return real_connect(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(sqlite3, "connect", quick)
    try:
        yield db, holder
    finally:
        holder.rollback()
        holder.close()


def test_a_busy_settings_write_is_a_worded_refusal_not_a_500(
    held_catalog: tuple[Path, sqlite3.Connection],
) -> None:
    """⚠ **THE HEADLINE, and it fails against yesterday's code** - which raised the
    `OperationalError` straight through this client."""
    db, _holder = held_catalog
    app = create_app(token=TOKEN, db=db)

    with TestClient(app, headers=_HEADERS) as client:
        response = client.post("/api/organize/settings", json={"mode": "move"})

    assert response.status_code == 503, f"a busy catalog answered {response.status_code}"
    payload = response.json()
    assert payload["code"] == CATALOG_BUSY_CODE
    assert "busy" in payload["error"]
    assert "try again" in payload["error"]
    assert response.headers.get("retry-after") == "5"
    assert "Internal Server Error" not in response.text


def test_the_refusal_does_not_assert_a_second_window() -> None:
    """⚠ **The whole of `(agp)`, held at this surface.** The reproduction showed the same
    "close the other Truestill window" sentence for a one-process first-run build and for a
    non-Truestill holder alike. Until detection exists, a window is one possibility among the
    three real causes - never an instruction to close something asserted to exist."""
    assert "close the other" not in CATALOG_BUSY_REQUEST_MESSAGE
    assert "stop the other" not in CATALOG_BUSY_REQUEST_MESSAGE
    assert "may be holding" in CATALOG_BUSY_REQUEST_MESSAGE, (
        "the possibility of another holder should be named as a possibility"
    )


def test_the_retry_rides_out_a_hold_that_clears(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bound's useful half: busy once - the fresh-build shape - then success.

    Fails against yesterday's code, where the first busy raised straight out of the setter.
    """
    calls = {"n": 0}

    class FakeCatalog:
        def set_setting(self, _key: str, _value: str) -> None:
            pass

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_a: object) -> None:
            return None

    def flaky_open(_db: Path) -> FakeCatalog:
        calls["n"] += 1
        if calls["n"] == 1:
            raise _busy_error()
        return FakeCatalog()

    monkeypatch.setattr(organize_service, "open_catalog", flaky_open)

    result = organize_service.set_organize_mode("move", Path("/nonexistent"))

    assert result == {"ok": True, "mode": "move"}
    assert calls["n"] == 2, "the write was not retried exactly once"


def test_the_retry_is_bounded_and_sustained_contention_stays_loud(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """⚠ **CRY-WOLF HALF ONE.** A retry that kept going would hide genuine sustained contention
    behind silence - the failure `REQUEST_BUSY_ATTEMPTS`'s docstring rules against. Exactly two
    attempts, then the busy surfaces."""
    calls = {"n": 0}

    def always_busy(_db: Path) -> object:
        calls["n"] += 1
        raise _busy_error()

    monkeypatch.setattr(organize_service, "open_catalog", always_busy)

    with pytest.raises(sqlite3.OperationalError):
        organize_service.set_organize_mode("move", Path("/nonexistent"))

    assert calls["n"] == REQUEST_BUSY_ATTEMPTS == 2, (
        f"the request-path bound moved: {calls['n']} attempts"
    )


def test_a_genuine_fault_is_not_dressed_as_busy(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF TWO, and the one that matters most.** A handler that translated every
    SQLite error into "busy, try again" would tell the user to retry a missing table forever.

    ⚠ **A REAL fault, not a patched one - and the fixture taught two lessons on the way.** The
    first draft patched the service facade and `test_patch_targets_stay_aimed` refused it; the
    second wrote a corrupt catalog file and learned that **`create_app` opens the catalog at
    construction** (`server.py:153`, `prepare_catalog`), so the fault fired before any route
    existed. A healthy boot whose `settings` table is then dropped raises a genuine non-busy
    `sqlite3.OperationalError` at exactly the write the busy path also hits.
    """
    db = tmp_path / "catalog.sqlite"
    app = create_app(token=TOKEN, db=db)
    with sqlite3.connect(db) as conn:
        conn.execute("DROP TABLE settings")

    with TestClient(app, headers=_HEADERS, raise_server_exceptions=False) as client:
        response = client.post("/api/organize/settings", json={"mode": "move"})

    assert response.status_code == 500, "a genuine fault was not surfaced as a fault"
    assert CATALOG_BUSY_CODE not in response.text, "a fault was dressed up as busy"


def test_the_handler_re_raises_what_is_not_busy() -> None:
    """The re-raise branch, held directly: the handler's only translation is busy."""
    fault = sqlite3.OperationalError("no such table: settings")
    fault.sqlite_errorcode = sqlite3.SQLITE_ERROR

    with pytest.raises(sqlite3.OperationalError):
        anyio.run(lambda: _catalog_busy_refusal(None, fault))  # type: ignore[arg-type]

    busy = _busy_error()
    response = anyio.run(lambda: _catalog_busy_refusal(None, busy))  # type: ignore[arg-type]
    assert response.status_code == 503


def test_every_settings_setter_goes_through_the_retried_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The census's guarantee for the three setters: none of them writes around the retry.

    A fourth setter added tomorrow that opens the catalog itself would reintroduce the raw-500
    path for its route only under sustained contention - the app-level handler still words it -
    so this pins the retry wiring, not the refusal.
    """
    seen: list[str] = []

    def record(_db: Path, key: str, _value: str) -> None:
        seen.append(key)

    monkeypatch.setattr(organize_service, "_write_setting", record)

    organize_service.set_organize_mode("move", Path("/x"))
    organize_service.set_sidebar_collapsed(True, Path("/x"))
    organize_service.set_text_size("large", Path("/x"))

    assert len(seen) == 3, f"a setter bypassed the retried write: {seen}"


def test_the_worded_refusal_reaches_the_browser_as_its_own_sentence() -> None:
    """`api()` in `app.js` shows a server-worded refusal alone; transport noise stays on
    unworded failures. Pinned textually because no JS runner is in the check lane - the browser
    lane owns behaviour, and this guard owns presence."""
    app_js = (
        Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"
    ).read_text(encoding="utf-8")

    assert 'typeof refusal.error === "string"' in app_js, (
        "api() no longer prefers the server's worded refusal"
    )
    assert "failed (${res.status}" in app_js, (
        "the diagnostic prefix for unworded failures was lost - a raw failure needs its address"
    )
