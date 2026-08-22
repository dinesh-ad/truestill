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
            text=True,
            check=False,
            timeout=30,
        )
    except OSError, subprocess.SubprocessError:  # pragma: no cover - no git in the environment
        return ""
    return done.stdout if done.returncode == 0 else ""


def _declared_closed() -> set[str]:
    log = _log()
    if not log:
        pytest.skip("no git history available to read")
    return set(_hook.CLOSES.findall(log))


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
    """
    repo = _repo(tmp_path, _OPEN, _BUILT)
    assert _hook_says(repo, "chore: unrelated\n\nCloses (zz).\n") == (0, "")
    assert _hook.refusals("Closes (zz).", "") == []
