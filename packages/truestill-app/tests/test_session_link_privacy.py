"""The session URL is a credential, and on some filesystems ``0600`` silently does nothing.

**The gap.** `session_link.write` creates the file with mode ``0600`` and never checked that the
mode took. FAT32 and exFAT have no POSIX permission bits at all: the mode is accepted, ignored,
and the file reports whatever the mount's ``fmask`` says - commonly ``0777``. A portable install,
a live USB, or a home directory on a removable drive puts the app's data directory exactly
there, and the token that reaches the whole library would be readable by every account on the
machine with nothing said about it.

**The ruling taken: warn, keep writing.** Refusing to write would restore the precise bug (aad)
closed - a running, listening, unreachable app whose token is minted per process and printed to
a console a double-clicked app does not have. Trading a confidentiality weakening for a total
loss of access is the worse deal, and it is not the user's to lose silently either way. Writing
it *elsewhere* was rejected because `app_paths` owns where every such file lives, and a
credential that moves to an unpredictable second location is harder to find and harder to clean
up than one that is where it always is and says what it could not do.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from truestill_app import session_link

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


def test_a_filesystem_that_honours_modes_reports_the_file_as_private(isolated_home: Path) -> None:
    """The ordinary case, pinned so the warning cannot start firing for everyone."""
    link = session_link.write(_URL)

    assert link.private is True
    assert stat.S_IMODE(isolated_home.stat().st_mode) == 0o600
    assert "could not be made private" not in isolated_home.read_text()


@pytest.mark.usefixtures("isolated_home")
def test_a_mode_ignoring_filesystem_is_detected_rather_than_assumed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAT32 accepts the mode, ignores it, and reports 0777. Simulated by reporting that mode,
    because creating a real FAT32 filesystem needs root and a loopback mount."""
    _pretend_fat(monkeypatch)

    link = session_link.write(_URL)

    assert link.private is False, "a world-readable credential was reported as private"


def test_the_file_itself_says_it_could_not_be_made_private(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The reader of this file is someone whose browser did not open. It is the one place the
    warning is certain to be seen, because a console is exactly what they do not have."""
    _pretend_fat(monkeypatch)

    session_link.write(_URL)

    text = isolated_home.read_text()
    assert "could not be made private" in text
    assert _URL in text, "the warning replaced the way back in rather than accompanying it"


def test_the_url_is_still_written_because_refusing_would_lock_the_user_out(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ruling, asserted rather than left to the commit message: a weakened credential beats
    an app that is running and unreachable, which is the bug this file exists to close."""
    _pretend_fat(monkeypatch)

    link = session_link.write(_URL)

    assert link.path.is_file()
    assert isolated_home.read_text().startswith(_URL)


def test_privacy_is_judged_on_other_users_access_not_on_an_exact_mode() -> None:
    """0400 and 0600 are both private; 0640 is not. Asserting an exact mode would refuse a
    correct file and would say nothing about the question actually being asked."""
    assert session_link.mode_is_private(0o600) is True
    assert session_link.mode_is_private(0o400) is True
    assert session_link.mode_is_private(0o640) is False
    assert session_link.mode_is_private(0o604) is False
    assert session_link.mode_is_private(0o777) is False


def _pretend_fat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report every mode as 0777, the way a vfat mount with the default fmask does."""
    real_stat = Path.stat

    def fat_stat(self: Path, **kwargs: object) -> object:
        result = real_stat(self, **kwargs)  # type: ignore[arg-type]
        return _ModeOverride(result, stat.S_IFREG | 0o777)

    monkeypatch.setattr(Path, "stat", fat_stat)


class _ModeOverride:
    """A stat result with ``st_mode`` replaced; everything else passes through."""

    def __init__(self, wrapped: object, mode: int) -> None:
        self._wrapped = wrapped
        self.st_mode = mode

    def __getattr__(self, name: str) -> object:
        return getattr(self._wrapped, name)
