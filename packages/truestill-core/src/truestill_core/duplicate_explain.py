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

from dataclasses import dataclass

from truestill_core.models import DuplicateKind, DuplicateMatch

#: Where the match was seen. ``run`` means earlier in the batch being processed now; ``catalog``
#: means a previous run put it in the library. The distinction matters to a user deciding
#: whether something is already safely stored, so it is never collapsed into "a duplicate".
_ORIGINS: dict[str, str] = {
    "run": "earlier in this batch",
    "catalog": "already in your library",
}


def origin_phrase(origin: str) -> str:
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
