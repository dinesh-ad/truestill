"""Extraction: what gets written, what is refused, and what a crash leaves behind ((jj)).

**Ordering is the whole crash story: the journal is written and flushed BEFORE any byte of the
staging tree exists.** The other order leaves files the journal does not know about, which is
the orphaned-200 GB case wearing a different hat - a directory nobody can attribute, on the
drive the user just filled.

**Entry names are REFUSED, not rewritten.** `zipfile.extractall` silently turns ``../../x`` into
``x``, which is safe but lossy: a Takeout never contains such a name, so its presence is a signal
worth reporting rather than normalising away. Streaming forces the issue anyway - the byte
counter needs `open()` per entry, so `extractall`'s sanitising is not on our path at all. Two
characterisation tests below pin the stdlib's behaviour regardless, because *"safe by accident
becomes unsafe if a future Python changes it"* deserves a test that fails on an upgrade rather
than a comment nobody re-reads.

**The budget aborts on the REAL running total, never the declared one.** Declared size is a
header field the attacker writes.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest
from truestill_core.archive_extract import (
    ExtractionRefusedError,
    clear_staging,
    extract_archive_set,
    pending_staging,
    staging_budget,
)
from truestill_core.archive_set import discover_archive_set

#: Run by the SIGKILL test in a separate interpreter, so the recovery assertion is made by a
#: process that never saw the extraction.
_CHILD_EXTRACTOR = (
    "import sys;"
    "from pathlib import Path;"
    "from truestill_core.archive_set import discover_archive_set;"
    "from truestill_core.archive_extract import extract_archive_set;"
    "extract_archive_set(discover_archive_set([Path(sys.argv[1])]), Path(sys.argv[2]))"
)


def _zip(path: Path, entries: dict[str, bytes]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def _symlink_zip(path: Path, name: str, target: str) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        info = zipfile.ZipInfo(name)
        info.external_attr = 0o120777 << 16  # S_IFLNK
        archive.writestr(info, target)
    return path


# --- what gets written -------------------------------------------------------------------


def test_entries_land_under_the_staging_root(tmp_path: Path) -> None:
    _zip(tmp_path / "a.zip", {"Takeout/Photos/IMG_1.jpg": b"x" * 40})
    found = discover_archive_set([tmp_path / "a.zip"])

    result = extract_archive_set(found, tmp_path / "dest")

    assert (result.staging_root / "Takeout/Photos/IMG_1.jpg").read_bytes() == b"x" * 40
    assert result.bytes_written == 40


def test_a_partial_file_is_never_left_where_a_finished_one_belongs(tmp_path: Path) -> None:
    """Written to a sibling and renamed, so an aborted run cannot leave a truncated JPEG that
    hashes as real media."""
    _zip(tmp_path / "a.zip", {"IMG_1.jpg": b"x" * 40})
    found = discover_archive_set([tmp_path / "a.zip"])

    result = extract_archive_set(found, tmp_path / "dest")

    leftovers = [p.name for p in result.staging_root.rglob("*.partial")]
    assert leftovers == []


# --- what is refused ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["../escape.jpg", "../../escape.jpg", "/abs/escape.jpg", "a/../../escape.jpg"]
)
def test_an_escaping_entry_name_is_refused_and_named(tmp_path: Path, name: str) -> None:
    """Refused rather than rewritten: a Takeout never contains one, so it is a signal."""
    _zip(tmp_path / "a.zip", {name: b"x"})
    found = discover_archive_set([tmp_path / "a.zip"])

    with pytest.raises(ExtractionRefusedError) as raised:
        extract_archive_set(found, tmp_path / "dest")

    assert name in str(raised.value)


def test_a_symlink_entry_is_refused(tmp_path: Path) -> None:
    """zipfile happens to write these as regular files rather than links; we refuse instead.

    Relying on that accident would mean a future Python could turn a refused entry into a link
    that writes through to somewhere else.
    """
    _symlink_zip(tmp_path / "a.zip", "evil", "/etc/passwd")
    found = discover_archive_set([tmp_path / "a.zip"])

    with pytest.raises(ExtractionRefusedError, match="evil"):
        extract_archive_set(found, tmp_path / "dest")


def test_nothing_is_written_when_an_entry_is_refused(tmp_path: Path) -> None:
    """A refusal must not leave half a library and an unattributable directory."""
    _zip(tmp_path / "a.zip", {"good.jpg": b"x" * 10, "../escape.jpg": b"y"})
    found = discover_archive_set([tmp_path / "a.zip"])

    with pytest.raises(ExtractionRefusedError):
        extract_archive_set(found, tmp_path / "dest")

    assert pending_staging(tmp_path / "dest") != [], "the staging root must remain attributable"


# --- the budget --------------------------------------------------------------------------


def test_the_budget_aborts_on_the_real_total_not_the_declared_one(tmp_path: Path) -> None:
    """The declared size is a header field the attacker writes; the counter is the truth."""
    _zip(tmp_path / "a.zip", {"big.bin": b"x" * 5000})
    found = discover_archive_set([tmp_path / "a.zip"])

    with pytest.raises(ExtractionRefusedError, match=r"expands to more than"):
        extract_archive_set(found, tmp_path / "dest", budget_bytes=1000)


def test_the_budget_comes_from_free_space_minus_a_reserve(tmp_path: Path) -> None:
    """Stated rather than picked silently: free space is the physical truth an attacker cannot
    influence, and the reserve keeps the machine usable when an export is refused."""
    budget = staging_budget(tmp_path, claimed_bytes=1_000_000)

    assert budget > 0
    assert budget <= max(0, shutil.disk_usage(tmp_path).free)


def test_expanding_far_beyond_the_claim_is_refused_even_with_disk_to_spare(
    tmp_path: Path,
) -> None:
    """The bomb detector. It works BECAUSE the attacker must under-claim to pass the space
    precondition, so over-expansion is exactly the signal that is left."""
    budget = staging_budget(tmp_path, claimed_bytes=100)

    assert budget < 1_000_000, "a tiny claim must not license unbounded expansion"


# --- the stdlib characterisation tests ---------------------------------------------------


def test_zipfile_still_neutralises_escaping_names(tmp_path: Path) -> None:
    """Not our defence - ours refuses - but pinned so a change is noticed on upgrade."""
    _zip(tmp_path / "t.zip", {"../../escaped.txt": b"x"})
    out = tmp_path / "out"
    out.mkdir()

    with zipfile.ZipFile(tmp_path / "t.zip") as archive:
        archive.extractall(out)

    assert (out / "escaped.txt").exists()
    assert not (tmp_path / "escaped.txt").exists(), "zipfile.extractall escaped its destination"


def test_zipfile_still_refuses_to_create_symlinks(tmp_path: Path) -> None:
    """The accident we do not rely on, pinned so an upgrade fails here and not on a user's disk."""
    _symlink_zip(tmp_path / "t.zip", "link", "/etc/passwd")
    out = tmp_path / "out"
    out.mkdir()

    with zipfile.ZipFile(tmp_path / "t.zip") as archive:
        archive.extractall(out)

    assert not (out / "link").is_symlink(), "zipfile started creating symlinks on extract"


