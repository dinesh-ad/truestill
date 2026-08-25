"""A folder attach cannot list is named, and its files are not quietly dropped.

**Measured before it was fixed**, on a scratch drive with a real ``chmod 000`` folder: five files
on the drive, three of them under the locked folder. ``attach_drive`` reported
``linked=2, unreadable=0, absent=3`` and wrote two ``file_copies`` rows. The three files were
physically present and got no copy row, so ``verify`` could not check them, ``status`` would not
count them toward 3-2-1 and ``where`` could not find them.

Two things made that worse than silence. ``rglob`` swallows ``PermissionError`` by design, so an
unlistable subtree simply does not appear - the files were never candidates, which is why
``unreadable`` (a per-*file* count, incremented where a hash fails) read **0** rather than 3.
And ``absent`` means *"catalogued files whose copy is not actually on the drive"*, so the one
number that moved was stating the opposite of the truth about a drive holding those copies.

``organizer.scan_source`` already solved this for the source side with
``Path.walk(on_error=...)``; this is the same construction on the custody side.

**Folders are named without a count, files are counted** - the asymmetry
``SourceScan.unreadable_dirs`` already carries (`IMPLEMENTATION_STANDARDS.md` §9): the walk never
went inside, so any number would be invented.
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest
from truestill_app.service.backup import backup_preview
from truestill_app.service.drives import attach_drive
from truestill_core.backup import UNREAD_FOLDERS_REASON
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file

# One condition, never two stacked decorators - see `test_platform_skips_collect_everywhere.py`.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or os.geteuid() == 0,
    reason="needs POSIX permissions and a non-root user",
)

_UUID = "DRIVE-1"
_LOCKED = "Camera/2015/09"
_LAYOUT = {
    "Camera/2014/08/open-a.jpg": b"bytes-open-a",
    "Camera/2014/08/open-b.jpg": b"bytes-open-b",
    f"{_LOCKED}/locked-a.jpg": b"bytes-locked-a",
    f"{_LOCKED}/locked-b.jpg": b"bytes-locked-b",
    f"{_LOCKED}/locked-c.jpg": b"bytes-locked-c",
}


@pytest.fixture
def drive(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    """A drive holding an organized library whose per-drive copy rows are gone (re-attach)."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    shas: dict[str, str] = {}
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=_UUID, label="Drive")
        for relative, payload in _LAYOUT.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            shas[relative] = sha256_file(path)
            catalog.record_uploaded(
                source_path=f"/src/{Path(relative).name}",
                original_name=Path(relative).name,
                sha256=shas[relative],
                copy_sha256=shas[relative],
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2014-08-16T10:46:26",
                category="Camera",
                relative=relative,
                drive_uuid=_UUID,
            )
        catalog._conn.execute("DELETE FROM file_copies WHERE drive_uuid = ?", (_UUID,))
        catalog._conn.commit()
    return db, root, shas


@pytest.fixture
def locked(drive: tuple[Path, Path, dict[str, str]]) -> tuple[Path, Path, dict[str, str]]:
    """`drive`, with one folder the current user cannot list. Restored however the test ends."""
    db, root, shas = drive
    folder = root / _LOCKED
    folder.chmod(0o000)
    try:
        yield db, root, shas  # type: ignore[misc]
    finally:
        folder.chmod(stat.S_IRWXU)


def _recorded(db: Path) -> set[str]:
    with Catalog(db) as catalog:
        rows = catalog._conn.execute("SELECT relative FROM file_copies")
        return {str(r["relative"]) for r in rows}


def test_the_fixture_really_denies_the_folder(
    locked: tuple[Path, Path, dict[str, str]],
) -> None:
    """Precondition asserted in the body, not merely set in the fixture (§4).

    `chmod 000` is a no-op for root, and this file's own skip is what keeps that true - if the
    skip were ever narrowed, every assertion below would pass while testing nothing.
    """
    _db, root, _shas = locked
    assert not os.access(root / _LOCKED, os.R_OK), "the folder is still readable - no condition"


