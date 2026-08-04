"""Cleaning the skeleton a migration leaves, without deleting anything it did not create.

Every test here is one of two questions: does it collapse what truestill emptied, and does it
leave alone everything else? The second matters more -- the whole category of empty-folder
cleaners earns its bad name by sweeping a drive and removing a directory the user meant to keep.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_core import cleanup
from truestill_core.cleanup import (
    JUNK_NAMES,
    NO_TRASH_REASON,
    CleanupPlan,
    Tier,
    emptied_directories,
    plan_cleanup,
    run_cleanup,
)


def _fingerprint(root: Path) -> list[str]:
    """Every path under a root -- files and folders -- so a removal cannot hide."""
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


def _skeleton(root: Path) -> list[str]:
    """A migration's leftovers: nested empty months under an empty category folder."""
    for relative in ("Camera/2013/09", "Camera/2013/10", "Camera/2014/01"):
        (root / relative).mkdir(parents=True)
    return emptied_directories(
        ["Camera/2013/09/a.jpg", "Camera/2013/10/b.jpg", "Camera/2014/01/c.jpg"]
    )


def test_a_nested_skeleton_collapses_bottom_up(tmp_path: Path) -> None:
    """Emptying the months is what makes the years, and then the category folder, removable.

    A top-down pass would look at `Camera/` while its children still existed, call it occupied
    and stop -- leaving exactly the skeleton the feature exists to remove.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)

    plan = plan_cleanup(root, emptied)

    assert [c.relative for c in plan.removable] == [
        "Camera/2013/09",
        "Camera/2013/10",
        "Camera/2014/01",
        "Camera/2013",
        "Camera/2014",
        "Camera",
    ]
    assert not plan.occupied

    # permanent=True is not the subject here - it is how this test still reaches a real
    # removal now that an absent backend refuses. What it asserts is which folders are
    # removable, which the 2026-08-04 refusal change did not touch.
    outcome = run_cleanup(root, plan, apply=True, backend=None, permanent=True)
    removed, failures = outcome.removed, outcome.failures
    assert removed == 6
    assert not failures
    assert not (root / "Camera").exists()


def test_a_junk_only_folder_is_removed_with_its_junk(tmp_path: Path) -> None:
    """`.DS_Store` should not keep a dead folder alive -- but it is named, not guessed."""
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    (root / "Camera/2013/09/.DS_Store").write_text("finder")
    (root / "Camera/2014/01/empty.log").write_bytes(b"")  # zero-byte counts as junk

    plan = plan_cleanup(root, emptied)

    junk = {c.relative: c for c in plan.candidates if c.tier is Tier.JUNK_ONLY}
    assert set(junk) == {"Camera/2013/09", "Camera/2014/01"}
    assert junk["Camera/2013/09"].contents == (".DS_Store",)
    assert junk["Camera/2014/01"].contents == ("empty.log",)

    # permanent=True is not the subject here - it is how this test still reaches a real
    # removal now that an absent backend refuses. What it asserts is which folders are
    # removable, which the 2026-08-04 refusal change did not touch.
    run_cleanup(root, plan, apply=True, backend=None, permanent=True)
    assert not (root / "Camera").exists()  # the junk went with the folders


def test_one_unknown_dotfile_keeps_a_folder_and_is_reported(tmp_path: Path) -> None:
    """Unknown is never junk. The folder survives and the file is named in the report."""
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    (root / "Camera/2013/09/.hidden-notes").write_text("something a user wrote")

    plan = plan_cleanup(root, emptied)

    occupied = {c.relative: c for c in plan.occupied}
    assert ".hidden-notes" in occupied["Camera/2013/09"].contents
    # Its parents survive too: they still hold a folder that is staying.
    assert "Camera/2013" in occupied
    assert "Camera" in occupied

    run_cleanup(root, plan, apply=True, backend=None)
    assert (root / "Camera/2013/09/.hidden-notes").read_text() == "something a user wrote"
    assert (root / "Camera/2013/09").is_dir()


def test_a_folder_holding_a_real_file_is_never_touched(tmp_path: Path) -> None:
    """The failure mode that matters: a photo the migration did not move must survive."""
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    keeper = root / "Camera/2014/01/still-here.jpg"
    keeper.write_bytes(b"a real photo")

    before = _fingerprint(root)
    plan = plan_cleanup(root, emptied)
    # permanent=True is not the subject here - it is how this test still reaches a real
    # removal now that an absent backend refuses. What it asserts is which folders are
    # removable, which the 2026-08-04 refusal change did not touch.
    run_cleanup(root, plan, apply=True, backend=None, permanent=True)

    assert keeper.read_bytes() == b"a real photo"
    assert "Camera/2014/01" in {c.relative for c in plan.occupied}
    # The unrelated branch still collapsed, so refusing one folder does not block the rest.
    assert not (root / "Camera/2013").exists()
    assert set(before) - set(_fingerprint(root))  # something was removed, just not the keeper


def test_a_preview_removes_nothing(tmp_path: Path) -> None:
    """Standing discipline: planning is a read. Byte-identical proof, same as the others."""
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    (root / "Camera/2013/09/.DS_Store").write_text("finder")

    before = _fingerprint(root)
    plan = plan_cleanup(root, emptied)
    outcome = run_cleanup(root, plan, apply=False)
    removed, failures = outcome.removed, outcome.failures

    assert removed == 0
    assert not failures
    assert _fingerprint(root) == before


def _refusing_trash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the trash refuse, deterministically.

    The refusal is simulated rather than provoked: whether a real `gio trash` succeeds depends on
    the host -- it declines "system internal mounts" like /tmp on a developer box but accepts the
    same path on a CI runner. A test that asserts a refusal must not depend on which of those it
    is running on.
    """

    def refuse(_path: Path, _backend: str) -> None:
        message = "Unable to trash file across filesystem boundaries"
        raise OSError(message)

    monkeypatch.setattr(cleanup, "_to_trash", refuse)


