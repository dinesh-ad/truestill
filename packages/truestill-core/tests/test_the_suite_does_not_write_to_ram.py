"""The suite's scratch is on a disk, not on a RAM-backed filesystem.

`/tmp` on the maintainer's machine is **tmpfs**. Measured 2026-08-23 from an empty `/tmp`:
`make test` writes 282 MB and the browser lane peaks at 716 MB, all of it disk-shaped data -
catalogs, rollback journals, copied media, every Playwright video and trace - held in RAM until
the kernel evicts something else to make room.

**This guards the redirect, not the volume.** The root `conftest.py` sets `TMPDIR` and
`tempfile.tempdir`; without *both*, half the routes leak back to the platform default -
`tempfile.tempdir` covers this process, `TMPDIR` covers every subprocess (the browsers,
`exiftool`, `uv`). A test that checked only one would pass against a half-applied fix.

**It skips where there is no scratch volume, and that is the CI answer rather than a hole.** No
runner has a `/data`, so `scratch_root()` returns `None` there and the platform default is
correct. The skip names which case it took, because a guard that goes quiet is indistinguishable
from one that passed - and `pytest_report_header` prints the same fact on every run.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from suite_scratch import PREFERRED_SCRATCH, scratch_root

_ROOT = scratch_root()
_NO_VOLUME = pytest.mark.skipif(
    _ROOT is None, reason=f"no scratch volume at {PREFERRED_SCRATCH} (the CI case)"
)


@_NO_VOLUME
def test_a_tmp_path_is_not_on_a_ram_backed_filesystem(tmp_path: Path) -> None:
    """The fixture every other test in this repo builds on."""
    assert _ROOT is not None
    assert tmp_path.is_relative_to(_ROOT), (
        f"tmp_path is {tmp_path}, not under the scratch volume {_ROOT} - the suite is writing "
        f"disk-shaped data wherever the platform puts temporary files"
    )


@_NO_VOLUME
def test_this_process_resolves_temporary_files_to_the_scratch_volume() -> None:
    """`tempfile.tempdir`, which `gettempdir` caches on first call.

    Separate from the subprocess case below on purpose: `TMPDIR` alone leaves this stale
    whenever something asked before `pytest_configure` ran, and the failure is silent.
    """
    assert _ROOT is not None
    assert Path(tempfile.gettempdir()) == _ROOT
    made = Path(tempfile.mkdtemp())
    try:
        assert made.is_relative_to(_ROOT), made
    finally:
        made.rmdir()


@_NO_VOLUME
def test_a_subprocess_inherits_the_scratch_volume() -> None:
    """`TMPDIR`, which is the only thing a child process reads.

    The children that matter are not hypothetical: `exiftool` writes an argfile per batch, and
    each browser writes a profile. Neither imports our `tempfile`.
    """
    assert _ROOT is not None
    proc = subprocess.run(
        [sys.executable, "-c", "import tempfile; print(tempfile.gettempdir())"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert Path(proc.stdout.strip()) == _ROOT, proc.stdout


@_NO_VOLUME
def test_the_windows_spellings_are_set_too() -> None:
    """`TEMP`/`TMP` are what a child reads on the platform this repo also ships to."""
    assert _ROOT is not None
    assert os.environ["TMPDIR"] == os.environ["TEMP"] == os.environ["TMP"] == str(_ROOT)


def test_an_explicitly_requested_root_that_cannot_be_made_raises_rather_than_falling_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The cry-wolf half, and the one asymmetry in `scratch_root`.

    An **absent** default volume is the CI case and falls back silently, on purpose. A root the
    caller **named** must not: writing somewhere other than where you were told is the failure
    this repo keeps filing entries about, and it leaves no trace to notice later.
    """
    blocked = tmp_path / "a-file-not-a-directory"
    blocked.write_text("")
    monkeypatch.setenv("TRUESTILL_TEST_TMPDIR", str(blocked / "child"))
    # NotADirectoryError on POSIX, NotADirectoryError/FileNotFoundError on Windows - the
    # subject is that it RAISES rather than which errno the platform picked.
    with pytest.raises(OSError, match=r"[Nn]ot a directory|cannot find|No such file"):
        scratch_root()


def test_an_absent_default_volume_falls_back_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half: CI must not go red for not having a `/data`."""
    monkeypatch.delenv("TRUESTILL_TEST_TMPDIR", raising=False)
    monkeypatch.setattr("suite_scratch.PREFERRED_SCRATCH", Path("/proc/no-such-volume/truestill"))
    assert scratch_root() is None
