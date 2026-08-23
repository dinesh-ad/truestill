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

    A guard is not known to work until it has been seen to fail (`ENGINEERING_STANDARD.md` §4).

    ⚠ **These are the HISTORICAL backup banner, and no longer match `app.js`** - `(afw)` Stage 4
    deleted the clause they end in, because *"a copy that did not match would have stopped the
    run"* stopped being true when one bad file stopped aborting the batch.

    **They are kept rather than refreshed, and that is the point of them.** This pair is the real
    defect the guard was written against; a fixture rewritten to match today's code stops being
    evidence that the guard ever caught anything. They are literals here, not read from `app.js`,
    so nothing goes red - which is exactly why the staleness is stated instead of discovered.
    """
    damaged = "checked against its original before being recorded- a copy"
    repaired = "checked against its original before being recorded - a copy"
    assert MALFORMED.search(damaged), "the guard would not have caught the shipped defect"
    assert not MALFORMED.search(repaired)

    # And it must not fire on ordinary hyphenated compounds, or it would be turned off.
    for benign in ("year-first layout", "re-hash the drive", "2014-08-15", "--apply"):
        assert not MALFORMED.search(benign), benign


#: A count pluralised by concatenating a suffix inline, instead of calling ``plural``.
#:
#: Matches the interpolation body ``n === 1 ? "" : "s"`` - an empty singular branch and a quoted
#: literal suffix. Deliberately keyed on *that shape* rather than on the word "plural", so it
#: cannot be dodged by renaming a variable, and so it stays blind to the two things that look
#: identical and are not: ``plural``'s own definition (whose else-branch is the identifier
#: ``suffix``, not a quoted literal) and a ternary choosing between two whole words for a stat
#: label (whose *if*-branch is a word, not ``""``). Both are pinned in
#: :func:`test_the_inline_plural_guard_does_not_fire_on_the_real_look_alikes`.
INLINE_PLURAL = re.compile(r'\?\s*""\s*:\s*"[A-Za-z]{1,3}"')


def test_counts_are_pluralised_through_the_shared_helper() -> None:
    """§9 names ``plural`` as *the* place a count is worded; six sites had re-implemented it.

    Each was byte-equivalent to ``plural(n, word)`` on the day it was written, which is exactly
    why this needs a gate rather than a review: nothing fails when the seventh copy drifts.
    """
    app_js = USER_FACING[0].read_text(encoding="utf-8")
    offenders = [
        f"app.js:{n}: {line.strip()}"
        for n, line in enumerate(app_js.splitlines(), 1)
        if INLINE_PLURAL.search(line)
    ]
    assert not offenders, (
        "count pluralised inline instead of through plural() - see IMPLEMENTATION_STANDARDS 9:\n"
        + "\n".join(offenders)
    )


def test_the_inline_plural_guard_does_not_fire_on_the_real_look_alikes() -> None:
    """Both halves: it must catch the shape it names, and let the two real neighbours through.

    A guard that fired on ``plural``'s own definition, or on a two-word label ternary, would be
    switched off the first time someone hit it - taking its real coverage with it
    (`ENGINEERING_STANDARD.md` 4).
    """
    caught = '`${nfmt(s.photos)} photo${s.photos === 1 ? "" : "s"}`'
    assert INLINE_PLURAL.search(caught), "the guard would not have caught the six shipped sites"
    assert INLINE_PLURAL.search('`${n} match${n === 1 ? "" : "es"}`'), "multi-letter suffix"

    # 1. plural's own definition: the else-branch is an identifier, not a quoted suffix.
    definition = 'const plural = (n, word, suffix = "s") => `${nfmt(n)} ${word}${Number(n) === 1 ? "" : suffix}`;'
    assert not INLINE_PLURAL.search(definition), "the guard must not fire on plural itself"

    # 2. A stat tile picks a bare noun for its label; the number lives in `value`, so routing
    #    this through plural() would print the count twice.
    label = 'label: Object.keys(r.folders).length === 1 ? "folder" : "folders",'
    assert not INLINE_PLURAL.search(label), "a two-word label ternary is not an inline plural"

    # 3. A mass noun that has no plural form at all.
    assert not INLINE_PLURAL.search("`${nfmt(s.audio)} audio`")


def test_trip_duration_names_active_days_not_calendar_span() -> None:
    """A Sep 13-16 trip with photos on three dates is three active days, not a three-day span."""
    app_js = USER_FACING[0].read_text(encoding="utf-8")
    assert 'plural(c.active_days, "active day")' in app_js
    assert 'plural(c.days.length, "day")' not in app_js


#: ``Import from <Service>`` - the shape that scopes a source-agnostic feature to one vendor.
#:
#: Keyed on the shape rather than on one vendor's name, so re-introducing the heading for a
#: different service fails the same way. The capital is what makes it a service name:
#: ``Import from a folder`` and ``Import from anywhere`` describe the real scope and must pass.
SERVICE_SCOPED_IMPORT = re.compile(r"Import from [A-Z]")


@pytest.mark.parametrize("path", [USER_FACING[0], USER_FACING[1]], ids=lambda p: p.name)
def test_no_surface_scopes_import_to_one_service(path: Path) -> None:
    """`ingest` reads any folder and any archive from any source.

    SHIPPED's (jj) scope correction says every user-facing string was audited and six reworded.
    Two were missed - the Import heading and the button on the Stats empty state that points at
    it - and nothing in the suite could see them, because prose is not something ruff or mypy
    reads. This is that gate, in the file written for exactly this failure.
    """
    offenders = [
        f"{path.relative_to(REPO)}:{n}: {line.strip()}"
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if SERVICE_SCOPED_IMPORT.search(line)
    ]
    assert not offenders, "import scoped to one service:\n" + "\n".join(offenders)


def test_the_service_scope_guard_catches_the_shipped_string_and_spares_the_real_ones() -> None:
    """A guard is not known to work until it has been seen to fail."""
    assert SERVICE_SCOPED_IMPORT.search("<h1>Import from Google Photos</h1>")
    assert SERVICE_SCOPED_IMPORT.search('data-stats-action="import">Import from Apple Photos<')

    # The motivating case may still be NAMED as an example - it is the scope that was wrong.
    # `takeout.py`, `scan_takeout` and the sidecar parsing are Google's own format and keep it.
    for benign in (
        'placeholder="e.g. /home/you/Downloads/Takeout or a folder of .zip files"',
        "Import from a folder of photos",
        "Import from anywhere",
        'start: () => api("/api/ingest/preview", { takeout, destination }),',
    ):
        assert not SERVICE_SCOPED_IMPORT.search(benign), benign


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
#: service/ is a package (F10); facade and surface modules that carry user-facing strings.
_SERVICE_USER_FACING: tuple[Path, ...] = (
    REPO / "packages/truestill-app/src/truestill_app/service/__init__.py",
    REPO / "packages/truestill-app/src/truestill_app/service/fs_browse.py",
    REPO / "packages/truestill-app/src/truestill_app/service/stats.py",
    REPO / "packages/truestill-app/src/truestill_app/service/drives.py",
    REPO / "packages/truestill-app/src/truestill_app/service/backup.py",
    REPO / "packages/truestill-app/src/truestill_app/service/organize.py",
)
_USER_FACING_TEXT = tuple(
    path
    for path in (*USER_FACING, *_SERVICE_USER_FACING)
    if path in _SERVICE_USER_FACING or path.name in {"app.js", "index.html", "cli.py", "README.md"}
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