def test_a_trash_failure_is_reported_not_downgraded_to_a_permanent_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trash can be refused per PATH, not just per machine.

    `gio trash` declines network and FUSE mounts, which is exactly where a cloud-synced library
    lives. When the user agreed to a recoverable removal, silently doing an irreversible one
    instead would break that agreement -- so the folder stays and the refusal is reported.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    _refusing_trash(monkeypatch)

    plan = plan_cleanup(root, emptied)
    outcome = run_cleanup(root, plan, apply=True, backend="gio")
    removed, failures = outcome.removed, outcome.failures

    assert removed == 0
    assert len(failures) == len(plan.removable)
    assert (root / "Camera/2013/09").is_dir()  # nothing was deleted behind the user's back


def test_no_trash_backend_is_a_refusal_not_a_licence_to_destroy(tmp_path: Path) -> None:
    """No trash on this machine means the folder is LEFT IN PLACE and reported.

    **This test replaces one that asserted the opposite, and the promise it asserted was
    withdrawn on 2026-08-04 rather than quietly reinterpreted.** The old test was
    ``test_removal_works_when_there_is_no_trash_to_use``, and its docstring called this "the
    disclosed-permanent path". It asserted ``removed == 6``, no failures, and the tree gone.

    **Why the old promise was wrong.** ``permanent`` was consulted only where trash was *tried
    and refused*; where there was no backend at all, the flag was never read and removal was
    unconditional. So two states that a user cannot tell apart - "your drive would not accept a
    trashed folder" and "this computer has no trash" - produced opposite outcomes, and the
    destructive one was the one that needed no decision from anybody. ``gio`` is a GLib tool, so
    "no backend" was the ordinary condition on Windows and macOS while a Linux desktop took the
    recoverable path; the safer behaviour was an accident of the developer's platform.

    Disclosure was never the problem - both surfaces did say which was about to happen. The
    problem is that the answer was decided by the machine rather than by the user, and the
    machine's default answer was the irreversible one. Destruction now requires ``permanent``,
    which is the flag whose whole purpose is to be asked for.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)

    plan = plan_cleanup(root, emptied)
    outcome = run_cleanup(root, plan, apply=True, backend=None)

    assert outcome.removed == 0
    assert outcome.trashed == 0
    assert outcome.deleted == 0
    assert (root / "Camera/2013/09").is_dir(), "a folder was destroyed with no trash and no flag"
    assert (root / "Camera").is_dir()

    # Never-silent: refused is reported per folder, by name, with a reason - not skipped.
    assert len(outcome.failures) == len(plan.removable)
    for candidate in plan.removable:
        assert any(f.startswith(f"{candidate.relative}:") for f in outcome.failures)
    assert all(NO_TRASH_REASON in failure for failure in outcome.failures)


def test_a_drive_that_cannot_hold_a_trash_is_reported_not_silently_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The external-backup-drive case, asserted with the REAL exception type.

    On Freedesktop platforms `send2trash` raises `TrashPermissionError` for a file on a device
    whose root has no `.Trash` and where a `.Trash-$UID` cannot be created - which is an ordinary
    external drive, and therefore the single most likely refusal a user of this product meets.

    Asserted with the real class rather than a bare `OSError` because the two are only equivalent
    while `TrashPermissionError` stays in that hierarchy: it subclasses `PermissionError`, which
    subclasses `OSError`, and `run_cleanup` catches `OSError`. If upstream ever reparents it, our
    handler stops catching it and the folder removal raises out of the loop instead of being
    reported - and a stand-in `OSError` would go on passing. This is the §4 provenance rule
    applied to a dependency's exception tree.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)

    from send2trash import TrashPermissionError  # noqa: PLC0415 - the subject of this test

    assert issubclass(TrashPermissionError, OSError), (
        "TrashPermissionError left the OSError hierarchy upstream; run_cleanup no longer catches "
        "it and a refusal on an external drive would raise instead of being reported"
    )

    def refuse(_path: Path, _backend: str) -> None:
        raise TrashPermissionError(str(root))

    monkeypatch.setattr(cleanup, "_to_trash", refuse)

    plan = plan_cleanup(root, emptied)
    outcome = run_cleanup(root, plan, apply=True, backend="send2trash")

    assert outcome.removed == 0
    assert (root / "Camera/2013/09").is_dir(), "a folder went with a refusal we said we handled"
    # Told, not silently skipped: one named line per folder that was left alone.
    assert len(outcome.failures) == len(plan.removable)
    for candidate in plan.removable:
        assert any(f.startswith(f"{candidate.relative}:") for f in outcome.failures)


def test_permanent_still_removes_when_there_is_no_trash_at_all(tmp_path: Path) -> None:
    """The cry-wolf half: the refusal above must not have disabled ``--permanent`` itself.

    ``--permanent`` exists for mounts with nowhere to trash to
    (`IMPLEMENTATION_STANDARDS.md` §1). If the change above had made an absent backend refuse
    *unconditionally*, that mode would have become unreachable on the machines it was written
    for, and every test here would still have been green. This is the assertion that fails if
    the refusal is widened past the case it was for.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)

    plan = plan_cleanup(root, emptied)
    outcome = run_cleanup(root, plan, apply=True, backend=None, permanent=True)

    assert outcome.deleted == 6
    assert not outcome.failures
    assert not (root / "Camera").exists()


