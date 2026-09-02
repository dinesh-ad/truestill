"""A commit that closes an entry must move it out of `BACKLOG.md` - and both directions of that.

**Why this exists.** `BACKLOG.md` carries open work only - `SHIPPED.md`'s header says that split
exists because `(aae)` and `(jj)` once sat in the wrong section while they were shipping. The rule
was written down and nothing ran it. On 2026-08-10 a sweep found three entries stale, and by the
end of that same day **three more** - `(acq)`, `(acr)`, `(acs)` - had been closed and left in
place, one of them by a commit whose own message said it was closing it.

That is `(ace)`'s pattern: a rule that depends on somebody remembering. Prose cannot refuse to run.

**Two directions, and only one of them belongs here.**

* *Declared closed, still open work* - checked below, over the corpus. It keys on the trailer, so
  it has no legacy exposure: an entry closed before the rule existed carries none and is not
  examined.
* *Left the backlog without ever being declared* - **not honestly checkable against history**, and
  the measurement is the argument. "A letter in `SHIPPED.md` must carry a trailer" fails **31 of
  its 32 entries** the day it is written, because the whole history holds exactly one trailer; and
  "an allocated letter is in one of the two files" is false too - `(e)`, `(h)` and `(gg)` are
  retired and legitimately in neither. A guard that goes red on the past gets switched off (§4).
  It lives in `scripts/check_entry_closure.py` instead, a commit-msg hook that reads only the
  staged diff of the commit being made, so its boundary is structural rather than a date.

**The marker is narrow on purpose, and the full stop is optional on purpose.** A letter counts as
closed when a line is `Closes (xyz)` - a trailer of its own, with or without the period. Tested
against the full history, the obvious wider pattern (`closes?\\s*\\(xyz\\)` anywhere, any case)
returns **two matches and both are false**:

* `(aco)` - *"a timezone dataset is not the cheapest way to close (aco)"*, a sentence ABOUT closing
  it. The entry is legitimately open.
* `(bbb)` - *"close (bbb) with item 4 verified, not ticked"*, on an entry that still carries
  partially-built sub-items.

The period is not required because requiring it fails in the dangerous direction: a missing full
stop would silently stop a commit counting as a closure, leaving a shipped entry sitting in the
open-work file with nothing to say so - the exact silence this guard exists to end. `BACKLOG.md`
says the same, so prose and regex cannot disagree.

**What this cannot see.** CI checks out at depth 1, so there `git log` holds only the tip; a batch
push means only the batch's last commit is examined. Locally the window is the whole history.
Neither is total; the check that matters most runs at commit time, when the entry move belongs in
the same commit anyway.

**And the gap no check can close.** `(acr)` was closed by the maintainer **in conversation**. No
repo check could ever have seen that, which is why the process rule in `BACKLOG.md`'s *Item
letters* section says a ruling is not a closure until a commit records it.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKLOG = ROOT / "docs/BACKLOG.md"
SHIPPED = ROOT / "docs/SHIPPED.md"
SCRIPT = ROOT / "scripts/check_entry_closure.py"


def _load():
    """The hook script, imported by path - the house pattern (`test_redirect_artifacts.py`).

    The patterns are imported rather than restated so the hook and this file cannot word the
    marker differently; two copies of one rule is the drift §4 names.
    """
    spec = importlib.util.spec_from_file_location("check_entry_closure", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_hook = _load()


def _log() -> str:
    """Whatever history this clone has. Empty string when git cannot answer."""
    try:
        done = subprocess.run(
            ["git", "log", "--format=%B"],
            cwd=ROOT,
            capture_output=True,
            # ⚠ **The same seam as the hook's, and this one has been live for longer**: commit
            # messages here carry `⚠` and `❌`, and `git log` over this history is already
            # undecodable as cp1252. `(aic)`, and `check_entry_closure._TEXT` beside it.
            encoding="utf-8",
            errors="surrogateescape",
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - no git in the environment
        return ""
    return done.stdout if done.returncode == 0 else ""


def _is_shallow() -> bool:
    done = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode == 0 and done.stdout.strip() == "true"


def _declared_closed() -> set[str]:
    log = _log()
    if not log:
        pytest.skip("no git history available to read")
    if _is_shallow():
        # CI checks out at depth 1, so this read one commit's body and passed over an empty set
        # for as long as it has run there (found 2026-09-02, P188). A stated skip is honest; a
        # vacuous pass is not. Widening the checkout is a cost decision for the maintainer.
        pytest.skip(
            "shallow checkout - one commit of history holds no closure trailers, so the corpus half cannot judge anything here"
        )
    closed = set(_hook.CLOSES.findall(log))
    # A pattern that stops matching passes both corpus tests over an empty set, and the fixture
    # tests below would not notice - they feed the regex a string that still matches. 125
    # trailers on 2026-09-02; the floor is a fraction of that.
    assert len(closed) >= 40, (
        f"only {len(closed)} `Closes` trailers matched in {len(log)} bytes of history; the pattern "
        "has stopped matching and every assertion over it is vacuous"
    )
    return closed


# --------------------------------------------------------------- the corpus half, over history


def test_a_letter_a_commit_declared_closed_is_not_still_open_work() -> None:
    """A commit said it closed the entry; the entry must not be in the open-work file."""
    still_open = sorted(_declared_closed() & set(_hook.ENTRY.findall(BACKLOG.read_text("utf-8"))))
    assert not still_open, (
        f"closed by a commit and still in BACKLOG.md: {still_open}. "
        "BACKLOG.md carries open work only - move the entry to SHIPPED.md, which keeps its "
        "letter. If the entry is NOT actually closed, the commit message should not say so."
    )


def test_a_letter_a_commit_declared_closed_arrived_in_shipped() -> None:
    """The hole the first test leaves: an entry can leave the backlog and arrive nowhere.

    Deleting it outright satisfies "not in BACKLOG.md" perfectly, and the letter stays allocated
    while its provenance is gone - which is how a closed item gets rebuilt.

    Keyed on the trailer, so it says nothing about the 31 entries that predate the rule.
    """
    missing = sorted(_declared_closed() - set(_hook.ENTRY.findall(SHIPPED.read_text("utf-8"))))
    assert not missing, (
        f"declared closed by a commit and in neither document: {missing}. "
        "A closed entry keeps its letter and moves to SHIPPED.md; it is provenance."
    )


def test_the_marker_does_not_match_prose_about_closing_something() -> None:
    """**The cry-wolf half, and it is the reason for the narrow marker.**

    The first two strings appear in this repo's real history and both describe an entry that is
    legitimately open. If the pattern ever widens, this fails before the widening reaches a
    contributor as a false alarm on ordinary work.
    """
    for prose in (
        "a timezone dataset is not the cheapest way to\nclose (aco).",
        "docs(backlog): close (bbb) with item 4 verified, not ticked",
        "This closes (abc) in spirit but not in fact.",
        "Closes (abc) once the second half lands.",
    ):
        assert not _hook.CLOSES.findall(prose), f"the marker matched prose: {prose!r}"


def test_the_marker_matches_the_declared_form_with_or_without_the_period() -> None:
    """A guard that matches nothing would pass forever - and the period must not decide it."""
    assert _hook.CLOSES.findall("Some body text.\n\nCloses (acq).") == ["acq"]
    assert _hook.CLOSES.findall("Closes (acq)") == ["acq"]


# ------------------------------------------------------- the per-commit half, over a real repo


def _repo(tmp_path: Path, backlog: str, shipped: str) -> Path:
    """A real git repo with both documents committed. The hook reads a staged diff, so a fake
    would be testing the fake."""
    run = lambda *args: subprocess.run(  # noqa: E731 - three-word helper, not a function
        args, cwd=tmp_path, capture_output=True, text=True, check=True
    )
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@example.invalid")
    run("git", "config", "user.name", "t")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/BACKLOG.md").write_text(backlog, "utf-8")
    (tmp_path / "docs/SHIPPED.md").write_text(shipped, "utf-8")
    run("git", "add", "-A")
    run("git", "commit", "-q", "-m", "base")
    return tmp_path


def _stage(repo: Path, backlog: str, shipped: str) -> None:
    (repo / "docs/BACKLOG.md").write_text(backlog, "utf-8")
    (repo / "docs/SHIPPED.md").write_text(shipped, "utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)


def _hook_says(repo: Path, message: str) -> tuple[int, str]:
    """Run the hook exactly as git does: the message in a file, the repo as cwd."""
    msg = repo / "COMMIT_EDITMSG"
    msg.write_text(message, "utf-8")
    done = subprocess.run(
        [sys.executable, str(SCRIPT), str(msg)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.returncode, done.stderr


_OPEN = "- **(zz) SOMETHING OPEN.** Body.\n\n- **(zy) ANOTHER.** Body.\n"
_ONLY_ZY = "- **(zy) ANOTHER.** Body.\n"
_BUILT = "- **(za) DONE LONG AGO.** Body.\n"


def test_an_entry_that_leaves_the_backlog_and_is_declared_and_arrives_is_accepted(
    tmp_path: Path,
) -> None:
    """The good commit, and the differential that proves the diff reached the check.

    A pass alone would be satisfied by a hook that read nothing at all - the same staged state
    with the trailer removed must be refused, which only a hook that saw the removal can do.
    """
    repo = _repo(tmp_path, _OPEN, _BUILT)
    _stage(repo, _ONLY_ZY, _BUILT + "\n- **(zz) SOMETHING OPEN.** Body.\n")

    assert _hook_says(repo, "docs: move it\n\nCloses (zz).\n") == (0, "")

    code, err = _hook_says(repo, "docs: move it\n")
    assert code == 1, "the staged removal never reached the hook"
    assert "(zz)" in err, f"the refusal does not name what it saw: {err!r}"


def test_an_entry_that_leaves_undeclared_is_refused(tmp_path: Path) -> None:
    """The case the corpus guard cannot see: it left, and no commit ever said it was closed."""
    repo = _repo(tmp_path, _OPEN, _BUILT)
    _stage(repo, _ONLY_ZY, _BUILT + "\n- **(zz) SOMETHING OPEN.** Body.\n")

    code, err = _hook_says(repo, "docs: tidy the backlog\n")
    assert code == 1
    assert "Closes (zz)." in err, f"the refusal does not name the remedy: {err!r}"


def test_an_entry_deleted_outright_is_refused_even_when_declared(tmp_path: Path) -> None:
    """Declaring it closed is not enough - provenance is the point of keeping the letter."""
    repo = _repo(tmp_path, _OPEN, _BUILT)
    _stage(repo, _ONLY_ZY, _BUILT)

    code, err = _hook_says(repo, "docs: drop it\n\nCloses (zz).\n")
    assert code == 1
    assert "did not arrive in docs/SHIPPED.md" in err, f"wrong refusal: {err!r}"


def test_retitling_an_entry_in_place_is_not_a_departure(tmp_path: Path) -> None:
    """**The cry-wolf half.** An edit to an entry's own title removes and re-adds its line.

    A guard that called that a closure would fire on ordinary backlog work and be switched off.
    The differential: the same commit with the entry really gone IS refused.
    """
    repo = _repo(tmp_path, _OPEN, _BUILT)
    _stage(
        repo, "- **(zz) SOMETHING OPEN, REWORDED.** Body.\n\n- **(zy) ANOTHER.** Body.\n", _BUILT
    )
    assert _hook_says(repo, "docs: reword (zz)\n") == (0, "")

    _stage(repo, _ONLY_ZY, _BUILT)
    assert _hook_says(repo, "docs: reword (zz)\n")[0] == 1, "the guard cannot see a real departure"


def test_ordinary_backlog_work_is_left_alone(tmp_path: Path) -> None:
    """Adding an entry, and editing prose that is not a title, must both pass."""
    repo = _repo(tmp_path, _OPEN, _BUILT)
    _stage(repo, _OPEN + "\n- **(zx) NEW WORK.** Body.\n", _BUILT)
    assert _hook_says(repo, "docs(backlog): (zx) new work\n") == (0, "")

    _stage(repo, _OPEN.replace("Body.", "Body, with more detail."), _BUILT)
    assert _hook_says(repo, "docs(backlog): expand (zz)\n") == (0, "")


def test_it_fails_open_where_it_cannot_answer(tmp_path: Path) -> None:
    """No staged change to either document is not a refusal, and neither is no git at all.

    A commit-msg hook that refuses when it cannot see is one that gets bypassed with
    `--no-verify`, which costs more than the check is worth.

    ⚠ **THIS ALSO ASSERTED THAT A STRAY `Closes (zz).` ON AN UNRELATED COMMIT WAS ACCEPTED, AND
    THAT ASSERTION WAS THE HOLE**, not a property. The hook is not unable to answer there: it
    reads `BACKLOG.md` and can see the entry is still open. `BACKLOG.md`'s own rule makes the
    trailer and the move **one act** - *"a commit whose message says `Closes (xyz)` on a line of
    its own, and ... that commit moves the entry"* - so a trailer without the move is always a
    false claim, whatever else the commit touched. It moved to
    `test_a_stray_closure_trailer_is_refused_even_on_an_unrelated_commit` below, as a refusal.
    """
    repo = _repo(tmp_path, _OPEN, _BUILT)
    assert _hook_says(repo, "chore: unrelated\n") == (0, "")
    assert _hook.refusals("Closes (zz).", "") == []


# --- the direction that had no COMMIT-TIME guard at all ----------------------------------------


def test_declaring_a_closure_without_moving_the_entry_is_refused(tmp_path: Path) -> None:
    """⚠ **THE HOLE THIS FILE DID NOT KNOW IT HAD, and it cost a red CI on 2026-08-23.**

    The corpus check above owns this direction - *declared closed, still open work* - and catches
    it perfectly. What it **cannot** do is catch it in time: it reads the **commit message**, and
    at the moment `make check` runs (before every commit, by the standing rule) that message does
    not exist yet. So it can only ever report on a commit already made, which in practice means
    after the push, from CI.

    Measured: commit `4051914` said `Closes (afw)` while `(afw)` was still an entry in
    `BACKLOG.md`. The hook **passed** - it only ever iterated over what LEFT the backlog, never
    over what was DECLARED - and all three CI lanes then went red on the corpus check.

    **So the two guards were not two halves of one rule; they were one half, twice.** The hook is
    the only thing that can act at commit time, and it now checks both directions. This has no
    legacy exposure for the reason the module's docstring already gives: it reads only the commit
    being made.
    """
    repo = _repo(tmp_path, _OPEN, _BUILT)
    # The entry is edited but NOT moved - exactly the shape of the commit that went red.
    _stage(repo, _OPEN.replace("SOMETHING OPEN", "SOMETHING OPEN, NOW WITH A STAGE DONE"), _BUILT)

    code, err = _hook_says(repo, "feat: finish the stage\n\nCloses (zz).\n")

    assert code == 1, "a commit claiming a closure it did not perform was accepted"
    assert "(zz)" in err, f"the refusal does not name the letter: {err!r}"
    assert "BACKLOG" in err, f"the refusal does not name the remedy: {err!r}"


def test_a_closure_trailer_for_an_entry_already_gone_is_accepted(tmp_path: Path) -> None:
    """⚠ **CRY-WOLF HALF.** The refusal must key on *"is it still open work"*, not on *"did it
    leave in THIS commit"*.

    A follow-up commit that repeats the trailer - or one that moves an entry whose title was
    already absent - is not a false claim: the entry is gone, which is the end state the rule
    exists to produce. Refusing here would make the correction commit for a red build impossible
    to write, which is exactly the situation this guard was added in.
    """
    repo = _repo(tmp_path, _ONLY_ZY, _BUILT + "\n- **(zz) SOMETHING OPEN.** Body.\n")
    _stage(repo, _ONLY_ZY, _BUILT + "\n- **(zz) SOMETHING OPEN.** Body.\n")

    assert _hook_says(repo, "docs: restate it\n\nCloses (zz).\n") == (0, "")


def test_the_two_directions_are_reported_together(tmp_path: Path) -> None:
    """One commit can get both wrong, and a guard that stopped at the first would hide the second.

    `(zz)` is claimed closed without moving; `(zy)` leaves with nothing said about it.
    """
    repo = _repo(tmp_path, _OPEN, _BUILT)
    _stage(repo, "- **(zz) SOMETHING OPEN.** Body.\n", _BUILT)

    code, err = _hook_says(repo, "docs: half a job\n\nCloses (zz).\n")

    assert code == 1
    assert "(zz)" in err, f"the declared-but-not-moved direction is missing: {err!r}"
    assert "(zy)" in err, f"the moved-but-not-declared direction is missing: {err!r}"


def test_a_stray_closure_trailer_is_refused_even_on_an_unrelated_commit(tmp_path: Path) -> None:
    """The declaration is the claim, and it is false whether or not the commit touched the docs.

    ⚠ **This is the case with the widest blast radius**, because it needs no doc edit to happen -
    a trailer typed into a code commit is enough. It used to be the accepted case.
    """
    repo = _repo(tmp_path, _OPEN, _BUILT)

    code, err = _hook_says(repo, "chore: unrelated\n\nCloses (zz).\n")

    assert code == 1, "a commit claimed a closure it did not perform and was accepted"
    assert "(zz)" in err


def test_it_judges_the_staged_backlog_not_the_working_tree(tmp_path: Path) -> None:
    """The commit is what the rule is about, and those two differ more often than they look.

    Here the move IS staged and the working tree has been edited again afterwards - an ordinary
    thing to do while writing the commit message. Reading the file from disk would see the entry
    still present and refuse a commit that is correct.
    """
    repo = _repo(tmp_path, _OPEN, _BUILT)
    _stage(repo, _ONLY_ZY, _BUILT + "\n- **(zz) SOMETHING OPEN.** Body.\n")
    # ...and then the author keeps typing, unstaged.
    (repo / "docs/BACKLOG.md").write_text(_OPEN, "utf-8")

    assert _hook_says(repo, "docs: move it\n\nCloses (zz).\n") == (0, "")


# --- the seam that only one of the three CI lanes can see --------------------------------------


def test_the_hook_reads_git_as_utf8_whatever_the_machine_locale_says() -> None:
    """⚠ **THE WINDOWS LANE CAUGHT THIS AND NO LOCAL RUN COULD.** `(aic)`, applied to git.

    `subprocess.run(..., text=True)` decodes with `locale.getpreferredencoding(False)` - **cp1252
    on Windows** - and both documents this hook reads are full of `⚠`, `❌` and `🔑`. `❌` is
    `E2 9D 8C`; `0x9D` is one of the five bytes cp1252 does not map. The first `❌` to reach
    `BACKLOG.md` therefore took the Windows lane red at byte 18,761, on a commit whose local
    `make check` was green - **a POSIX locale is UTF-8, so the defect cannot appear here at all.**

    🔑 **So this test does not wait for a platform; it forces the decode.** Swapping `text=True`
    for `encoding="cp1252"` reproduces the Windows seam exactly - same byte, same position - and
    bites on every lane. That technique is `test_the_reply_survives_the_machine_locale.py`'s, and
    the reason a `pytest.mark.skipif(sys.platform != "win32")` would be worse than nothing: it
    would be silent on the machine anyone actually develops on.

    ⚠ **It reads the REAL `BACKLOG.md`, deliberately, and that is what makes it a live guard**
    rather than a statement about a fixture: it fails the moment someone adds a character the
    old code could not have decoded, which is precisely the event that took CI red.
    """
    real = subprocess.run

    def as_windows_would(*args: object, **kwargs: object) -> object:
        # Only a call that left the decision to the locale is redirected. One that states its own
        # encoding has made the whole decision - which is exactly what the fix does, so a fixed
        # call passes straight through here and an unfixed one meets cp1252.
        if kwargs.pop("text", False):
            kwargs["encoding"] = "cp1252"
        return real(*args, **kwargs)  # type: ignore[arg-type]

    _hook.subprocess.run = as_windows_would
    try:
        assert _hook.staged_text(_hook.BACKLOG) != "", (
            "the guard read nothing, so it proves nothing"
        )
        assert _hook.refusals("Closes (zz).", "") == []
    finally:
        _hook.subprocess.run = real
