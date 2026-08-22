"""A catalog write that fails is not one bad file. `(afe)`

IMPLEMENTATION_STANDARDS.md §1 says one bad file never aborts a batch, and these tests pin the
**exception** to it and the reason for the exception. §1 is about a file the product could not
use, where skipping costs one file. A catalog write fails *after* the copy is on disk, so there
is no skip available: the cost is the record of a file that now exists, and that absence is what
duplicates the library on the next run.

⚠ **The failures here are produced, never simulated.** The catalog's directory is really
``chmod``-ed and SQLite really refuses; the busy conditions come from a second connection really
holding a lock. Soak three's reason 2 is why: a simulation freezes an assumption about how a
failure presents, and this whole area is one where that assumption has been wrong before -- the
measurement that started this entry found ``sqlite_errorcode`` carrying **1544**, not the ``8`` a
hand-built double would have carried.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest
from truestill_core.catalog import Catalog
from truestill_core.catalog_busy import (
    is_catalog_busy,
    is_catalog_unwritable,
    is_catalog_write_permanent,
    primary_code,
    retry_while_busy,
)
from truestill_core.categorize import CategoryMatch, Confidence
from truestill_core.destinations import LocalDestination
from truestill_core.hashing import sha256_file
from truestill_core.models import (
    ActionStatus,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
)
from truestill_core.organizer import (
    CatalogWriteError,
    Rollback,
    _catalog_stop_detail,
    _roll_back_unrecorded_copy,
    execute,
)

posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="chmod 555 does not deny the owner on Windows; this refusal has no Windows equivalent",
)


def _resolution(source: Path, when: datetime, sha: str) -> Resolution:
    category = CategoryMatch(
        label="Camera", reason="t", confidence=Confidence.MEDIUM, rule="device"
    )
    decision = Decision(
        source=source,
        category=category,
        captured_at=when,
        date_source=DateSource.EXIF,
        date_tag="DateTimeOriginal",
        relative=Path(f"Camera/{when:%Y}/{when:%m}/{source.name}"),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256=sha, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def _sources(root: Path, count: int) -> list[Resolution]:
    root.mkdir(parents=True, exist_ok=True)
    out = []
    for i in range(count):
        f = root / f"pic{i}.jpg"
        f.write_bytes(f"bytes-{i}".encode())
        out.append(_resolution(f, datetime(2023, 5, 4, 12, 0), sha256_file(f)))
    return out


def _readonly_catalog_error(tmp_path: Path) -> sqlite3.Error:
    """A REAL SQLITE_READONLY_DIRECTORY, produced by chmod rather than constructed."""
    d = tmp_path / "ro"
    d.mkdir()
    conn = sqlite3.connect(d / "c.sqlite")
    conn.execute("CREATE TABLE t (x)")
    conn.commit()
    d.chmod(0o555)
    try:
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
    except sqlite3.Error as exc:
        return exc
    finally:
        d.chmod(0o755)
        conn.close()
    pytest.fail("the catalog directory was made read-only and SQLite still wrote to it")


# --------------------------------------------------------------------------------------------
# The classifier. Real codes, and the masking that the measurement forced.
# --------------------------------------------------------------------------------------------


@posix_only
def test_a_read_only_catalog_directory_is_permanent_not_busy(tmp_path: Path) -> None:
    """R5's actual failure, classified. ⚠ Its code is **1544**, not 8."""
    exc = _readonly_catalog_error(tmp_path)
    assert exc.sqlite_errorcode == sqlite3.SQLITE_READONLY_DIRECTORY
    assert exc.sqlite_errorcode != sqlite3.SQLITE_READONLY, (
        "the extended code is not the primary one; a classifier comparing raw codes to "
        "SQLITE_READONLY would not fire here"
    )
    assert primary_code(exc) == sqlite3.SQLITE_READONLY
    assert not is_catalog_busy(exc)
    assert is_catalog_write_permanent(exc)


def test_a_real_contended_write_is_busy(tmp_path: Path) -> None:
    """The ordinary case, from a real second connection holding a real lock."""
    db = tmp_path / "c.sqlite"
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("CREATE TABLE t (x)")
    writer = sqlite3.connect(db, timeout=0.05)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.Error) as caught:
            writer.execute("INSERT INTO t VALUES (1)")
    finally:
        holder.execute("ROLLBACK")
        holder.close()
        writer.close()
    assert is_catalog_busy(caught.value)
    assert not is_catalog_write_permanent(caught.value)