def test_an_unreadable_folder_on_the_drive_is_named(
    locked: tuple[Path, Path, dict[str, str]],
) -> None:
    """The fact must survive the walk. Named, never a bare number, never nothing."""
    db, root, _shas = locked

    result = attach_drive(root, db, write=True)

    assert result.unreadable_dirs == (_LOCKED,), (
        f"a folder attach could not list was not named: {result.unreadable_dirs}"
    )


def test_the_readable_copies_are_still_attached(
    locked: tuple[Path, Path, dict[str, str]],
) -> None:
    """One locked folder must not cost the rest of the drive - the partial-failure policy."""
    db, root, shas = locked

    result = attach_drive(root, db, write=True)

    assert result.linked == 2
    assert _recorded(db) == {r for r in shas if not r.startswith(_LOCKED)}


def test_an_ordinary_drive_names_no_folder(
    drive: tuple[Path, Path, dict[str, str]],
) -> None:
    """The cry-wolf half: a drive with nothing locked must report nothing (§4).

    Without this, a guard that named every folder would pass the test above and be switched off
    the first time it fired on a healthy drive.
    """
    db, root, shas = drive

    result = attach_drive(root, db, write=True)

    assert result.unreadable_dirs == ()
    assert result.linked == len(shas)


# --- and it has to REACH somebody. `(abm)` ------------------------------------------------


def _preview(db: Path, source: Path) -> dict[str, object]:
    """`backup_preview` from this drive to a fresh empty one beside it, both marked."""
    create_marker(source, "Source")
    target = source.parent / "target"
    target.mkdir()
    create_marker(target, "Target")
    return dict(backup_preview(source, target, db))


def test_the_preview_names_the_folder_it_could_not_read(
    locked: tuple[Path, Path, dict[str, str]],
) -> None:
    """⚠ **THE PROPERTY, and the dataclass already had it - that WAS the defect.** `(abm)`

    `DriveAttachment.unreadable_dirs` has been correct since the walk fix above; `service/backup.py`
    read `.label`, `.registered` and `.linked` and dropped the rest, so the fact stopped at the
    Python boundary. Asserting on the outcome object would pass without a user ever seeing it,
    which is why this asserts on the **payload**.

    ⚠ **`unreadable` IS NOT COVERED BY `test_no_thirty_fifth_dead_payload_key.py`, and nobody
    should later assume it is.** That guard works at key-NAME granularity, and `unreadable`
    already appears in `app.js` through other payloads - verify's `v.unreadable` and takeout's
    `r.unreadable` - so a dead `unreadable` key would read as live and slip through. The same
    collision hides `BakeSummary.absent`. `unreadable_dirs`, `unread_title` and `unread_reason`
    are unique names and ARE covered; this one field's render is a human check, and this test is
    it.
    """
    db, root, _ = locked

    payload = _preview(db, root)

    assert payload["ok"] is True
    folders = list(payload["unreadable_dirs"])  # type: ignore[call-overload]
    assert any(_LOCKED in entry for entry in folders), (
        f"the locked folder is not in the payload: {folders!r}"
    )
    assert "Source" in folders[0], "each entry names its drive - either side can carry one"
    assert payload["unread_title"], "the banner heading must travel with it"
    assert payload["unread_reason"], "so must the sentence explaining it"


def test_the_preview_of_a_readable_drive_says_nothing(
    drive: tuple[Path, Path, dict[str, str]],
) -> None:
    """⚠ **CRY-WOLF HALF.** A banner on every ordinary backup is one nobody reads, and §4's rule
    about a guard that fires on healthy input applies to user-facing warnings first."""
    db, root, _ = drive

    payload = _preview(db, root)

    assert payload["unreadable_dirs"] == []
    assert payload["unread_title"] == ""
    assert payload["unread_reason"] == ""