def test_scope_is_the_journal_not_the_drive(tmp_path: Path) -> None:
    """An empty folder truestill never emptied is not a candidate, and cannot be removed.

    This is the decision that keeps the whole feature safe: a deliberate placeholder is
    indistinguishable from a leftover by inspection, so it is distinguished by provenance.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    placeholder = root / "My Own Empty Folder"
    placeholder.mkdir()

    plan = plan_cleanup(root, emptied)
    run_cleanup(root, plan, apply=True, backend=None)

    assert placeholder.is_dir()
    assert "My Own Empty Folder" not in {c.relative for c in plan.candidates}


def test_the_junk_list_is_a_named_set_not_a_pattern() -> None:
    """Extending it must be a deliberate edit, so it is asserted as an exact membership."""
    assert ".DS_Store" in JUNK_NAMES
    assert "Thumbs.db" in JUNK_NAMES
    assert "notes.txt" not in JUNK_NAMES
    assert ".hidden" not in JUNK_NAMES  # dotfiles as a class are NOT junk


def test_an_empty_plan_is_harmless(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    root.mkdir()
    assert run_cleanup(root, CleanupPlan(), apply=True).removed == 0


def test_a_refused_folder_names_loose_files_alongside_subfolders(tmp_path: Path) -> None:
    """Never-silent applies to the refusal report, not just to the decision.

    A loose file must be named, not just counted and not just subfolders. If the listing showed
    only directories, a preview could not be checked against a file someone knows is there --
    and a preview you cannot check is one you should not confirm against.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    (root / "Camera/2014/loose-photo.jpg").write_bytes(b"a real photo")

    plan = plan_cleanup(root, emptied)

    refused = {c.relative: c for c in plan.occupied}
    # `contents` names what is KEEPING THE FOLDER ALIVE, not everything inside it: `2014-01` is
    # already going in this pass, so the loose photo is the whole reason `Camera/2014` stays.
    assert refused["Camera/2014"].contents == ("loose-photo.jpg",)
    assert "Camera" in refused  # and the parent is refused because that child survives


def test_permanent_mode_only_applies_where_trash_was_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Trash is still tried first; permanent only changes what happens when it says no.

    That is why the mode needs no separate "is trash available here?" gate -- it applies per
    folder, and exactly to the folders trash would not take.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    _refusing_trash(monkeypatch)  # every folder therefore falls through to the permanent path

    outcome = run_cleanup(
        root, plan_cleanup(root, emptied), apply=True, backend="gio", permanent=True
    )

    assert outcome.trashed == 0
    assert outcome.deleted == 6
    assert not outcome.failures
    assert not (root / "Camera").exists()


def test_permanent_removal_cannot_delete_a_folder_that_gained_a_file(tmp_path: Path) -> None:
    """The race the confirm prompt opens: a preview said empty, then something appeared.

    Removal uses rmdir semantics, so a non-empty folder physically cannot go -- the protection is
    structural rather than a re-check that could itself race. `rmtree` would have taken it.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    plan = plan_cleanup(root, emptied)
    assert "Camera/2013/09" in {c.relative for c in plan.removable}

    # Between the preview and the confirm, something lands in one of the approved folders.
    (root / "Camera/2013/09/appeared.jpg").write_bytes(b"a new photo")

    outcome = run_cleanup(root, plan, apply=True, backend=None, permanent=True)

    assert (root / "Camera/2013/09/appeared.jpg").read_bytes() == b"a new photo"
    assert any("Camera/2013/09" in f for f in outcome.failures)
    # Its parents are refused too, because the child survives -- the skeleton stops collapsing
    # at the first thing that is actually in use.
    assert (root / "Camera/2013").is_dir()
    assert (root / "Camera").is_dir()


def test_permanent_removal_still_takes_named_junk_with_the_folder(tmp_path: Path) -> None:
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    (root / "Camera/2013/09/.DS_Store").write_text("finder")

    outcome = run_cleanup(
        root, plan_cleanup(root, emptied), apply=True, backend=None, permanent=True
    )

    assert not outcome.failures
    assert not (root / "Camera").exists()
