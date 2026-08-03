"""The forecast says what it will read, never how long that will take.

**A wrong time estimate is worse than none** - it is the number a user plans their evening
around. The obvious signal is tier 0's own measured throughput and it cannot carry the claim:
tier 0 times `stat` calls against directory metadata, this tier reads file *contents*. A FUSE
client serving directory listings from its local cache - the common case - produces a fast
tier 0 on an arbitrarily slow link, so the correlation is not weak but **absent or inverted**.

Measured on the 32,628-file, 192 GB encrypted cloud mount: tier 0 took 21 s; the expensive
tiers moved 29.4 GB at ~9 MB/s over 53 minutes. The maintainer's advance projection from a 5 GB
sample of *content reads* - a much better predictor than a stat rate - still spanned 3.6x-36x.

This is a **guard against a future good intention**, in the shape of
`test_no_migration_performs_a_backfill`: adding a time estimate should fail here and force the
conversation, rather than land because it looked helpful. `docs/PERFORMANCE.md` §5.2 holds the
measurement and the reasoning.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from PIL import Image
from truestill_cli.cli import main

#: Shapes a time estimate takes. Deliberately broad - the point is that *no* wording of one
#: gets in, not that one particular phrasing does not.
_TIME_CLAIM = re.compile(
    r"\b(?:"
    r"(?:about|around|roughly|approx\w*|~)\s*[\d.]+\s*(?:s|sec|second|min|minute|hour|hr)"
    r"|[\d.]+\s*(?:seconds|minutes|hours)\s+(?:to go|remaining|left)"
    r"|estimated?\s+(?:time|to\s+finish)"
    r"|eta\b"
    r"|will\s+take\s+(?:about\s+)?[\d.]+"
    r")",
    re.IGNORECASE,
)


@pytest.fixture
def library(tmp_path: Path) -> Path:
    folder = tmp_path / "pics"
    folder.mkdir()
    for i in range(4):
        Image.new("RGB", (32, 32), (i * 9 % 256, 3, 3)).save(folder / f"p{i}.jpg", "JPEG")
    # A second copy, so the size pre-filter finds collidable files and the forecast has work.
    (folder / "twin.jpg").write_bytes((folder / "p0.jpg").read_bytes())
    return folder


def test_the_forecast_states_what_it_will_read(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Anti-vacuity: the forecast must actually be printed, or the ban below guards nothing."""
    main(["analyze", str(library)])
    out = capsys.readouterr().out

    assert "needs to read" in out
    assert "GB of your" in out


def test_the_forecast_makes_no_claim_about_how_long_it_will_take(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The deliverable. Accurate-or-absent, the rule `_rate_note` already follows."""
    main(["analyze", str(library)])
    out = capsys.readouterr().out

    found = _TIME_CLAIM.findall(out)
    assert not found, f"the report grew a time estimate: {found}\n{out}"


def test_the_contrast_is_stated_because_it_needs_no_number(
    library: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Refusing the estimate is not the same as saying nothing.

    The honest half of the answer costs no accuracy: the census is fast on any mount because
    it reads folder listings, and this tier scales with the connection because it reads the
    files. That is what a user needs in order to decide whether to wait.
    """
    main(["analyze", str(library)])
    out = capsys.readouterr().out

    assert "folder listings" in out
    assert "depends on your disk or connection" in out


def test_the_ban_can_see_the_shapes_it_forbids() -> None:
    """Anti-vacuity for the regex: one that matched nothing would pass this file forever."""
    for sample in (
        "  this will take about 45 minutes",
        "  estimated time: 12 minutes",
        "  ~3.5 hours remaining",
        "  ETA 20 min",
        "  12 minutes remaining",
    ):
        assert _TIME_CLAIM.search(sample), sample


def test_the_ban_spares_the_facts_the_report_is_allowed_to_state() -> None:
    """Cry-wolf. Elapsed time *already measured* is a fact, not a forecast, and tier 0 reports
    it - so a guard that flagged `time taken : 21 s` would take real coverage with it."""
    for spared in (
        "  time taken         : 0.31 s  (7,319 files/second)",
        "  time taken         : 3 min 12 s",
        "  needs to read 29.40 GB of your 192.49 GB",
        "  Press Ctrl-C to stop and keep everything above.",
    ):
        assert not _TIME_CLAIM.search(spared), spared