def test_the_wording_is_not_typed_into_the_browser() -> None:
    """One wording home (`(ahc)`'s ruling): `app.js` renders what the payload handed it.

    ⚠ **Read from `app.js` as text rather than through a browser** - the same route
    `test_the_rearrange_card_name.py` uses, and the reason the browser lane is not needed for a
    wording change.
    """
    app_js = (Path(__file__).resolve().parents[1] / "src/truestill_app/static/app.js").read_text(
        encoding="utf-8"
    )

    assert "unread_title" in app_js, "the banner does not render the heading it is handed"
    assert "unread_reason" in app_js, "the banner does not render the sentence it is handed"
    assert UNREAD_FOLDERS_REASON not in app_js, (
        "the sentence is typed into the browser as well as core - two homes, two languages, "
        "which is exactly what `STOP_WORDING` exists to prevent"
    )


#: The two cards `backup_preview` can produce, by a phrase unique to each. **Both must warn**, and
#: the first is the one that matters: it is where the screen reassures.
_BACKUP_CARDS = ("Already backed up.", "to copy</div>")


def test_both_preview_cards_call_the_warning() -> None:
    """⚠ **FOUND BY MUTATION, AND IT SURVIVED EVERYTHING ELSE.** `(abm)`

    Deleting `${unreadFolders(r)}` from the *nothing-to-copy* card - the single place a user is
    told their backup is complete - was caught by **nothing**: `test_no_thirty_fifth_dead_payload_key.py`
    is a text search and the key names still appear inside the helper, and the test above only
    asks whether the strings exist somewhere in the file.

    **A helper that is defined and not called is indistinguishable from one that is used**, to any
    check that greps. So this asserts the call site per card rather than the name per file, which
    is the same distinction `(agu)` drew between a name being present and a route declaring itself.
    """
    app_js = (Path(__file__).resolve().parents[1] / "src/truestill_app/static/app.js").read_text(
        encoding="utf-8"
    )

    for phrase in _BACKUP_CARDS:
        assert phrase in app_js, f"the card marked by {phrase!r} moved; this test is now blind"
        card = app_js[app_js.index(phrase) : app_js.index("`);", app_js.index(phrase))]
        assert "unreadFolders(r)" in card, (
            f"the card marked by {phrase!r} does not warn about folders that could not be read"
        )


def test_the_warning_has_one_guard_and_one_render() -> None:
    """⚠ **THE SECOND SURVIVOR, and the honest limit beside it.** `(abm)`

    Making `unreadFolders` `return ""` unconditionally passed every other check here: the payload
    was still right, the names were still in the file, and both call sites were still there. A
    helper called from the right places that renders nothing is invisible to text.

    So the shape is pinned: **exactly two returns** - the guard that keeps an ordinary backup
    silent, and the banner. A third is either a new early exit or the mutation above.

    ⚠ **WHAT THIS STILL CANNOT SEE, stated rather than implied**: whether the banner *appears in a
    browser*. That is the browser lane's question, and it was deliberately not run - this change
    ADDS a render and no screen stops showing anything, so `IMPLEMENTATION_STANDARDS.md` §6.1's
    condition is not met. A structural pin is what `make check` can honestly offer here.
    """
    app_js = (Path(__file__).resolve().parents[1] / "src/truestill_app/static/app.js").read_text(
        encoding="utf-8"
    )
    start = app_js.index("function unreadFolders(r) {")
    body = app_js[start : app_js.index("\nfunction ", start + 1)]

    assert body.count("return") == 2, (
        f"`unreadFolders` has {body.count('return')} returns, not the guard and the banner. "
        "An unconditional early return renders nothing and every other check here passes."
    )
    assert 'if (!folders.length && !r.unreadable) return "";' in body, (
        "the silent case is no longer guarded on both facts"
    )
    assert UNREAD_FOLDERS_REASON not in app_js, (
        "the sentence is typed into the browser as well as core - two homes, two languages, "
        "which is exactly what `STOP_WORDING` exists to prevent"
    )