@pytest.mark.parametrize(
    "name",
    ["SQLITE_BUSY_RECOVERY", "SQLITE_BUSY_SNAPSHOT", "SQLITE_BUSY_TIMEOUT"],
)
def test_an_extended_busy_code_is_still_busy(name: str) -> None:
    """⚠ The masking pin. These three answered *not busy* until 2026-08-22.

    Constructed rather than produced, and deliberately so: these three cannot be staged on demand
    (they need WAL recovery, a stale snapshot, or a timeout handler). The value they pin is
    arithmetic -- that a code of the form ``5 | (n << 8)`` reaches the busy side -- which does not
    depend on how the exception was made. The two tests above carry the produced evidence.
    """
    code = getattr(sqlite3, name)
    assert code & 0xFF == sqlite3.SQLITE_BUSY
    exc = sqlite3.OperationalError("database is locked")
    exc.sqlite_errorcode = code
    assert is_catalog_busy(exc), f"{name} ({code}) must reach the retry path"
    assert not is_catalog_write_permanent(exc)


@pytest.mark.parametrize(
    ("name", "why"),
    [
        ("SQLITE_READONLY_DIRECTORY", "the catalog's folder is read-only"),
        ("SQLITE_IOERR_DELETE", "the journal beside the catalog could not be removed"),
        ("SQLITE_FULL", "the drive holding the catalog is full"),
        ("SQLITE_CANTOPEN", "the catalog's folder is gone"),
        ("SQLITE_PERM", "the catalog cannot be opened for writing"),
    ],
)
def test_the_conditions_a_user_can_act_on_are_all_recognised(name: str, why: str) -> None:
    """The unwritable family, each member a real thing that happens to a real drive.

    ⚠ **``SQLITE_IOERR`` is the one to look at twice, and it is not hypothetical.** Measured
    2026-08-22: an `organize` whose catalog directory was ``chmod``-ed to 555 mid-run failed with
    **SQLITE_IOERR_DELETE** -- SQLite could reuse the journal file it had already created, and
    only the *removal* of it needed the directory. So R5 presents as ``READONLY_DIRECTORY`` or as
    ``IOERR_DELETE`` depending on where in the transaction the refusal lands, and dropping
    ``IOERR`` from this set would leave the commonest of the two answering with a traceback.

    That is also why `is_catalog_write_permanent`'s docstring calls ``IOERR``'s *retry* side
    unresolved while this test pins its *wording* side: a flaky USB might make it transient, but
    nothing makes it a bug of ours rather than a condition of the user's.
    """
    code = getattr(sqlite3, name)
    exc = sqlite3.OperationalError("...")
    exc.sqlite_errorcode = code
    assert is_catalog_unwritable(exc), f"{name} ({code}): {why}"
    assert not is_catalog_busy(exc)


def test_a_bug_of_ours_is_not_dressed_up_as_a_condition_of_the_users(tmp_path: Path) -> None:
    """⚠ The other cry-wolf, and a first cut of this entry committed it.

    ``SELECT * FROM no_such_table`` is ``SQLITE_ERROR``. Answering it with "check that the folder
    holding your catalog can be written to" is exactly as useless as answering a read-only disk
    with "wait for the other operation to finish".
    """
    db = tmp_path / "c.sqlite"
    conn = sqlite3.connect(db)
    try:
        with pytest.raises(sqlite3.Error) as caught:
            conn.execute("SELECT * FROM no_such_table")
    finally:
        conn.close()
    assert caught.value.sqlite_errorname == "SQLITE_ERROR"
    assert not is_catalog_unwritable(caught.value)
    assert not is_catalog_busy(caught.value)
    # It is still permanent for the *retry* decision: we must not sit in a backoff loop over it.
    assert is_catalog_write_permanent(caught.value)


def test_an_unrecognised_sqlite_failure_is_permanent_rather_than_retryable() -> None:
    """Unknown must mean permanent, or the product waits out a fault that never clears."""
    exc = sqlite3.OperationalError("something new")
    exc.sqlite_errorcode = sqlite3.SQLITE_CORRUPT
    assert is_catalog_write_permanent(exc)
    bare = sqlite3.OperationalError("no code at all")
    assert not is_catalog_busy(bare)
    assert is_catalog_write_permanent(bare)


# --------------------------------------------------------------------------------------------
# The retry. Busy is transient only because we wait it out.
# --------------------------------------------------------------------------------------------


