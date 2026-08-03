"""`analyze` reaches dates and identical copies, with no destination and no catalog.

**The gap this closes.** Tier 0 shipped in commit 1, but dates and duplicates were reachable
only through `organize --dry-run`, which requires a **destination** the funnel's audience has
not chosen. The free tier stopped one tier short of its own headline number.

**The sequencing is the ruling, and it is what these tests mostly pin.** Tier 0 prints
*immediately* -- the sub-second answer that earns trust survives -- then the report says what
is coming and what it will cost, then the expensive tiers run. A user who wanted only the
census interrupts, and keeps everything already on screen.

**Tier 2b (look-alikes) does not run**, because it decodes every image where 2a reads only the
size-colliding minority. It stays *not yet analysed*, never zero.
"""

from __future__ import annotations

import inspect
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli import cli
from truestill_cli.cli import main
from truestill_core import organizer, scan
from truestill_core.hashing import perceptual_hash

pytestmark = pytest.mark.skipif(shutil.which("exiftool") is None, reason="exiftool not installed")


def _photo(path: Path, tint: int, when: datetime | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 32), (tint, 40, 90)).save(path, "JPEG")
    if when is not None:
        # exiftool, not Pillow: `getexif()[306]` writes DateTime, while the date chain reads
        # DateTimeOriginal. A fixture that wrote the wrong tag would test nothing.
        subprocess.run(
            [
                "exiftool",
                "-overwrite_original",
                "-q",
                "-m",
                f"-DateTimeOriginal={when:%Y:%m:%d %H:%M:%S}",
                str(path),
            ],
            check=True,
        )
    return path


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """Two identical files plus dated uniques - so 2a has something to find and 1 has dates."""
    root = tmp_path / "src"
    first = _photo(root / "a.jpg", 10, datetime(2011, 3, 2, 9, 0))
    twin = root / "b.jpg"
    twin.write_bytes(first.read_bytes())
    _photo(root / "c.jpg", 200, datetime(2019, 7, 14, 18, 30))
    _photo(root / "d.jpg", 90)
    return root


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = main(argv)
    return code, capsys.readouterr().out


# --- the new tiers actually arrive -------------------------------------------------------------


