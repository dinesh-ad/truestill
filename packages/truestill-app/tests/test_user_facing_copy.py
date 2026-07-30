"""Guards on the prose a user actually reads.

On 2026-07-28 a repo-wide sweep replacing em-dashes with hyphens consumed the leading space too,
turning ``recorded - a copy`` into ``recorded- a copy`` in 61 places. Two of them were in the web
UI's backup banner, so the damage was shipped-facing rather than internal. Ruff, mypy and the test
suite were all green throughout: **no gate we had could see prose.**

These tests are that gate. They read the shipped files directly rather than rendering the UI,
because the defect is in the source text and does not need a browser to detect - the E2E lane
owns what the page *does*, this owns what the copy *says*.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]

#: Surfaces whose text a user reads. Kept in step with `scripts/normalize_dashes.EXCLUDED`,
#: which is the list of paths that script refuses to rewrite for this same reason.
#: Every path here **must** resolve - a missing file is a broken guard, not a skip (audit F12).
USER_FACING: tuple[Path, ...] = (
    REPO / "packages/truestill-app/src/truestill_app/static/app.js",
    REPO / "packages/truestill-app/src/truestill_app/templates/index.html",
    REPO / "packages/truestill-cli/src/truestill_cli/cli.py",
    REPO / "README.md",
    REPO / "SECURITY.md",
)

#: Paths that may be absent without disarming the suite. Empty on purpose today: nothing in
#: USER_FACING is optional, and a future optional surface must be named here explicitly.
OPTIONAL_USER_FACING: tuple[Path, ...] = ()

#: ``word- word``: a hyphen glued to the preceding word with a space only after it. Real prose
#: never does this - it is either a compound (``year-first``, no spaces) or a parenthetical dash
#: (`` - ``, spaces both sides). Anything in between is a mangled dash.
MALFORMED = re.compile(r"[0-9A-Za-z]- [0-9A-Za-z]")


def test_user_facing_paths_resolve() -> None:
    """Relocating a USER_FACING file must fail the suite, not skip the guard (audit F12)."""
    missing = [str(path.relative_to(REPO)) for path in USER_FACING if not path.exists()]
    assert not missing, "USER_FACING path(s) missing - guard would be silent:\n" + "\n".join(
        missing
    )


@pytest.mark.parametrize("path", USER_FACING, ids=lambda p: p.name)
def test_user_facing_copy_has_no_mangled_dash(path: Path) -> None:
    """No shipped string may contain ``word- word``."""
    if path in OPTIONAL_USER_FACING and not path.exists():
        pytest.skip(f"{path.name} not present (optional)")
    assert path.exists(), (
        f"{path.relative_to(REPO)} must exist - see test_user_facing_paths_resolve"
    )

    offenders = [
        f"{path.relative_to(REPO)}:{n}: {line.strip()}"
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if MALFORMED.search(line)
    ]
    assert not offenders, "mangled dash in user-facing copy:\n" + "\n".join(offenders)


def test_the_guard_can_actually_see_the_defect() -> None:
    """The pattern must reject the real damaged string and accept the real repaired one.

    A guard is not known to work until it has been seen to fail (`ENGINEERING_STANDARD.md` 4).
    Both strings below are the actual before/after of the backup banner in `app.js`.
    """
    damaged = "checked against its original before being recorded- a copy"
    repaired = "checked against its original before being recorded - a copy"
    assert MALFORMED.search(damaged), "the guard would not have caught the shipped defect"
    assert not MALFORMED.search(repaired)

    # And it must not fire on ordinary hyphenated compounds, or it would be turned off.
    for benign in ("year-first layout", "re-hash the drive", "2014-08-15", "--apply"):
        assert not MALFORMED.search(benign), benign


def test_trip_duration_names_active_days_not_calendar_span() -> None:
    """A Sep 13-16 trip with photos on three dates is three active days, not a three-day span."""
    app_js = USER_FACING[0].read_text(encoding="utf-8")
    assert 'plural(c.active_days, "active day")' in app_js
    assert 'plural(c.days.length, "day")' not in app_js


def test_trip_and_event_result_rows_keep_their_kind_label() -> None:
    app_js = USER_FACING[0].read_text(encoding="utf-8")
    assert "function reviewResultCards(summary)" in app_js
    assert "g.kind.toUpperCase()" in app_js
    assert "tripResultCards" not in app_js


# Phrases from older wording that this audit replaces.
#
# We ban exact copy snippets (not generic words) so this guard stays focused on user-facing
# prose and does not fight internal ids/comments.
_BANNED_USER_PHRASES = (
    "This folder isn't a truestill backup yet - use <b>Copy your library to another drive</b> below to create one.",
    "In-place mode uses the source folder as destination.",
    "Invalid:",
    # 3-part structure is a writing guide, not visible scaffolding.
    "What happened:",
    "What to do:",
)
_ALLOWED_USER_TERMS = (
    "custody",
    "catalog file",
    "template",
    "preset",
    "--in-place",
    "--phash-threshold",
    "JSON",
)
_USER_FACING_TEXT = tuple(
    path
    for path in (
        *USER_FACING,
        REPO / "packages/truestill-app/src/truestill_app/service.py",
    )
    if path.name in {"app.js", "index.html", "cli.py", "README.md", "service.py"}
)


@pytest.mark.parametrize("path", _USER_FACING_TEXT, ids=lambda p: p.name)
def test_user_facing_copy_avoids_banned_jargon(path: Path) -> None:
    assert path.exists(), (
        f"{path.relative_to(REPO)} must exist - relocating it must fail this guard"
    )
    text = path.read_text(encoding="utf-8")
    offenders = [phrase for phrase in _BANNED_USER_PHRASES if phrase in text]
    assert not offenders, (
        f"banned user-facing terms in {path.relative_to(REPO)}: {', '.join(offenders)}"
    )


def test_user_facing_copy_allowlist_documents_kept_terms() -> None:
    missing = [str(path.relative_to(REPO)) for path in _USER_FACING_TEXT if not path.exists()]
    assert not missing, "allowlist inputs missing:\n" + "\n".join(missing)
    combined = "\n".join(path.read_text(encoding="utf-8") for path in _USER_FACING_TEXT).lower()
    for allowed in _ALLOWED_USER_TERMS:
        assert allowed.lower() in combined
