"""`--version`, and the date line's origin formatting.

Both are small, but both are things a bug reporter reads first: the version they paste into
a report, and the line that says where a date came from.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli import __version__
from truestill_cli.cli import _format_new, main
from truestill_core.models import (
    CategoryMatch,
    Confidence,
    DateSource,
    Decision,
    FileHashes,
    Resolution,
)
from truestill_core.version import UNKNOWN_VERSION


def test_version_flag_exits_zero_without_a_subcommand(capsys: pytest.CaptureFixture[str]) -> None:
    """Subcommands are required, but --version must not need one -- that is the whole point."""
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"truestill {__version__}"


def test_version_comes_from_package_metadata() -> None:
    """Not a hardcoded string: a release bump must not be able to leave a stale number."""
    assert __version__ != UNKNOWN_VERSION
    assert __version__[0].isdigit()


def _resolution(source: DateSource, tag: str | None) -> Resolution:
    decision = Decision(
        source=Path("a.jpg"),
        category=CategoryMatch(
            label="Saved", confidence=Confidence.LOW, rule="fallback", reason="-"
        ),
        captured_at=None,
        date_source=source,
        date_tag=tag,
        relative=Path("Saved/Undated/a.jpg"),
    )
    return Resolution(
        decision=decision,
        hashes=FileHashes(sha256="0" * 64, perceptual=None),
        exact_duplicate=None,
        near_duplicate=None,
    )


def test_date_line_omits_the_tag_when_there_is_none() -> None:
    """A tagless source printed 'source=none, tag=none' -- the same word twice, reading as
    two independent pieces of evidence when it was only ever one."""
    out = _format_new(_resolution(DateSource.NONE, None), "local")
    assert "(source=none)" in out
    assert "tag=" not in out


def test_date_line_keeps_the_tag_when_a_metadata_field_supplied_it() -> None:
    out = _format_new(_resolution(DateSource.EXIF, "DateTimeOriginal"), "local")
    assert "(source=exif, tag=DateTimeOriginal)" in out


def test_a_real_run_never_says_uploaded(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The terminal is a user-facing surface too.

    Nothing is uploaded when organizing to a local folder, and saying so contradicts the
    promise the product is built on. The one legitimate survivor is Google's own
    "upload time", which names something the user really did do -- to Google.
    """
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"unique-content-one")
    (src / "b.jpg").write_bytes(b"unique-content-two")

    main(["organize", str(src), str(tmp_path / "out"), "--apply", "--db", str(tmp_path / "c.db")])

    out = capsys.readouterr().out
    assert "organized" in out  # it did say what happened
    assert "upload" not in out.lower()