def test_dates_are_reported(library: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = _run(["analyze", str(library)], capsys)
    assert code == 0
    assert "2011-03-02" in out
    assert "2019-07-14" in out


def test_identical_copies_are_found_and_their_bytes_named(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _code, out = _run(["analyze", str(library)], capsys)
    # The RESULT line, not the forecast - the forecast also names identical copies, which is
    # the point of it, and a loose match would assert against the wrong sentence.
    line = next(line for line in out.splitlines() if line.strip().startswith("identical copies"))
    assert "1 file" in line, line


def test_no_destination_no_catalog_and_no_db_are_needed_for_the_deep_tiers(
    library: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The funnel's premise, extended to the tiers that used to require an organize preview."""
    before = {p for p in tmp_path.rglob("*") if p.suffix in {".sqlite", ".db"}}

    code, _out = _run(["analyze", str(library)], capsys)

    assert code == 0
    assert {p for p in tmp_path.rglob("*") if p.suffix in {".sqlite", ".db"}} == before
    with pytest.raises(SystemExit):
        main(["analyze", str(library), "--db", str(tmp_path / "c.sqlite")])
    assert "--db" in capsys.readouterr().err


# --- tier 2b must not run ------------------------------------------------------------------------


def test_no_perceptual_hashing_happens(
    library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Asserted on behaviour: the function that decodes every image is never called.

    Patched on `truestill_core.scan`, which is the module that *calls* it - patching
    `hashing.perceptual_hash` would leave `scan`'s own binding untouched (§4, the aiming rule).
    """
    calls: list[Path] = []

    def spy(path: Path, *args: object, **kwargs: object) -> str | None:
        calls.append(path)
        return perceptual_hash(path, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(scan, "perceptual_hash", spy)
    code, out = _run(["analyze", str(library)], capsys)

    assert code == 0
    assert calls == [], f"tier 2b ran for {len(calls)} file(s)"
    assert "look-alike" in out.lower()


def test_look_alikes_still_say_not_yet_analysed(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Partial truth: the tier that did not run is named, never rendered as zero."""
    _code, out = _run(["analyze", str(library)], capsys)
    assert "not yet analysed" in out.lower()
    tail = out.lower().split("not yet analysed", 1)[1]
    assert "look-alike" in tail
    assert "0 look-alike" not in out.lower()


# --- the sequencing, which is the whole ruling ---------------------------------------------------


def test_the_census_prints_before_the_expensive_work_starts(
    library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ordering, not presence. The sub-second answer must not wait behind the slow tiers.

    Captured at the moment the first expensive call happens, so a refactor that moved the
    census below it would fail here even though every number still appeared.
    """
    seen_at_hash: list[str] = []
    real = scan.compute_hashes

    def spy(*args: object, **kwargs: object) -> object:
        seen_at_hash.append(capsys.readouterr().out)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(scan, "compute_hashes", spy)
    monkeypatch.setattr(organizer, "compute_hashes", spy)
    _run(["analyze", str(library)], capsys)

    assert seen_at_hash, "hashing never ran"
    already = seen_at_hash[0]
    assert "files found" in already, "the census had not printed before hashing began"
    # The forecast legitimately names identical copies before the wait; what must NOT have
    # printed yet is the RESULT line, which is indented and colon-aligned.
    assert not any(line.strip().startswith("identical copies") for line in already.splitlines()), (
        "the duplicate result printed before hashing ran"
    )


def test_the_forecast_and_the_interrupt_hint_appear_before_the_wait(
    library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unexplained wait becomes an informed one - the reason the forecast exists."""
    seen: list[str] = []
    real = scan.compute_hashes

    def spy(*args: object, **kwargs: object) -> object:
        seen.append(capsys.readouterr().out)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(scan, "compute_hashes", spy)
    monkeypatch.setattr(organizer, "compute_hashes", spy)
    _run(["analyze", str(library)], capsys)

    already = seen[0].lower()
    assert "identical copies" in already, "the forecast must name what is about to run"
    assert "ctrl-c" in already, "the user must be told stopping keeps what printed"


# --- interruption ---------------------------------------------------------------------------------


def test_an_interrupt_keeps_what_printed_and_refuses_a_partial_duplicate_count(
    library: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """**A half-scanned duplicate total is a wrong answer, not a partial one.**

    A duplicate count is a claim about the whole set: an unscanned file may be the twin of a
    scanned one, so the pairs found so far understate by an unknown amount. Unlike a file
    count, it has no honest partial reading -- so an interrupted tier reports *not analysed*.
    """

    def interrupted(*_args: object, **_kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(organizer, "compute_hashes", interrupted)
    code, out = _run(["analyze", str(library)], capsys)

    assert code == 0, "an interrupt is a supported outcome, not a failure"
    assert "files found" in out, "what printed before the interrupt must be kept"
    assert "Traceback" not in out
    lowered = out.lower()
    assert "stopped" in lowered
    assert "identical copies   : 0" not in out, "a partial scan must not report a zero"


# --- the HEIC forecast -----------------------------------------------------------------------------


def test_a_heic_heavy_library_is_warned_about(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The case our own corpus cannot show: an iPhone library straight off the cable.

    The files need not be real HEIC - the forecast reads the extension census, which is the
    point: it costs nothing and happens before any decode.
    """
    root = tmp_path / "iphone"
    root.mkdir()
    for i in range(8):
        (root / f"IMG_{i}.heic").write_bytes(b"\x00" * 10)
    _photo(root / "one.jpg", 10)

    _code, out = _run(["analyze", str(root)], capsys)
    assert "heic" in out.lower()
    assert "slower" in out.lower()


def test_a_jpeg_library_gets_no_heic_warning(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cry-wolf: a warning that fires on an all-JPEG library would be ignored when it matters."""
    _code, out = _run(["analyze", str(library)], capsys)
    assert "slower" not in out.lower()


def test_a_handful_of_strays_does_not_trigger_the_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The threshold's cry-wolf half, at the surface rather than only in the forecast."""
    root = tmp_path / "mostly-jpeg"
    root.mkdir()
    for i in range(40):
        _photo(root / f"IMG_{i}.jpg", i % 200)
    (root / "stray.heic").write_bytes(b"\x00" * 10)

    _code, out = _run(["analyze", str(root)], capsys)
    assert "slower" not in out.lower()


def test_cancellation_is_offered_to_the_engine() -> None:
    """The CLI must pass a cancel event, or Ctrl-C can only ever be a hard abort."""
    source = inspect.getsource(cli._analyze_deep)
    assert "threading.Event" in source or "cancel" in source
