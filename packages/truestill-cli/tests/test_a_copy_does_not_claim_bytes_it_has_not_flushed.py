"""The backup summary does not claim the bytes are on the drive when they are still in RAM.

⚠ **MEASURED, 2026-09-12, real exFAT drive over USB.** `backup` printed *"Copied 161 file(s),
297 MB"* after 2.36 s, and **240 MB of it was still dirty**; `sync` needed 4.28 s more. Every
write call had returned and every staged file had taken its real name, so the FILE count is
honest - what the line could not support is the fair inference that the bytes are on the drive.

`cli.py`'s own comment read *"the count above is unqualified and true"* until that measurement.
"""

from __future__ import annotations

from pathlib import Path

import truestill_core.backup as core
from truestill_cli import cli
from truestill_core.backup import EJECT_BEFORE_UNPLUGGING, WRITES_MAY_STILL_BE_IN_FLIGHT

_CLI_SOURCE = Path(cli.__file__ or "").read_text(encoding="utf-8")


def test_the_qualifier_says_what_is_not_yet_true() -> None:
    """It has to name MEMORY, not just advise an eject - the eject note already does that, and a
    second line repeating the remedy would leave the claim itself uncorrected."""
    assert "memory" in WRITES_MAY_STILL_BE_IN_FLIGHT.lower()
    assert WRITES_MAY_STILL_BE_IN_FLIGHT != EJECT_BEFORE_UNPLUGGING


def test_the_backup_report_prints_both_the_reason_and_the_remedy() -> None:
    """The qualifier is the reason, the eject note is the remedy, and a reader needs both. Read
    from the source because these are two adjacent `print` calls, not a composed string."""
    body = _CLI_SOURCE
    assert "WRITES_MAY_STILL_BE_IN_FLIGHT}" in body, "the qualifier is not printed anywhere"
    where = body.index("WRITES_MAY_STILL_BE_IN_FLIGHT}")
    after = body[where : where + 400]
    assert "EJECT_BEFORE_UNPLUGGING}" in after, "the remedy does not follow the reason"


def test_the_qualifier_has_one_wording_home() -> None:
    """⚠ **Core, not the CLI**, so the app can adopt the same words rather than write a second
    sentence about the same physics. `IMPLEMENTATION_STANDARDS.md` 9: one home per outcome."""

    assert core.WRITES_MAY_STILL_BE_IN_FLIGHT
    assert "may still be in memory" not in _CLI_SOURCE, "the sentence was re-typed in the CLI"
