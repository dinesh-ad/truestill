"""What a move left in the source, and the sentence that names it.

A move skips a file already in the library and never touches its original. That is right -
deleting the original of a file this run did not move would be far worse - and until now it was
also **silent**. The consequence is worse than "nothing happened": the source is left PARTIALLY
emptied, some files gone and some still there, and the empty-folder offer that follows names the
folders the move did empty while saying nothing about the ones it did not.

Sibling of :func:`truestill_core.cleanup.plan_cleanup`, which answers the other half of the same
question, and the two must agree: a folder counted here still holds files, so `plan_cleanup`
drops it as ``OCCUPIED`` and never offers it. That agreement is pinned by
``test_the_cleanup_offer_never_names_a_folder_that_still_holds_files``.

**Copy mode is deliberately out of scope.** The originals always stay in a copy, that is what
the mode is called, and saying so after every run would be noise rather than news. Callers gate
on the mode; nothing here infers it.

**Complexity:** O(results), plus one ``stat`` per skipped duplicate. The ``stat`` is what makes
*remain* a claim about the disk rather than an inference from a status - "never deleted by this
run" is not "still there", and the sentence says the second thing.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from truestill_core.duplicate_explain import DuplicateSplit, describe_split
from truestill_core.models import ActionResult, ActionStatus, DuplicateOrigin

#: How many folders a report NAMES. Five, not twenty: this is read as one sentence, and twenty
#: folder names inline is a wall rather than an answer - measured on the rendered card. The rest
#: are counted, never dropped, so a truncated list can never read as a complete one.
FOLDER_LIMIT = 5


@dataclass(frozen=True, slots=True)
class LeftBehindFolder:
    """One folder and how much of the user's material is still sitting in it.

    ``folder`` is relative to the source root in POSIX form, and is **empty for the root
    itself** - there is no relative name for it, and inventing one would name a folder that is
    not there. The surfaces word that case; the fact stays empty.
    """

    folder: str
    files: int


@dataclass(frozen=True, slots=True)
class LeftBehind:
    """Files the move did not take, split by why and grouped by where.

    The reason split uses the vocabulary `duplicate_explain` established: *already in your
    library* means the source copy is redundant, *earlier in this batch* says nothing about the
    library at all - this run moved the twin in. They lead to opposite next actions, so no
    single "because" clause is written when both are present.
    """

    total: int
    already_in_library: int
    within_this_batch: int
    #: An origin token this build does not recognise. Counted rather than discarded so the parts
    #: always sum to the whole, exactly as `split_by_origin` does.
    unclassified: int
    folders: tuple[LeftBehindFolder, ...]
    #: How many folders there really are, before :data:`FOLDER_LIMIT`.
    folders_total: int


def files_left_in_source(
    results: list[ActionResult], source_root: Path, *, folder_limit: int = FOLDER_LIMIT
) -> LeftBehind | None:
    """Files still in the source after a move, or ``None`` when the move left nothing.

    Only ``DUPLICATE`` results qualify. ``FAILED`` is deliberately excluded: it is already
    counted and named on its own, and it means the opposite thing - *this file is not in your
    library* rather than *this file is in your library, which is why the original was left*.
    Folding them together would tell a user their photo may be lost when it is safely stored.
    """
    library = batch = other = 0
    folders: Counter[str] = Counter()
    for row in results:
        if row.status is not ActionStatus.DUPLICATE:
            continue
        source = row.resolution.decision.source
        try:
            if not source.exists():
                continue
        except OSError:
            continue
        folders[_folder_of(source, source_root)] += 1
        match = row.resolution.exact_duplicate
        origin = match.origin if match is not None else None
        if origin == DuplicateOrigin.CATALOG:
            library += 1
        elif origin == DuplicateOrigin.RUN:
            batch += 1
        else:
            other += 1
    if not folders:
        return None
    # Biggest first, then by name: a user reads the first name, and it should be where most of
    # their files are rather than wherever the walk happened to arrive first.
    ranked = sorted(folders.items(), key=lambda item: (-item[1], item[0]))
    return LeftBehind(
        total=sum(folders.values()),
        already_in_library=library,
        within_this_batch=batch,
        unclassified=other,
        folders=tuple(LeftBehindFolder(name, count) for name, count in ranked[:folder_limit]),
        folders_total=len(ranked),
    )


def _folder_of(source: Path, source_root: Path) -> str:
    """The containing folder, relative to the root where it can be.

    `discover` walks the source, so a file outside it should not arise; if it ever does, its own
    path is kept rather than the file being dropped, because a dropped file makes the count stop
    matching the disk.
    """
    try:
        return source.parent.relative_to(source_root).as_posix().removeprefix(".")
    except ValueError:
        return str(source.parent)


def describe_left_behind(left: LeftBehind | None) -> list[str]:
    """The lines a surface prints after a move. Empty when nothing was left.

    One folder and one reason produces the whole statement as a single sentence, which is the
    case this exists for. More than one folder names each with its count - *"3 files remain"* is
    weaker than *"3 files remain in D/E"*, and the data is there. More than one reason drops the
    "because" clause entirely and states the split, because with both present no single clause
    is true of every file.
    """
    if left is None or not left.total:
        return []
    reasons = _reason_lines(left)
    where = _where(left)
    verb = "file remains" if left.total == 1 else "files remain"
    head = f"{left.total:,} {verb} {where}"
    if len(reasons) == 1:
        return [f"{head} because {reasons[0]}."]
    return [f"{head}.", "Of those, " + "; ".join(reasons) + "."]


def _where(left: LeftBehind) -> str:
    hidden = left.folders_total - len(left.folders)
    # The bare "in D/E" reads best, and is only honest when D/E is the whole story - one folder
    # AND nothing cut by the cap. Otherwise the counted list, which admits what it left out.
    if len(left.folders) == 1 and not hidden:
        return f"in {left.folders[0].folder or 'the folder you selected'}"
    listed = ", ".join(
        f"{f.folder or 'the folder you selected'} ({f.files:,})" for f in left.folders
    )
    more = f", and {hidden:,} more folders" if hidden else ""
    return f"in {listed}{more}"


#: The clause that follows "because" when a reason is the *only* reason. When more than one is
#: present the counted lines come from `describe_split` instead, so the phrasing a user meets
#: here is the phrasing they already met on the duplicate tally.
_ONLY_REASON: tuple[str, str, str] = (
    "they were already on this drive",
    "an identical file from this batch was moved instead",
    "they matched a file recorded somewhere this build does not name",
)


def _reason_lines(left: LeftBehind) -> list[str]:
    """One clause per reason present. A zero prints nothing."""
    counts = (left.already_in_library, left.within_this_batch, left.unclassified)
    present = [clause for n, clause in zip(counts, _ONLY_REASON, strict=True) if n]
    if len(present) == 1:
        return present
    return describe_split(DuplicateSplit(*counts))


def will_remain_line(already_in_library: int) -> str | None:
    """What a **move preview** says about the files it will not take. ``None`` when there are
    none - a zero here reads as a finding and invites someone to wonder what went wrong.

    Deliberately a different sentence from :func:`describe_left_behind`: a preview answers *what
    will happen*, a result answers *what to do now*, and the result is the more important of the
    two because it is the only place the leftover files are explained after the fact.
    """
    if already_in_library <= 0:
        return None
    one = already_in_library == 1
    subject = "file here is" if one else "files here are"
    stays = "It stays where it is." if one else "They stay where they are."
    return f"{already_in_library:,} {subject} already on this drive and will not be moved. {stays}"
