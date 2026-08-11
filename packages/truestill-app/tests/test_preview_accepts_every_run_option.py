"""Every option that changes what a run does must reach the preview - `(acx)`.

**The defect this exists for.** `organize_run` accepted `skip_undated`; `organize_preview` did
not. So the screen offered a checkbox that changed the run and could not change the preview, and
the confirm control promised files the run would then skip. It survived because nothing anywhere
compared the two signatures, and no test could: the preview simply did not have the parameter to
be wrong about.

**Why this is a guard and not a note.** Two surfaces answering one question differently has been
recorded three times on this project. The first instances were recorded and not checkable - they
were about a rule written twice in prose. This one is mechanically checkable, because both halves
are functions in one module and Python will hand you their signatures.

**Scope, stated so a green run is not read as more than it is.** This checks the APP's own
preview/run pair only, and only that the preview *accepts* what the run accepts - not that it
does the same thing with it. A preview that took `skip_undated` and ignored it would pass here
and fail `test_the_preview_promise_equals_the_run.py`, which is the pair's other half. It says
nothing about the CLI, whose preview is a set of printers rather than a function.

`progress` and `cancel` are excluded by name: they are how a long job reports itself, not
decisions about what the run will do, and the run takes them through a different door.
"""

from __future__ import annotations

import inspect

from truestill_app.service import organize_preview, organize_run

#: Plumbing, not decisions. A parameter added here is a claim that it cannot change the answer.
NOT_A_DECISION = {"progress", "cancel"}


def _keyword_options(function: object) -> set[str]:
    return {
        name
        for name, parameter in inspect.signature(function).parameters.items()  # type: ignore[arg-type]
        if parameter.kind is inspect.Parameter.KEYWORD_ONLY and name not in NOT_A_DECISION
    }


def test_the_preview_accepts_every_option_the_run_accepts() -> None:
    """The forward direction: a run option the preview cannot see is a preview that can lie."""
    missing = _keyword_options(organize_run) - _keyword_options(organize_preview)
    assert not missing, (
        f"organize_run accepts {sorted(missing)} and organize_preview does not, so a preview "
        f"cannot answer for a run configured that way. Thread it through, or add it to "
        f"NOT_A_DECISION with the reason it cannot change the outcome."
    )


def test_the_guard_names_the_options_it_is_checking() -> None:
    """Cry-wolf half, and the non-vacuous half in one.

    A signature check that resolved to an empty set on both sides would pass forever and prove
    nothing - the failure mode of every comparison over data it fetches for itself. This pins
    that the thing being compared is really the run's options, including the one the defect was
    about, so the guard cannot quietly stop looking at anything.
    """
    options = _keyword_options(organize_run)
    assert "skip_undated" in options, "the option (acx) was about is no longer being compared"
    assert "mode" in options
    assert "refresh_metadata" in options
    assert not (options & NOT_A_DECISION), "plumbing leaked into the decision set"
