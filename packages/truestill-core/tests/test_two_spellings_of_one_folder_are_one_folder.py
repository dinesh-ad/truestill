"""A symlinked path is the same folder, and the product must say so. `(aeb)`, restore stage 3.

⚠ **THIS IS LIVE ON THE MAINTAINER'S MACHINE.** `/home/dinesh/TruestillLibrary` is a symlink to
`/data/TruestillLibrary`. Both spellings are real, both get typed at different times, and they are
one folder. `(aeb)` found the first casualty on `truestill catalog`, which reported a correctly
placed catalog as being *"in the old location"* and advised a `--move` that could not help.

**Real symlinks, never a mock.** A fake that returns a fixed answer would assert the test's own
idea of the filesystem rather than the filesystem's; `os.symlink` is what the defect happens
through, so it is what this uses.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest
from truestill_core.app_paths import is_same_file, is_same_location
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker, drive_path_hint, ghost_drive_at, read_marker
from truestill_core.recover import RecoverPair, recover_into_library

#: ⚠ **SKIPPED LOUDLY, NEVER PASSING SILENTLY.** Windows can make a directory symlink only with
#: SeCreateSymbolicLinkPrivilege or Developer Mode, so an unprivileged runner raises `OSError`.
#: A test that swallowed that would report green on the platform where it proved nothing.
_SYMLINKS = pytest.mark.skipif(
    sys.platform == "win32", reason="a directory symlink needs a privilege CI does not grant"
)


@pytest.fixture
def two_spellings(tmp_path: Path) -> tuple[Path, Path]:
    """``(real, link)`` - one folder reachable by two paths, as on the maintainer's machine."""
    real = tmp_path / "data" / "TruestillLibrary"
    real.mkdir(parents=True)
    home = tmp_path / "home"
    home.mkdir()
    link = home / "TruestillLibrary"
    link.symlink_to(real)
    assert link.is_symlink(), "the fixture made no symlink, so nothing below is about one"
    assert str(link) != str(real), "the two spellings are identical; the test proves nothing"
    return real, link


@_SYMLINKS
def test_two_spellings_of_one_folder_are_the_same_location(
    two_spellings: tuple[Path, Path],
) -> None:
    """The whole point, and every cheaper comparison is shown failing beside it."""
    real, link = two_spellings

    assert is_same_location(link, real)
    # The instruments that do NOT answer this, so the assertion above is not free.
    assert str(link) != str(real)
    assert link != real
    assert os.path.normpath(link) != os.path.normpath(real)


@_SYMLINKS
def test_two_genuinely_different_folders_are_still_different(
    two_spellings: tuple[Path, Path],
) -> None:
    """⚠ **The half that makes the other one mean something.** A comparison that said True for
    everything would satisfy the test above perfectly."""
    real, link = two_spellings
    other = real.parent / "SomewhereElse"
    other.mkdir()

    # ⚠ The positive anchor first: without it every assertion below is satisfied by an
    # implementation that answers False to everything, which is the other way to be useless.
    assert is_same_location(link, real)
    assert not is_same_location(link, other)
    assert not is_same_location(real, other)


def test_a_folder_that_does_not_exist_yet_is_the_same_as_itself(tmp_path: Path) -> None:
    """⚠ **THE REGRESSION `is_same_file` ALONE WOULD HAVE SHIPPED.**

    It compares device and inode, so it answers **False for a path against itself** when that
    path is not there. The first-run flow accepts a library folder before it exists and says so,
    so a comparison built on inodes alone would stop matching a declared library against itself
    until the folder was created.
    """
    ghost = tmp_path / "not-created-yet"

    assert not ghost.exists()
    assert is_same_file(ghost, ghost) is False, "the trap this exists for has moved"
    assert is_same_location(ghost, ghost)
    assert is_same_location(ghost, tmp_path / "." / "not-created-yet")


def test_a_path_that_is_not_there_is_not_every_other_path(tmp_path: Path) -> None:
    """The cry-wolf half of the test above: the lexical arm must not make absence universal."""
    assert is_same_location(tmp_path / "missing-a", tmp_path / "missing-a"), "the anchor"
    assert not is_same_location(tmp_path / "missing-a", tmp_path / "missing-b")


@_SYMLINKS
def test_a_broken_link_answers_rather_than_raising(tmp_path: Path) -> None:
    """⚠ **A comparison that throws where it used to answer is a worse failure than the one being
    fixed** - which is why this never resolves both sides. A link to nowhere is an ordinary state
    on a machine with an unplugged drive, and it must produce `False`, not an exception."""
    broken = tmp_path / "broken"
    broken.symlink_to(tmp_path / "nowhere")
    real = tmp_path / "real"
    real.mkdir()

    assert broken.is_symlink()
    assert not is_same_location(broken, real)


def test_trailing_slashes_and_dot_segments_do_not_make_two_folders(tmp_path: Path) -> None:
    """The lexical arm's own job, on a path that does exist."""
    here = tmp_path / "Library"
    here.mkdir()

    assert is_same_location(here, Path(f"{here}/"))
    assert is_same_location(here, here / ".")
    assert is_same_location(here, here.parent / "." / "Library")


