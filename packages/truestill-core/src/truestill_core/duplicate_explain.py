"""Plain-language answers to "what did this match?" - one wording, shared by every surface.

**This exists because the app was the drifted twin.** The engine has always computed
:class:`~truestill_core.models.DuplicateMatch` - the matched path, the detection tier, whether it
was seen earlier in the same run or in a previous one, and the perceptual distance. The CLI
printed all of it. The app dropped every field at the payload boundary and rendered a count:
*"2,057 duplicates - identical to a kept file"*, with no way to learn **which** kept file.

`IMPLEMENTATION_STANDARDS.md` §9 requires a skipped outcome to be *counted **and named***. The
app counted. So this is a §9 repair, not a feature - and, separately, the single most-repeated
complaint about photo tools since 2007 is exactly this: a tool that declares a file a duplicate
and will not say what it matched.

The remedy is a shared home rather than a second copy of the wording (`ENGINEERING_STANDARD.md`
§4): `models.status_label` and `models.date_quality` already prove that pattern, and the
dual-hash rule proves the cost of skipping it. **Both surfaces phrase a match from here.**

**Wording rules**, from `(ccc)`'s plain-language audit:

* Name what happened, not the mechanism. "Identical to" beats "SHA-256 match, origin=catalog".
* A near-duplicate was **kept**. Say so, because the fear is that a tool silently deleted it.
* Never imply the user must act when nothing is wrong.

**Complexity: O(1)** per match - dict lookup and string formatting. No I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from truestill_core.models import DuplicateKind, DuplicateMatch, DuplicateOrigin

#: Where the match was seen. ``run`` means earlier in the batch being processed now; ``catalog``
#: means a previous run put it in the library. The distinction matters to a user deciding
#: whether something is already safely stored, so it is never collapsed into "a duplicate".
# Keyed by :class:`DuplicateOrigin` members but typed `str`, and that is the point rather
# than a looseness: a `StrEnum` member hashes as its own string, so the bare tokens the
# engine has always written find the same row - while the signature still admits the
# unrecognised token this function promises not to raise on.
_ORIGINS: dict[str, str] = {
    DuplicateOrigin.RUN: "earlier in this batch",
    DuplicateOrigin.CATALOG: "already on this drive",
}


def origin_phrase(origin: DuplicateOrigin | str) -> str:
    """Where the match lives, in words. Unknown values degrade to the raw token rather than
    raising: this is a display path, and a newer engine must not be able to break the screen
    describing it."""
    return _ORIGINS.get(origin, origin)


@dataclass(frozen=True, slots=True)
class DuplicateExplanation:
    """One match, in words a user can act on."""

    #: "Identical to" / "Looks like" - what kind of sameness was found.
    headline: str
    #: The file it matched. The whole point; never omitted.
    matched_path: str
    #: "already in your library" / "earlier in this batch".
    origin: str
    #: One sentence combining the above, for surfaces that render a single line.
    detail: str
    #: True when the file was kept and is worth a look, false when it was skipped.
    kept: bool


def explain_duplicate(match: DuplicateMatch) -> DuplicateExplanation:
    """Turn a match into the sentence both surfaces show.

    An exact match was **skipped** - keeping a second identical copy in one library is not
    custody, it is waste. A perceptual match was **kept**, and saying so is the point: the
    complaint this answers is from users who feared a tool had thrown something away.
    """
    where = origin_phrase(match.origin)
    if match.kind is DuplicateKind.EXACT:
        return DuplicateExplanation(
            headline="Identical to",
            matched_path=match.matched_path,
            origin=where,
            detail=f"Identical to {match.matched_path} - {where}. Not copied again.",
            kept=False,
        )
    closeness = (
        "" if match.distance is None else f" Closeness {match.distance}, where 0 is identical."
    )
    return DuplicateExplanation(
        headline="Looks like",
        matched_path=match.matched_path,
        origin=where,
        detail=(
            f"Looks like {match.matched_path} - {where}. Kept, not removed;"
            f" worth a look.{closeness}"
        ),
        kept=True,
    )


#: The one sentence that introduces a split, shared so the surfaces cannot disagree about what
#: happened to the files. **"Not copied again" is the whole claim** - nothing of the user's was
#: deleted, and an exact-duplicate report that reads as a deletion report is the single
#: most-repeated fear this module was written to answer.
ORIGIN_HEADLINE = "identical copies, not copied again"


@dataclass(frozen=True, slots=True)
class DuplicateSplit:
    """How many skipped duplicates matched where.

    **A count per origin, not a list per origin.** The lists are separately capped for display
    (`DUPLICATE_SAMPLE_LIMIT`); these are taken from every match, so the two can never imply
    different totals.
    """

    already_in_library: int = 0
    within_this_batch: int = 0
    #: Matches whose origin token neither value recognises. Kept rather than discarded so the
    #: parts always sum to the whole - see :func:`split_by_origin`.
    unclassified: int = 0

    @property
    def total(self) -> int:
        return self.already_in_library + self.within_this_batch + self.unclassified


def split_by_origin(matches: Iterable[DuplicateMatch]) -> DuplicateSplit:
    """Count matches by where their twin is.

    **An unrecognised origin is counted, never dropped.** `origin_phrase` is allowed to degrade
    an unknown token to itself because it is a display path and a newer engine must not be able
    to break a screen. A count has no such licence: silently discarding a match would make the
    parts stop summing to the whole, and a total that does not add up is exactly the kind of
    number a user cannot act on.
    """
    library = batch = other = 0
    for match in matches:
        if match.origin == DuplicateOrigin.CATALOG:
            library += 1
        elif match.origin == DuplicateOrigin.RUN:
            batch += 1
        else:
            other += 1
    return DuplicateSplit(library, batch, other)


def describe_split(split: DuplicateSplit) -> list[str]:
    """The lines a surface prints beneath a duplicate count. Empty when there is nothing to say.

    **A zero bucket prints no line.** Never-silent is about what happened, not about what did
    not: "0 already in your library" reads as a finding and invites someone to wonder what went
    wrong, when the honest report is the one statement that is true.
    """
    lines: list[str] = []
    if split.already_in_library:
        lines.append(f"{split.already_in_library:,} {origin_phrase(DuplicateOrigin.CATALOG)}")
    if split.within_this_batch:
        lines.append(
            f"{split.within_this_batch:,} matched another file {origin_phrase(DuplicateOrigin.RUN)}"
        )
    if split.unclassified:
        lines.append(
            f"{split.unclassified:,} matched a file recorded somewhere this build does not name"
        )
    return lines