# --- the crash story ---------------------------------------------------------------------


def test_the_journal_exists_before_any_extracted_byte_does(tmp_path: Path) -> None:
    """The ordering, asserted at the only moment it can be: from inside the first write.

    The other order leaves files the journal does not know about - an unattributable directory
    on the drive the user just filled.
    """
    _zip(tmp_path / "a.zip", {"IMG_1.jpg": b"x" * 10})
    found = discover_archive_set([tmp_path / "a.zip"])
    destination = tmp_path / "dest"
    seen: list[bool] = []

    def observe(_path: Path) -> None:
        seen.append(pending_staging(destination) != [])

    extract_archive_set(found, destination, on_entry=observe)

    assert seen, "no entry was written, so the ordering was never observed"
    assert all(seen), "a byte was written before the journal knew about the staging root"


@pytest.mark.skipif(os.name == "nt", reason="POSIX SIGKILL")
def test_a_real_kill_leaves_a_state_a_fresh_process_can_clear(tmp_path: Path) -> None:
    """SIGKILL specifically: no handler runs, so the journal is the only thing that can know.

    Simulated by calling a cleanup function this would test the function, not the property. The
    assertion is made from **this** process, which never saw the extraction - a state only the
    original process could interpret is not recovery.
    """
    entries = {f"Takeout/IMG_{i:04d}.jpg": os.urandom(200_000) for i in range(200)}
    _zip(tmp_path / "big.zip", entries)
    destination = tmp_path / "dest"

    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _CHILD_EXTRACTOR,
            str(tmp_path / "big.zip"),
            str(destination),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # Wait for real EXTRACTED FILES, not merely for the journal. Waiting on the journal
        # alone killed the child before it had written anything, which proves the ordering but
        # not recovery *mid-extraction* - measured at 0.34s, which is what gave it away.
        deadline = time.monotonic() + 30
        while True:
            records = pending_staging(destination)
            written = list(records[0].staging_root.rglob("*.jpg")) if records else []
            if len(written) >= 5:
                break
            assert child.poll() is None, "the child finished before it could be interrupted"
            assert time.monotonic() < deadline, "the child never extracted anything to interrupt"
            time.sleep(0.01)
        # Asserted immediately before the signal: without it this test survives a mutation
        # that journals AFTER extraction, because "finished, then journalled" is indistinguishable
        # from "killed mid-extraction" once the loop exits. It must kill a RUNNING process.
        assert child.poll() is None, "the child had already finished; nothing was interrupted"
        child.send_signal(signal.SIGKILL)
        child.wait(timeout=30)
    finally:
        if child.poll() is None:  # pragma: no cover - only on a hung child
            child.kill()
            child.wait(timeout=10)

    # A fresh process, with nothing but the destination path.
    leftover = pending_staging(destination)
    assert leftover, "a SIGKILLed extraction left nothing the next run can attribute"
    orphaned = list(leftover[0].staging_root.rglob("*.jpg"))
    assert orphaned, "precondition: the kill must have landed mid-extraction, not before it"

    clear_staging(leftover[0])

    assert pending_staging(destination) == []
    assert not leftover[0].staging_root.exists()