def test_a_busy_catalog_is_waited_out_rather_than_failed(tmp_path: Path) -> None:
    """A lock released while we retry: the write lands, and the run never learns of it."""
    db = tmp_path / "c.sqlite"
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("CREATE TABLE t (x)")
    writer = sqlite3.connect(db, timeout=0.05, isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    calls = {"n": 0}

    def attempt() -> str:
        calls["n"] += 1
        if calls["n"] == 3:
            holder.execute("ROLLBACK")  # the other operation finishes, mid-retry
        writer.execute("INSERT INTO t VALUES (1)")
        return "wrote"

    try:
        assert retry_while_busy(attempt, sleep=lambda _: None) == "wrote"
        assert calls["n"] == 3, "it must actually have retried, not succeeded first time"
        assert writer.execute("SELECT count(*) FROM t").fetchone()[0] == 1
    finally:
        holder.close()
        writer.close()


@posix_only
def test_a_fault_is_not_waited_out_even_once(tmp_path: Path) -> None:
    """⚠ Found by a surviving mutation, 2026-08-22, and it was a missing guard rather than noise.

    With the early ``raise`` removed, a permanent failure was retried the full ten times and then
    raised the same error, so **every test still passed** -- the end state is identical. What
    changes is everything in between: seconds of backoff per file spent waiting out a fault that
    cannot clear, and a catalog that is already refusing writes hammered ten times instead of
    once. The behaviour under test is the *number of attempts*, so that is what this asserts.
    """
    real = _readonly_catalog_error(tmp_path)
    calls = {"n": 0}

    def attempt() -> None:
        calls["n"] += 1
        raise real

    with pytest.raises(sqlite3.Error):
        retry_while_busy(attempt, sleep=lambda _: None)
    assert calls["n"] == 1, f"a fault was retried {calls['n']} times; it can never clear"


def test_a_busy_that_never_clears_stops_being_transient(tmp_path: Path) -> None:
    """⚠ The property the whole split rests on.

    A transient failure we give up on **is a permanent one**, and for this write it is an
    unrecorded file. If exhausted busy quietly became a per-file failure, a run would copy every
    file for as long as the other process held the lock and record none of them.
    """
    db = tmp_path / "c.sqlite"
    holder = sqlite3.connect(db, isolation_level=None)
    holder.execute("CREATE TABLE t (x)")
    writer = sqlite3.connect(db, timeout=0.05)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        with pytest.raises(sqlite3.Error) as caught:
            retry_while_busy(
                lambda: writer.execute("INSERT INTO t VALUES (1)"),
                attempts=3,
                sleep=lambda _: None,
            )
    finally:
        holder.execute("ROLLBACK")
        holder.close()
        writer.close()
    assert is_catalog_busy(caught.value), "it must surface as the busy it is, for its own wording"


# --------------------------------------------------------------------------------------------
# The rollback. One unlink, and every guard around it.
# --------------------------------------------------------------------------------------------


def _staged_copy(tmp_path: Path) -> tuple[LocalDestination, str, str]:
    root = tmp_path / "dest"
    dest = LocalDestination(root)
    src = tmp_path / "src.jpg"
    src.write_bytes(b"the-bytes")
    dest.upload(src, "Camera/2023/05/src.jpg")
    return dest, "Camera/2023/05/src.jpg", sha256_file(src)


def test_a_copy_whose_row_was_never_written_is_removed_again(tmp_path: Path) -> None:
    """Copy mode: the destination file is redundant, so the run leaves nothing behind."""
    dest, rel, sha = _staged_copy(tmp_path)
    outcome, detail = _roll_back_unrecorded_copy(
        dest, relative=rel, copy_sha=sha, moved_in_place=False
    )
    assert (outcome, detail) == (Rollback.REMOVED, "")
    assert not (dest.local_root() / rel).exists()


def test_a_file_moved_in_place_is_never_removed(tmp_path: Path) -> None:
    """⚠ The data-loss guard. Under --in-place the destination file is the ONLY copy.

    ``moved_in_place`` answers this structurally and is checked before anything else: there is no
    verification that could make deleting the user's only copy safe, so this is not a heuristic
    and the ordering is not incidental.
    """
    dest, rel, sha = _staged_copy(tmp_path)
    outcome, _ = _roll_back_unrecorded_copy(dest, relative=rel, copy_sha=sha, moved_in_place=True)
    assert outcome is Rollback.KEPT_MOVED_IN_PLACE
    assert (dest.local_root() / rel).exists(), "the user's only copy was deleted"


def test_a_copy_whose_contents_no_longer_match_is_left_alone(tmp_path: Path) -> None:
    """We are deleting a path we constructed. Anything we did not write is not ours to remove."""
    dest, rel, _ = _staged_copy(tmp_path)
    outcome, _ = _roll_back_unrecorded_copy(
        dest, relative=rel, copy_sha="0" * 64, moved_in_place=False
    )
    assert outcome is Rollback.KEPT_CONTENT_DIFFERS
    assert (dest.local_root() / rel).exists()


@posix_only
def test_a_copy_that_cannot_be_re_read_is_left_alone(tmp_path: Path) -> None:
    """No verification, no removal -- and the run says so rather than assuming it is gone."""
    dest, rel, sha = _staged_copy(tmp_path)
    target = dest.local_root() / rel
    target.chmod(0o000)
    try:
        outcome, detail = _roll_back_unrecorded_copy(
            dest, relative=rel, copy_sha=sha, moved_in_place=False
        )
    finally:
        target.chmod(0o644)
    assert outcome is Rollback.KEPT_UNVERIFIABLE
    assert detail, "the reason it could not be verified must reach the report"
    assert target.exists()


@posix_only
def test_a_removal_that_fails_is_reported_rather_than_suppressed(tmp_path: Path) -> None:
    """⚠ A swallowed cleanup failure leaves exactly the state we are about to deny exists."""
    dest, rel, sha = _staged_copy(tmp_path)
    parent = (dest.local_root() / rel).parent
    parent.chmod(0o555)
    try:
        outcome, detail = _roll_back_unrecorded_copy(
            dest, relative=rel, copy_sha=sha, moved_in_place=False
        )
    finally:
        parent.chmod(0o755)
    assert outcome is Rollback.REMOVE_FAILED
    assert detail, "the reason the removal failed must reach the report"
    assert (dest.local_root() / rel).exists()


def test_only_a_successful_removal_claims_nothing_was_left_behind() -> None:
    """The two questions the report asks of a rollback, kept from drifting apart."""
    orphaning = set(Rollback) - {Rollback.REMOVED}
    for outcome in orphaning:
        exc = CatalogWriteError(
            sqlite3.OperationalError("x"),
            relative="a/b.jpg",
            source=Path("/s/b.jpg"),
            rollback=outcome,
            rollback_detail="d",
            busy_exhausted=False,
            catalog_dir=Path("/cat"),
        )
        assert exc.left_an_orphan, f"{outcome} leaves a file with no row"
        assert "rescan" in _catalog_stop_detail(exc, recorded=2)


# --------------------------------------------------------------------------------------------
# The run. Soak three's R5, end to end.
# --------------------------------------------------------------------------------------------


def test_the_stop_cannot_be_swallowed_by_the_per_file_handler() -> None:
    """⚠ The entire mechanism, in one assertion.

    `execute`'s per-file boundary catches ``OSError`` and ``DestinationError``. `MetadataBakeError`
    subclasses ``OSError`` **on purpose**, so that it is caught and the run continues. This one
    must do the opposite. If a later change makes it an ``OSError`` "for consistency", the run
    silently goes back to copying files it cannot record.
    """
    assert not issubclass(CatalogWriteError, OSError)
    assert not issubclass(CatalogWriteError, sqlite3.Error), (
        "it must not be caught by a top-level `except sqlite3.Error` either -- the report is "
        "the deliverable, and unwinding past `execute` would lose it"
    )


@posix_only
def test_a_run_whose_catalog_turns_read_only_stops_with_a_report(tmp_path: Path) -> None:
    """R5. The catalog's **directory** goes read-only once files are landing.

    SQLite creates its ``-journal`` sidecar beside the database, so denying the directory refuses
    writes without touching the catalog file's own permissions -- which is why R5 presents as
    ``SQLITE_READONLY_DIRECTORY`` and not as anything about the file.
    """
    catalog_dir = tmp_path / "cat"
    catalog_dir.mkdir()
    catalog = Catalog(catalog_dir / "catalog.sqlite")
    dest_root = tmp_path / "dest"
    resolutions = _sources(tmp_path / "src", 8)

    def deny_once_files_are_landing(progress: object) -> None:
        if getattr(progress, "done", 0) == 4:
            catalog_dir.chmod(0o555)

    try:
        results = execute(
            resolutions,
            LocalDestination(dest_root),
            catalog=catalog,
            apply=True,
            progress=deny_once_files_are_landing,
        )
    finally:
        catalog_dir.chmod(0o755)

    failed = [r for r in results if r.status is ActionStatus.FAILED]
    assert len(failed) == 1, "one stop, not one failure per remaining file"
    detail = failed[0].detail or ""

    # It stopped, rather than carrying on.
    assert len(results) < len(resolutions), "files after the stop must be unattempted"
    assert results[-1].status is ActionStatus.FAILED

    # It reported: what happened, what landed, and where to go.
    assert "could not be written" in detail
    assert "organized and recorded before this" in detail
    assert str(catalog_dir) in detail, "the directory to fix must be named"
    assert "SQLITE_READONLY_DIRECTORY" in detail, "the diagnostic must survive to the report"
    assert "Traceback" not in detail

    # ⚠ And it left nothing on the drive that the catalog does not know about.
    on_disk = {p.name for p in dest_root.rglob("*.jpg")}
    rows = (
        sqlite3.connect(catalog_dir / "catalog.sqlite")
        .execute("SELECT count(*) FROM files")
        .fetchone()[0]
    )
    assert len(on_disk) == rows, (
        f"{len(on_disk)} files on disk against {rows} catalog rows: the run left "
        "files it never recorded"
    )
    assert "removed again" in detail