# ------------------------------------------------------- the guard that fails OPEN without this


@_SYMLINKS
def test_the_ghost_guard_recognises_a_drive_recorded_by_its_other_spelling(
    two_spellings: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """⚠ **`(aap)` - and a string compare made this guard fail OPEN.**

    `ghost_drive_at` refuses to mint a drive id where a known drive was recorded and its marker
    is gone. Recorded as `/data/X`, pointed at as `~/X`, the string compare did not match, the
    refusal never fired, and truestill would have minted a SECOND id for a library it already
    had - counting one copy of the user's photographs as two.
    """
    real, link = two_spellings
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u1", label="My Library")
        catalog.set_setting(drive_path_hint("u1"), str(real))

        ghost = ghost_drive_at(link, catalog, [("u1", "My Library")])

    assert ghost is not None, "the ghost guard did not recognise the drive by its other spelling"
    assert ghost.label == "My Library"


@_SYMLINKS
def test_the_ghost_guard_still_ignores_an_unrelated_folder(
    two_spellings: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """The anti-cry-wolf half: a guard that matched everything would refuse every new drive."""
    real, _link = two_spellings
    stranger = tmp_path / "SomewhereElse"
    stranger.mkdir()
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u1", label="My Library")
        catalog.set_setting(drive_path_hint("u1"), str(real))

        assert ghost_drive_at(stranger, catalog, [("u1", "My Library")]) is None


def test_the_ghost_guard_still_matches_an_unmounted_drive(tmp_path: Path) -> None:
    """⚠ **The case `is_same_file` ALONE would have broken, and it is the commonest ghost.**

    An unmounted drive's folder is gone, so there is no inode to compare - and the whole point of
    the guard is to refuse where a drive *was*. The lexical arm is what keeps it firing.
    """
    gone = tmp_path / "media" / "Backup"
    with Catalog(tmp_path / "c.sqlite") as catalog:
        catalog.upsert_drive(uuid="u1", label="Backup")
        catalog.set_setting(drive_path_hint("u1"), str(gone))

        assert not gone.exists()
        assert ghost_drive_at(gone, catalog, [("u1", "Backup")]) is not None


# ------------------------------------------ the refusal a symlink COULD have fooled, and does not


@_SYMLINKS
def test_recovering_a_drive_into_itself_through_a_symlink_is_still_refused(
    two_spellings: tuple[Path, Path],
    tmp_path: Path,
) -> None:
    """⚠ **THE DANGEROUS ONE, AND IT WAS NEVER A PATH COMPARISON.**

    A recover that could be fooled into running a drive into itself would copy a library over
    itself. It cannot be: every same-drive refusal in the product - `recover` and `backup`, in
    core, the CLI and the app - compares the two MARKER UUIDS, never the two paths. Both
    spellings reach one folder, which holds one `.truestill-drive.json`, which yields one uuid.

    Asserted through the real engine rather than by reading the comparison, because "it compares
    uuids" is an argument and this is evidence.
    """
    real, link = two_spellings
    db = tmp_path / "c.sqlite"
    marker = create_marker(real, label="My Library")
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
    via_real, via_link = read_marker(real), read_marker(link)
    assert via_real is not None
    assert via_link is not None
    assert via_real.uuid == via_link.uuid, "two spellings read two identities; the premise is gone"

    with pytest.raises(ValueError, match="same drive"):
        recover_into_library(
            RecoverPair(
                drive=link,
                drive_marker=via_link,
                library=real,
                library_marker=via_real,
            ),
            db,
            progress=lambda _p: None,
            cancel=threading.Event(),
        )


def test_a_tilde_and_its_expansion_are_one_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ **A MUTATION FOUND THIS UNPROVEN.** `_spelling` expands `~` and nothing asserted it, so
    dropping `expanduser()` survived the whole suite.

    It matters because the two spellings reach this comparison from different places: a drive
    hint is written from a resolved path by the code, and a declared library root is whatever the
    user typed - and `~/Photos` is what a person types.

    HOME is redirected rather than the real one used: a test that expanded to the developer's
    actual home would assert something about this machine.
    """
    home = tmp_path / "home"
    (home / "Photos").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))  # Windows' spelling of the same thing

    assert is_same_location(Path("~/Photos"), home / "Photos")
    assert not is_same_location(Path("~/Photos"), home / "Elsewhere")


def test_a_dot_dot_segment_in_a_path_that_is_not_there_still_names_one_folder(
    tmp_path: Path,
) -> None:
    """⚠ **A MUTATION FOUND `normpath` UNPROVEN**, because the trailing-slash test above uses
    paths that EXIST - so the inode arm answers first and the lexical arm is never reached.

    Measured, `normpath` adds exactly one thing over `str(Path(x))`: collapsing `..`. Everything
    else `Path` already settles. So this is the only case that can prove it, and it has to use a
    path that is not there.
    """
    ghost = tmp_path / "library"
    assert not ghost.exists(), "the inode arm would answer first and prove nothing"

    assert is_same_location(ghost, tmp_path / "sibling" / ".." / "library")
    assert not is_same_location(ghost, tmp_path / "sibling" / ".." / "elsewhere")
