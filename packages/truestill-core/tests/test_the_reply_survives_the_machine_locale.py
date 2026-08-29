"""The door decodes text replies as UTF-8, whatever the machine locale says. `(aic)`.

The subject is `binaries._pin_text_decoding`, observed through its real consumers rather than
asserted from a table. The hostile environment below (``LC_ALL=C``, ``PYTHONUTF8=0``,
``PYTHONCOERCECLOCALE=0``) forces the ambient preferred encoding off UTF-8 on POSIX - the same
seam Windows sits on ambiently with cp1252 - so the child tests bite on **every** platform with
no platform conditional. Measured before the fix: the read child died with a
``UnicodeDecodeError`` out of ``subprocess.communicate``, which on a cp1252 machine is instead a
silently mojibaked ``SourceFile`` and a correctly-dated photograph filed ``Undated/``.

⚠ The hostile environment moves Python's *filesystem* decoding too, not only the pipe's - under
``LC_ALL=C`` an ``é`` filename becomes surrogates in ``str(path)`` while the fixed door decodes
the reply to the real ``é``, so a filename-keying assertion cannot pass under it **by
construction** (measured 2026-08-29). That is why the hostile children below carry their
non-ASCII in a tag value and a listing, never in the fixture's name, and the filename-keying
test runs under the ambient environment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from truestill_core import binaries
from truestill_core.exif import read_metadata, write_metadata_batch

_NEEDS_EXIFTOOL = pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="exiftool not installed"
)

#: Inert on Windows - there the ANSI code page IS the ambient hostility these vars simulate.
_HOSTILE = {"LC_ALL": "C", "LANG": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"}

_READ_CHILD = """\
import json, sys
from pathlib import Path
from truestill_core.exif import read_metadata

path = Path(sys.argv[1])
hit = read_metadata([path]).get(path, {})
print(json.dumps({"model": hit.get("Model"), "date": hit.get("DateTimeOriginal")}))
"""

_LIST_CHILD = """\
import json, sys
from truestill_core.destinations.rclone import RcloneDestination

