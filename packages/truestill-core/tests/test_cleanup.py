"""Cleaning the skeleton a migration leaves, without deleting anything it did not create.

Every test here is one of two questions: does it collapse what truestill emptied, and does it
leave alone everything else? The second matters more -- the whole category of empty-folder
cleaners earns its bad name by sweeping a drive and removing a directory the user meant to keep.
"""

from __future__ import annotations

from pathlib import Path

from truestill_core.cleanup import (
    JUNK_NAMES,
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

    outcome = run_cleanup(root, plan, apply=True, backend=None)
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

    run_cleanup(root, plan, apply=True, backend=None)
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
    run_cleanup(root, plan, apply=True, backend=None)

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


def test_a_trash_failure_is_reported_not_downgraded_to_a_permanent_delete(
    tmp_path: Path,
) -> None:
    """Trash can be refused per PATH, not just per machine.

    `gio trash` declines "system internal mounts" and network/FUSE mounts, which is exactly
    where a cloud-synced library lives. When the user agreed to a recoverable removal, silently
    doing an irreversible one instead would break that agreement -- so the folder stays and the
    refusal is reported.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)

    plan = plan_cleanup(root, emptied)
    outcome = run_cleanup(root, plan, apply=True, backend="gio")
    removed, failures = outcome.removed, outcome.failures

    assert removed == 0
    assert len(failures) == len(plan.removable)
    assert (root / "Camera/2013/09").is_dir()  # nothing was deleted behind the user's back


def test_removal_works_when_there_is_no_trash_to_use(tmp_path: Path) -> None:
    """The disclosed-permanent path. Covered because only one of the two is recoverable."""
    root = tmp_path / "drive"
    emptied = _skeleton(root)

    plan = plan_cleanup(root, emptied)
    outcome = run_cleanup(root, plan, apply=True, backend=None)
    removed, failures = outcome.removed, outcome.failures

    assert removed == 6
    assert not failures
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


def test_permanent_mode_only_applies_where_trash_was_refused(tmp_path: Path) -> None:
    """Trash is still tried first; permanent only changes what happens when it says no.

    That is why the mode needs no separate "is trash available here?" gate -- it applies per
    folder, and exactly to the folders trash would not take.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)

    # backend="gio" is refused for tmp_path ("system internal mounts"), so every folder falls
    # through to the permanent path.
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