def test_the_partial_handle_is_closed_before_it_is_unlinked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The property, asserted so it fails on **Linux** where the bug is otherwise invisible.

    POSIX happily unlinks an open file, so a cleanup that runs while the handle is still open
    works here and raises ``PermissionError`` (WinError 32) on Windows - which meant CI caught
    this and every local run did not. Asserting the *exception* would only reproduce on Windows;
    asserting the *ordering* reproduces everywhere.

    The user-visible cost of the bug was worse than a leftover file: the budget abort surfaced
    as a permission error, so a refusal Truestill makes on purpose read as a filesystem failure.
    """
    _zip(tmp_path / "a.zip", {"big.bin": b"x" * 5000})
    found = discover_archive_set([tmp_path / "a.zip"])

    handles: dict[Path, object] = {}
    real_open = Path.open
    real_unlink = Path.unlink
    unlinked_while_open: list[Path] = []

    def tracking_open(self: Path, *args: object, **kwargs: object) -> object:
        handle = real_open(self, *args, **kwargs)  # type: ignore[arg-type]
        if self.name.endswith(".partial"):
            handles[self] = handle
        return handle

    def checking_unlink(self: Path, **kwargs: object) -> None:
        handle = handles.get(self)
        if handle is not None and not handle.closed:  # type: ignore[attr-defined]
            unlinked_while_open.append(self)
        real_unlink(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", tracking_open)
    monkeypatch.setattr(Path, "unlink", checking_unlink)

    with pytest.raises(ExtractionRefusedError, match=r"expands to more than"):
        extract_archive_set(found, tmp_path / "dest", budget_bytes=1000)

    assert handles, "no .partial was ever opened, so the ordering was never observed"
    assert unlinked_while_open == [], (
        "a .partial was unlinked while its handle was still open - POSIX tolerates this and "
        "Windows raises PermissionError"
    )


def test_an_aborted_extraction_is_still_described_by_its_journal(tmp_path: Path) -> None:
    """The staging tree stays attributable after an abort, partial files included.

    Now that cleanup happens after the handle closes, a `.partial` can briefly outlive a failed
    entry - so the thing that matters is that everything left behind is under the journalled
    root and goes away with it.
    """
    _zip(tmp_path / "a.zip", {"big.bin": b"x" * 5000})
    found = discover_archive_set([tmp_path / "a.zip"])
    destination = tmp_path / "dest"

    with pytest.raises(ExtractionRefusedError):
        extract_archive_set(found, destination, budget_bytes=1000)

    leftover = pending_staging(destination)
    assert leftover, "an aborted extraction left nothing the next run can attribute"
    for stray in leftover[0].staging_root.rglob("*"):
        assert stray.is_relative_to(leftover[0].staging_root)

    clear_staging(leftover[0])

    assert pending_staging(destination) == []
    assert not leftover[0].staging_root.exists()