dest = RcloneDestination("remote:photos", binary=sys.argv[1])
print(json.dumps({"listing": dest.list()}))
"""


def _hostile_child(script: Path, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, **_HOSTILE},
        check=False,
        timeout=120,
    )


def _photo_with_reunion_metadata(path: Path) -> None:
    """A real JPEG whose ``Model`` carries an ``é``, written through the product's own bake door.

    The argfile route on purpose: a non-ASCII *value* on the command line would transit Windows
    argv through the console code page - the separate input-side defect `(aif)` - and this file's
    subject is the reply. Inside the argfile the value is UTF-8 bytes, the documented form.
    """
    Image.new("RGB", (32, 32), (120, 30, 200)).save(path, "JPEG")
    verdicts = write_metadata_batch(
        [(path, ["-overwrite_original", "-Model=Réunion", "-DateTimeOriginal=2019:07:12 10:30:00"])]
    )
    assert verdicts == {path: True}


@_NEEDS_EXIFTOOL
def test_a_tag_value_survives_a_hostile_locale(tmp_path: Path) -> None:
    """The biting proof for the door: delete its ``encoding=`` and this dies on any platform.

    The fixture's NAME is ASCII, so nothing here depends on how a filename transits argv
    (`(aif)`) - only on how the reply is decoded, which is exactly `(aic)`'s seam.
    """
    photo = tmp_path / "IMG_0001.jpg"
    _photo_with_reunion_metadata(photo)
    script = tmp_path / "read_child.py"
    script.write_text(_READ_CHILD, encoding="utf-8")

    done = _hostile_child(script, str(photo))

    assert done.returncode == 0, f"read_metadata failed under a hostile locale:\n{done.stderr}"
    assert json.loads(done.stdout) == {"model": "Réunion", "date": "2019:07:12 10:30:00"}


def test_rclone_listings_decode_as_utf8_regardless_of_locale(tmp_path: Path) -> None:
    """`destinations/rclone.py` parses FILENAMES out of ``lsf`` - a mojibaked listing makes
    ``exists()`` false for a file that exists, so backup re-uploads and verify reports missing.

    rclone's own docs pin the encoding: names are well-formed UTF-8 by construction (invalid
    bytes are replaced with a quoted representation before output - rclone.org/local/), so a
    UTF-8 decode is right for this consumer in its own right, not by analogy with exiftool.
    The stub prints a real ``é`` as UTF-8 bytes; no real remote is involved.
    """
    body = tmp_path / "stub_rclone.py"
    body.write_text(
        'import sys\nsys.stdout.buffer.write("Réunion 2019/photo.jpg\\n".encode("utf-8"))\n',
        encoding="utf-8",
    )
    if sys.platform == "win32":
        stub = tmp_path / "rclone-stub.bat"
        stub.write_text(f'@"{sys.executable}" "{body}" %*\n', encoding="ascii")
    else:
        stub = tmp_path / "rclone-stub"
        stub.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{body}" "$@"\n', encoding="ascii")
        stub.chmod(0o755)
    script = tmp_path / "list_child.py"
    script.write_text(_LIST_CHILD, encoding="utf-8")

    done = _hostile_child(script, str(stub))

    assert done.returncode == 0, f"rclone listing failed under a hostile locale:\n{done.stderr}"
    assert json.loads(done.stdout) == {"listing": ["Réunion 2019/photo.jpg"]}


@_NEEDS_EXIFTOOL
def test_a_non_ascii_filename_keys_the_result_by_its_real_path(tmp_path: Path) -> None:
    """`(aic)`'s misfile, end to end: the ``é`` file's metadata lands under its real path.

    Runs under the AMBIENT environment deliberately - the module docstring records why the
    hostile one cannot key by construction. This carried ``xfail(strict=False)`` on Windows
    while `(aif)` was open, and the lane answered: **XFAIL on run 33242186610** - the argv
    route really did lose the filename there. The read path now ships every argument to
    exiftool over stdin (`exif._run_via_stdin_argfile`), so this is a plain assertion on every
    platform: a Windows failure here is a regression of `(aif)`'s fix, not an open question.
    """
    photo = tmp_path / "Réunion.jpg"
    _photo_with_reunion_metadata(photo)

    metadata = read_metadata([photo])

    assert photo in metadata, f"real path missing; keys: {[str(k) for k in metadata]}"
    assert metadata[photo].get("DateTimeOriginal") == "2019:07:12 10:30:00"


def test_the_door_injects_utf8_only_when_text_is_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wiring, not behaviour - the hostile children above are the biting proof. This pins the
    injection deterministically on every platform, and for ``popen``, which no child exercises:
    text mode gets UTF-8 + surrogateescape, bytes mode is untouched, an explicit ``encoding=``
    is the call site's whole decision and is left alone.
    """
    seen: dict[str, object] = {}

    def capture_run(_command: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.clear()
        seen.update(kwargs)
        return subprocess.CompletedProcess(["x"], 0, "", "")

    monkeypatch.setattr(binaries.subprocess, "run", capture_run)

    binaries.run(["x"], capture_output=True, text=True)
    assert seen.get("encoding") == "utf-8"
    assert seen.get("errors") == "surrogateescape"

    binaries.run(["x"], capture_output=True)
    assert "encoding" not in seen
    assert "errors" not in seen

    binaries.run(["x"], capture_output=True, text=True, encoding="latin-1")
    assert seen.get("encoding") == "latin-1"
    assert "errors" not in seen

    def capture_popen(_command: object, **kwargs: object) -> None:
        seen.clear()
        seen.update(kwargs)

    monkeypatch.setattr(binaries.subprocess, "Popen", capture_popen)

    binaries.popen(["x"], text=True)
    assert seen.get("encoding") == "utf-8"
    assert seen.get("errors") == "surrogateescape"


def test_the_read_arguments_travel_on_stdin_with_the_charset_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DECLARATION guard, and it says so (`handoff-2026-08-27.md` names the convention).

    What it pins is only observable on Windows, which no lane runs with a non-ASCII fixture the
    hard way: `(aif)`'s measurement (XFAIL, run 33242186610) proved a filename on argv does not
    reach exiftool intact there. Asserted everywhere instead: the read command is ``-@ -`` with
    nothing after it, and the stdin argfile names ``-charset filename=utf8`` BEFORE the first
    filename line - options apply in order, so a charset after the paths armours nothing.
    """
    seen: dict[str, object] = {}

    def snoop(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen["command"] = [str(part) for part in command]
        seen["input"] = kwargs.get("input")
        return subprocess.CompletedProcess(list(command), 0, "[]", "")

    monkeypatch.setattr(binaries, "run", snoop)
    monkeypatch.setattr("truestill_core.exif.ensure_exiftool", lambda: "exiftool")
    photo = tmp_path / "Réunion.jpg"
    photo.write_bytes(b"not really a jpeg; nothing here reaches a real exiftool")

    read_metadata([photo])

    command = seen["command"]
    assert isinstance(command, list)
    assert command[1:] == ["-@", "-"], command
    lines = str(seen["input"]).splitlines()
    charset = lines.index("-charset")
    assert lines[charset + 1] == "filename=utf8"
    assert lines.index(str(photo)) > charset + 1
