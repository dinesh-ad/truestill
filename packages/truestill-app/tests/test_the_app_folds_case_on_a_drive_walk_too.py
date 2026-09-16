"""The app's attach walk asks the same question `rescan` does. `(ala)`

⚠ **A STRUCTURAL TWIN IN A DIFFERENT PACKAGE, WITH NO SHARED CODE.** `service/drives.py`'s
`_unrecorded_files` compares a live `Path.walk` against `file_copies.relative`, exactly as
`rescan.reconcile` does, and was written independently. The census that raised this found the
same comparison spelled three times across three packages; `compare_key` is now the one home for
what it means, and this file is what stops the app drifting away from it again.

**What it costs when it is wrong**: the docstring's own promise - *"A file sitting where the
catalog already says it sits needs no read"* - fails open. Every file on a drive whose case has
drifted becomes a candidate for hashing, on the attach path that runs whenever a drive is
plugged in.
"""

from __future__ import annotations

from pathlib import Path

from truestill_app.service.drives import _unrecorded_files


def _library(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x" * 16)


def test_a_file_at_its_recorded_path_is_not_a_candidate(tmp_path: Path) -> None:
    """The cry-wolf half: without this, every assertion below is satisfied by a walk that
    returns nothing at all."""
    _library(tmp_path, "Saved/photo.jpg", "Saved/other.jpg")

    walk = _unrecorded_files(tmp_path, {"Saved/photo.jpg"})

    assert [p.name for p in walk.files] == ["other.jpg"]


def test_the_walk_returns_what_is_genuinely_unrecorded(tmp_path: Path) -> None:
    """The other direction, so folding cannot be implemented as "nothing is ever a candidate"."""
    _library(tmp_path, "Saved/photo.jpg")

    walk = _unrecorded_files(tmp_path, set())

    assert [p.name for p in walk.files] == ["photo.jpg"]


def test_a_case_drift_is_judged_the_way_the_mount_judges_it(tmp_path: Path) -> None:
    """⚠ **The assertion is tied to the FILESYSTEM's answer, not to a platform guess.**

    A `skipif(sys.platform != "win32")` here would run nowhere in CI and prove nothing - this
    repo already records a module-wide skip hiding a live instance. Instead the expectation is
    derived from the same question the code asks: if this filesystem folds, the drifted name is
    the recorded file and must not be a candidate; if it does not, it is a different file and
    must be. One assertion, correct on every lane, and on a macOS or Windows runner it exercises
    the folding branch for real.
    """
    _library(tmp_path, "Saved/photo.jpg")
    folds = (tmp_path / "Saved/PHOTO.JPG").exists()

    walk = _unrecorded_files(tmp_path, {"Saved/PHOTO.JPG"})

    assert [p.name for p in walk.files] == ([] if folds else ["photo.jpg"])


def test_an_unreadable_folder_is_still_reported(tmp_path: Path) -> None:
    """The probe runs over the walk's results, so it must not disturb the error path it shares.

    `_note_unreadable` is why `Path.walk` was chosen over `rglob` in the first place - measured
    at three files present and zero rows - and reordering the walk to collect first could have
    dropped it.
    """
    _library(tmp_path, "Saved/photo.jpg")
    locked = tmp_path / "Locked"
    locked.mkdir()
    (locked / "inner.jpg").write_bytes(b"x")
    locked.chmod(0o000)
    try:
        walk = _unrecorded_files(tmp_path, set())
    finally:
        locked.chmod(0o755)

    assert walk.unreadable_dirs == ("Locked",)
    assert [p.name for p in walk.files] == ["photo.jpg"]


def test_both_surfaces_ask_the_same_question() -> None:
    """The anti-drift assertion: read the source rather than trusting a reviewer noticed.

    The census's finding was that this comparison exists three times with no shared code. It now
    has one: whatever else changes, both surfaces must route through `compare_key` and both must
    decide by asking the mount rather than by naming a platform.
    """
    root = Path(__file__).resolve().parents[3]
    app = (root / "packages/truestill-app/src/truestill_app/service/drives.py").read_text(
        encoding="utf-8"
    )
    cli = (root / "packages/truestill-cli/src/truestill_cli/cli.py").read_text(encoding="utf-8")

    for surface in (app, cli):
        assert "compare_key" in surface
        assert "folds_case(" in surface
        assert "sys.platform" not in surface.split("folds_case(")[1][:400], (
            "the fold is being decided by platform rather than by the mount"
        )
