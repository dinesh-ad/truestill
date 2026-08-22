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


def _skeleton_with_junk(root: Path) -> list[str]:
    """The same skeleton, with one month holding OS junk.

    ⚠ **Every trash-refusal test needs this, and until 2026-08-22 none of them had it.** Removal
    now sends a folder's *junk* to the trash and the folder itself to ``rmdir``, so a plan of
    nothing but empty folders never calls the trash at all - and a test that makes the trash
    refuse over `_skeleton` asserts nothing about refusal. `(afj)`
    """
    emptied = _skeleton(root)
    (root / "Camera/2013/09/.DS_Store").touch()
    return emptied


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

    ⚠ **`_skeleton_with_junk`, and the reason is the whole of `(afj)`.** What reaches the trash is
    now a folder's junk, not the folder, so over a plan of empty folders this test would make a
    refusal that nothing ever asks for. The empty siblings are asserted separately below: they
    never needed a trash, so a refused one does not stop them.
    """
    root = tmp_path / "drive"
    emptied = _skeleton_with_junk(root)
    _refusing_trash(monkeypatch)

    plan = plan_cleanup(root, emptied)
    outcome = run_cleanup(root, plan, apply=True, backend="gio")

    assert (root / "Camera/2013/09").is_dir(), "a refused folder was removed anyway"
    assert (root / "Camera/2013/09/.DS_Store").exists(), "junk went somewhere despite the refusal"
    assert outcome.discarded == 0, "a refusal was downgraded to an outright removal"
    assert any(f.startswith("Camera/2013/09:") for f in outcome.failures)
    # The folder that held the junk survives; the branch that never needed a trash collapses.
    assert not (root / "Camera/2014/01").exists()
    assert not (root / "Camera/2014").exists()
    # ⚠ And the refusal CASCADES, which is the honest outcome rather than an awkward one: a kept
    # folder keeps its parents non-empty, so they are refused too - each by name, each with the
    # real reason. `Camera/2013` and `Camera` are those parents.
    assert (root / "Camera/2013").is_dir()
    assert (root / "Camera").is_dir()
    assert {f.split(":")[0] for f in outcome.failures} == {
        "Camera/2013/09",
        "Camera/2013",
        "Camera",
    }
    assert outcome.removed == 3


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
    assert outcome.discarded == 0
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
    emptied = _skeleton_with_junk(root)  # a refusal needs something to refuse -- see `(afj)`

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

    assert (root / "Camera/2013/09").is_dir(), "a folder went with a refusal we said we handled"
    assert (root / "Camera/2013/09/.DS_Store").exists()
    assert outcome.discarded == 0
    # Told, not silently skipped: the folder that was left alone is named.
    assert any(f.startswith("Camera/2013/09:") for f in outcome.failures)


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

    assert outcome.removed == 6
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

    ⚠ **This test asserted nothing at all between 2026-08-22 and the commit that added the junk.**
    Over `_skeleton` every candidate is `Tier.EMPTY`, so after `(afj)` the trash is never called,
    no refusal ever happens, and `permanent` is never consulted - yet the folders all came away
    and every assertion here was green *for the wrong reason*. §4's fifty-fourth member, in a test
    whose entire subject is the branch it had stopped reaching.

    What `--permanent` now governs is the **junk**: it is the only thing a trash can refuse.
    """
    root = tmp_path / "drive"
    emptied = _skeleton_with_junk(root)
    _refusing_trash(monkeypatch)  # so the junk falls through to the permanent path

    outcome = run_cleanup(
        root, plan_cleanup(root, emptied), apply=True, backend="gio", permanent=True
    )

    # The refusal was overridden for the junk, which is the flag's whole remaining effect.
    assert outcome.discarded == 1
    assert not (root / "Camera/2013/09/.DS_Store").exists()
    assert outcome.removed == 6
    assert not outcome.failures
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


def _recording_trash(monkeypatch: pytest.MonkeyPatch, bin_dir: Path) -> list[Path]:
    """A trash that really MOVES what it is given, into ``bin_dir``. Returns what it took.

    ⚠ **A no-op fake cannot catch `(afj)`.** The symptom being tested is that a *folder moved*; a
    fake that records and does nothing leaves the folder where it was, so the assertion "the
    folder is still there" would pass against the very code that takes it. This performs the real
    happy path -- `os.replace`, which is what `send2trash` does when the source and the trash share
    a filesystem, measured -- so a folder that is wrongly handed over really does disappear.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    taken: list[Path] = []

    def take(path: Path, _backend: str) -> None:
        taken.append(path)
        path.replace(bin_dir / f"{len(taken)}-{path.name}")

    monkeypatch.setattr(cleanup, "_to_trash", take)
    return taken


def test_trash_removal_cannot_take_a_folder_that_gained_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ The twin `test_permanent_removal_cannot_delete_a_folder_that_gained_a_file` never had.

    That test pins the rmdir guarantee with ``backend=None, permanent=True``, so it has only ever
    exercised `_remove_permanently`. The **default** path had no such guarantee and no such test:
    `send2trash` has no emptiness precondition, so a folder that gained a file between the plan
    and the confirm was handed over whole, file and all. Measured in soak four, D7. `(afj)`
    """
    root = tmp_path / "drive"
    emptied = _skeleton_with_junk(root)
    taken = _recording_trash(monkeypatch, tmp_path / "bin")
    plan = plan_cleanup(root, emptied)

    # The race, after the plan is made and before the removal runs.
    appeared = root / "Camera/2013/09/appeared.jpg"
    appeared.write_bytes(b"a photo the preview never named")

    outcome = run_cleanup(root, plan, apply=True, backend="send2trash")

    assert appeared.read_bytes() == b"a photo the preview never named", (
        "a file the preview never named was removed from the user's drive"
    )
    assert (root / "Camera/2013/09").is_dir()
    assert not any(p.name == "09" for p in taken), "the FOLDER was handed to the trash"
    assert any(f.startswith("Camera/2013/09:") for f in outcome.failures)
    # ⚠ And the residue is better than either path produced before: the junk is recoverable.
    assert [p.name for p in taken] == [".DS_Store"]
    assert not (root / "Camera/2013/09/.DS_Store").exists()


