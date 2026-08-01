"""The session URL is a credential, and not every filesystem can keep one.

**The gap.** `session_link.write` creates the file with mode ``0600`` and never checked that the
mode took. FAT32 and exFAT store no per-file access control at all: the mode is accepted,
ignored, and the file is readable by every account on the machine. A portable install, a live
USB, or a home directory on a removable drive puts the app's data directory exactly there.

**The ruling: warn, keep writing.** Refusing would restore the precise bug (aad) closed - a
running, listening, unreachable app whose token is minted per process and printed to a console a
double-clicked app does not have. Trading a confidentiality weakening for a total loss of access
is the worse deal. Writing it *elsewhere* was rejected because `app_paths` owns where every such
file lives, and a credential that moves to an unpredictable second location is harder to find
and harder to clean up than one that is where it always is and says what it could not do.

**Why this file is split in two, which the first version was not.** The first version read the
POSIX mode back and called that "is it private". On Windows CPython *synthesizes* ``st_mode``,
so it reported every file as world-readable and would have fired this warning on every Windows
start, on NTFS, where the profile ACL does protect the file - caught by the Windows lane, which
is the only place it could be. Detecting and deciding are now separate: the **policy** tests
below patch the answer and run everywhere, and the **detection** tests exercise each platform's
own mechanism where that platform can run them.
"""

from __future__ import annotations

import stat
import sys
from pathlib import Path

import pytest
from truestill_app import session_link
from truestill_core.filesystem import FilesystemFacts, stores_access_control

_URL = "http://127.0.0.1:7357/?token=secret-token-value"


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the session file at a temp directory, on the module that owns the answer.

    Without this the test writes a real credential into the user's own data directory - the
    mutation-hermeticity failure recorded beside guard rule 5.
    """
    target = tmp_path / "data" / "session-url.txt"
    monkeypatch.setattr(session_link, "path", lambda: target)
    return target


def _cannot_keep_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer "this filesystem cannot keep a file private" at the detect/decide seam.

    Patched at the seam rather than by faking a mode or a volume name, because the policy is
    what these tests are about and it must not depend on which platform is running them.
    """
    monkeypatch.setattr(session_link, "_is_private", lambda _target: False)


# --- the policy: what happens once the answer is known ------------------------------------


def test_a_filesystem_that_can_keep_secrets_reports_the_file_as_private(
    isolated_home: Path,
) -> None:
    """The ordinary case on every platform - a temp directory on an ordinary volume. Pinned so
    the warning cannot start firing for everyone, which is exactly what it did on Windows."""
    link = session_link.write(_URL)

    assert link.private is True
    assert "could not be made private" not in isolated_home.read_text()


def test_the_file_itself_says_it_could_not_be_made_private(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reader of this file is someone whose browser did not open. It is the one place the
    warning is certain to be seen, because a console is exactly what they do not have."""
    _cannot_keep_secrets(monkeypatch)

    session_link.write(_URL)

    text = isolated_home.read_text()
    assert "could not be made private" in text
    assert _URL in text, "the warning replaced the way back in rather than accompanying it"


def test_the_url_is_still_written_because_refusing_would_lock_the_user_out(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ruling, asserted rather than left to the commit message: a weakened credential beats
    an app that is running and unreachable, which is the bug this file exists to close."""
    _cannot_keep_secrets(monkeypatch)

    link = session_link.write(_URL)

    assert link.private is False
    assert link.path.is_file()
    assert isolated_home.read_text().startswith(_URL)


# --- the detection: each platform's own mechanism -----------------------------------------


def test_privacy_is_judged_on_other_users_access_not_on_an_exact_mode() -> None:
    """0400 and 0600 are both private; 0640 is not. Asserting an exact mode would refuse a
    correct file and would still say nothing about the question actually being asked."""
    assert session_link.mode_is_private(0o600) is True
    assert session_link.mode_is_private(0o400) is True
    assert session_link.mode_is_private(0o640) is False
    assert session_link.mode_is_private(0o604) is False
    assert session_link.mode_is_private(0o777) is False


def test_only_the_filesystems_that_store_no_access_control_are_called_out() -> None:
    """The Windows-side question. exFAT belongs here even though it is *not* in the FAT
    4 GiB-limit family: the two questions have different answers and must not share a list."""
    assert stores_access_control("exfat") is False
    assert stores_access_control("FAT32") is False
    assert stores_access_control("vfat") is False
    assert stores_access_control("NTFS") is True
    assert stores_access_control("ext4") is True
    assert stores_access_control(None) is True, "unknown must never cry wolf"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes are synthesized on Windows")
@pytest.mark.usefixtures("isolated_home")
def test_on_posix_a_mode_ignoring_filesystem_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A vfat mount reports whatever its fmask says - commonly 0777. Simulated by reporting
    that mode, because creating a real FAT32 filesystem needs root and a loopback mount."""
    real_stat = Path.stat

    def fat_stat(self: Path, **kwargs: object) -> object:
        return _ModeOverride(real_stat(self, **kwargs), stat.S_IFREG | 0o777)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "stat", fat_stat)

    assert session_link.write(_URL).private is False


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows volume-type mechanism")
@pytest.mark.usefixtures("isolated_home")
def test_on_windows_the_volume_type_decides_rather_than_the_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The regression this file was rewritten for.

    The mode is synthesized on Windows, so it must not be consulted: an exFAT stick has to be
    detected, and NTFS must **not** be reported as exposed. Patched on `session_link`, which is
    where the call is made from - guard rule 3.
    """
    monkeypatch.setattr(
        session_link,
        "facts_for",
        lambda _target: FilesystemFacts(filesystem="exFAT", max_file_bytes=None),
    )
    assert session_link.write(_URL).private is False

    monkeypatch.setattr(
        session_link,
        "facts_for",
        lambda _target: FilesystemFacts(filesystem="NTFS", max_file_bytes=None),
    )
    assert session_link.write(_URL).private is True


@pytest.mark.usefixtures("isolated_home")
def test_the_windows_branch_consults_the_volume_and_not_the_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runs everywhere, by faking the platform rather than the filesystem.

    The Windows lane is the only place the real mechanism can run, and a lane that runs after a
    push is a poor place to learn that a branch was wired to the wrong input. So the *selection*
    is proved here: with the platform reporting Windows, the mode is made to look world-readable
    **and** the volume is made to look like NTFS. Only one of those can win, and the answer says
    which - guard rule 8, where two mechanisms could produce the same outcome and only
    provenance distinguishes them.
    """
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(
        session_link,
        "facts_for",
        lambda _target: FilesystemFacts(filesystem="NTFS", max_file_bytes=None),
    )
    real_stat = Path.stat

    def world_readable(self: Path, **kwargs: object) -> object:
        return _ModeOverride(real_stat(self, **kwargs), stat.S_IFREG | 0o777)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "stat", world_readable)

    assert session_link.write(_URL).private is True, (
        "the Windows branch read the synthesized mode instead of the volume type"
    )


class _ModeOverride:
    """A stat result with ``st_mode`` replaced; everything else passes through."""

    def __init__(self, wrapped: object, mode: int) -> None:
        self._wrapped = wrapped
        self.st_mode = mode

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)