def test_an_empty_folder_never_reaches_the_trash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The positive form of "no folder is ever trashed", so a refactor cannot quietly undo it."""
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    taken = _recording_trash(monkeypatch, tmp_path / "bin")

    outcome = run_cleanup(root, plan_cleanup(root, emptied), apply=True, backend="send2trash")

    assert taken == [], "an empty folder has nothing to recover; the trash was consulted anyway"
    assert outcome.removed == 6
    assert not (root / "Camera").exists()


def test_junk_already_in_the_trash_is_named_when_the_rmdir_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`(afk)`, on the path this change creates it for.

    A folder whose junk reached the trash and whose ``rmdir`` then refused is a state no previous
    version could produce. Reported as a bare *"directory not empty"* it reads as *nothing
    happened here*, which is `(aez)`'s shape: a partial destructive action describing itself as
    none.
    """
    root = tmp_path / "drive"
    emptied = _skeleton_with_junk(root)
    _recording_trash(monkeypatch, tmp_path / "bin")
    plan = plan_cleanup(root, emptied)
    (root / "Camera/2013/09/appeared.jpg").write_bytes(b"x")

    outcome = run_cleanup(root, plan, apply=True, backend="send2trash")

    line = next(f for f in outcome.failures if f.startswith("Camera/2013/09:"))
    assert "not removed" in line
    assert "directory not empty" in line
    assert ".DS_Store" in line, "the junk that DID go is not mentioned, so the line reads as 'none'"
    assert "in the trash" in line


def test_junk_that_vanished_before_the_apply_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``unlink(missing_ok=True)``'s tolerance, preserved across a backend that cannot offer it.

    `_remove_permanently` shrugged at junk that disappeared between the plan and the apply -- and
    it makes the ``rmdir`` MORE likely to succeed, not less. `send2trash` raises on a missing path
    and `gio` exits non-zero, so without this the tidiest possible case became a reported failure.
    """
    root = tmp_path / "drive"
    emptied = _skeleton_with_junk(root)
    _recording_trash(monkeypatch, tmp_path / "bin")
    plan = plan_cleanup(root, emptied)
    (root / "Camera/2013/09/.DS_Store").unlink()  # the user, or another app, got there first

    outcome = run_cleanup(root, plan, apply=True, backend="send2trash")

    assert outcome.failures == []
    assert outcome.removed == 6


def test_a_folder_that_vanished_before_the_apply_is_not_reported_as_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The `is_dir()` pre-check's job, now done by ``rmdir``'s own errno after the act."""
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    _recording_trash(monkeypatch, tmp_path / "bin")
    plan = plan_cleanup(root, emptied)
    (root / "Camera/2014/01").rmdir()

    outcome = run_cleanup(root, plan, apply=True, backend="send2trash")

    assert outcome.failures == [], "a folder already gone is neither removed nor failed"
    assert outcome.removed == 5


def test_a_candidate_that_became_a_file_is_reported_not_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ The case the `is_dir()` pre-check swallowed in silence.

    A preview naming six folders could report five removed with nothing at all explaining the
    sixth, because `is_dir()` answered `False` and `continue` said nothing. `rmdir` answers
    ``ENOTDIR`` and the file survives, named.
    """
    root = tmp_path / "drive"
    emptied = _skeleton(root)
    _recording_trash(monkeypatch, tmp_path / "bin")
    plan = plan_cleanup(root, emptied)
    (root / "Camera/2014/01").rmdir()
    (root / "Camera/2014/01").write_bytes(b"not a folder any more")

    outcome = run_cleanup(root, plan, apply=True, backend="send2trash")

    assert (root / "Camera/2014/01").is_file(), "a file standing where a folder was got removed"
    assert any(f.startswith("Camera/2014/01:") for f in outcome.failures)


def test_a_discarded_count_never_includes_junk_that_had_already_gone(tmp_path: Path) -> None:
    """``discarded`` is a count of irreversible removals, so it must not count a no-op.

    The no-backend permanent path unlinks with ``missing_ok=True``. A junk file that vanished
    between the plan and the apply is not something this run destroyed, and saying it was would
    overstate the only number in the outcome that means *gone for good*.
    """
    root = tmp_path / "drive"
    emptied = _skeleton_with_junk(root)
    plan = plan_cleanup(root, emptied)
    (root / "Camera/2013/09/.DS_Store").unlink()

    outcome = run_cleanup(root, plan, apply=True, backend=None, permanent=True)

    assert outcome.discarded == 0
    assert outcome.removed == 6
