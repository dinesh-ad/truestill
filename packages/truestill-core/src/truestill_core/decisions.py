"""The decisions a rescan cannot recompute, as a document that can live beside a drive marker.

A catalog can be lost - machine formatted, disk died, file corrupted. The photos survive on the
drives; **the decisions do not.** Nothing on disk knows "Wayanad"; a human typed it. Everything
else the catalog holds - hashes, dates, GPS, camera, categories, placements - is recomputable by
reading the files again, and is most of what makes a catalog megabytes rather than kilobytes.

**No server, decided rather than deferred.** The market leader has servers, a subscription and the
photos and still cannot restore a lost catalog. And a catalog holds GPS and timestamps, which are
personal data and a location history in practice, so "we only take folder names" would have been
false. This goes on the user's own drives or nowhere.

**Least recomputable first.** Every entry here except one is a name that could be retyped from
memory. `date_confirmations` is a human OVERRULING the evidence about when a photo was taken, and
re-reading the file reproduces the wrong answer they corrected - scanning actively undoes it.
`skipped_clusters` is the same class: lose it and every declined question is asked again.

**Membership travels as a signature, never as a list.** `events.signature` is already a SHA-256
over its sorted member SHA-256s, so a restore re-clusters and matches. Identical membership
reproduces the signature and the name re-attaches; a mismatch means membership changed, which is
exactly when the name must NOT be auto-applied. Correctness first - being 221 KB smaller at full
membership is the side effect.

**IDENTITY MUST TRAVEL INSIDE THE ROW IT IDENTIFIES.** That is what makes the signature work, and
trips needed the same treatment: their membership lives in `trip_days`, keyed by `trips.id`, and a
rowid is meaningless on a machine that has never seen this catalog. A document that carried those
ids looked like a mapping and was not - the first trip came back holding every other trip's days,
which is worse than a trip going missing because a wrong trip looks like a successful restore. So
a trip carries its OWN days. `trip_days.day` is a primary key, so days are disjoint across trips
and a day list identifies a trip exactly, the way a signature identifies an event.
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from truestill_core.drive import DriveReach, drive_path_hint, drive_reach
from truestill_core.drive_unwritable import explain_unwritable_drive
from truestill_core.event_review import propose_from_catalog
from truestill_core.events import EventCandidate, EventSettings

#: Bumped only when a reader must REFUSE a document, never for an added field. Adding a field is
#: forward-compatible by construction (see :func:`from_document`), so a bump would be a false alarm
#: that strands a user's names on a disk they can see.
FORMAT_VERSION = 1

#: Settings excluded from the document. `path_hint.drive.<uuid>` holds an absolute local path - a
#: username, a folder layout, and in one real library the existence of a Vault. This file
#: lands on a drive the user may lend or sell, and a path from another machine is useless anyway.
#: Matched by PREFIX so a future `path_hint.something` is excluded without another edit.
#:
#: `decisions.` is this feature's own bookkeeping and is excluded for a different reason: it is
#: not a decision, and restoring it onto another machine would carry that machine's answer to
#: "have I written the upgrade copy yet" - the document would ship the reason it is never written
#: again. Machine-local notes about the backup do not belong in the backup.
#: `catalog.` is this file's own bookkeeping about its query planner - where `ANALYZE` last ran -
#: and describes a database that exists only here.
_EXCLUDED_SETTING_PREFIXES = ("path_hint.", "decisions.", "catalog.")

#: When this catalog last put its decisions on a drive. Machine-local; see the exclusion above.
DECISIONS_SAVED_AT_KEY = "decisions.saved_at"

#: Top-level keys this version writes. Anything else in a document came from a newer version and
#: is carried through untouched - see :func:`from_document`.
_KNOWN_KEYS = frozenset(
    {
        "format",
        "written",
        "drive",
        "settings",
        "trips",
        "events",
        "skipped_clusters",
        "date_confirmations",
        "albums",
    }
)


@dataclass(frozen=True, slots=True)
class Decisions:
    """Everything a human decided, and nothing a machine can re-derive."""

    drive_uuid: str = ""
    drive_label: str = ""
    drive_notes: str | None = None
    settings: dict[str, str] = field(default_factory=dict)
    #: Each trip carries its own ``days``; see the module note on identity travelling in the row.
    trips: tuple[dict[str, Any], ...] = ()
    events: tuple[dict[str, Any], ...] = ()
    skipped_clusters: tuple[str, ...] = ()
    date_confirmations: tuple[dict[str, Any], ...] = ()
    albums: tuple[dict[str, Any], ...] = ()
    written: str = ""
    #: Sections a NEWER version wrote that this one does not understand. Held so a downgrade can
    #: write them back rather than deleting someone's data - see :func:`from_document`.
    unknown: dict[str, Any] = field(default_factory=dict)


def publishable_settings(settings: dict[str, str]) -> dict[str, str]:
    """The settings that may leave this machine. Excludes local paths; see the module note."""
    return {
        key: value
        for key, value in settings.items()
        if not key.startswith(_EXCLUDED_SETTING_PREFIXES)
    }


def to_document(decisions: Decisions) -> dict[str, Any]:
    """Render for the drive: plain JSON types, readable by a person with a text editor.

    Unknown sections are written back FIRST so a known key can never be shadowed by one.
    """
    document: dict[str, Any] = dict(decisions.unknown)
    document.update(
        {
            "format": FORMAT_VERSION,
            "written": decisions.written,
            "drive": {
                "uuid": decisions.drive_uuid,
                "label": decisions.drive_label,
                "notes": decisions.drive_notes,
            },
            "settings": publishable_settings(decisions.settings),
            "trips": [dict(trip) for trip in decisions.trips],
            "events": [dict(event) for event in decisions.events],
            "skipped_clusters": list(decisions.skipped_clusters),
            "date_confirmations": [dict(row) for row in decisions.date_confirmations],
            "albums": [dict(album) for album in decisions.albums],
        }
    )
    return document


def from_document(document: dict[str, Any]) -> Decisions:
    """Read a document, tolerating both older and newer versions. **Never raises on shape.**

    **Missing sections read as empty.** An older document simply has fewer; that is not corruption,
    and refusing it would strand names on a disk the user can see.

    **Unknown sections are KEPT, not ignored.** Tolerating them would be easy - skip and move on -
    but an older Truestill that reads a drive, restores, and later writes it back would then
    silently delete the newer version's data. The user downgrades once and loses their captions.
    Preservation is the requirement; surviving the read is only half of it.
    """
    drive = document.get("drive") or {}
    return Decisions(
        drive_uuid=str(drive.get("uuid") or ""),
        drive_label=str(drive.get("label") or ""),
        drive_notes=drive.get("notes"),
        settings=dict(document.get("settings") or {}),
        trips=tuple(dict(trip) for trip in document.get("trips") or ()),
        events=tuple(dict(event) for event in document.get("events") or ()),
        skipped_clusters=tuple(document.get("skipped_clusters") or ()),
        date_confirmations=tuple(dict(r) for r in document.get("date_confirmations") or ()),
        albums=tuple(dict(a) for a in document.get("albums") or ()),
        written=str(document.get("written") or ""),
        unknown={k: v for k, v in document.items() if k not in _KNOWN_KEYS},
    )


class SupersededReason(StrEnum):
    """WHY a value lost, which is not always "it was older". `(aia)`

    ⚠ **The model phrasing this class used to offer was "3 trip names on Backup B were older and
    were not used", and the CLI copied it verbatim into a sentence that is false twice over.**
    `_ranked` orders on `written` descending with `drive_uuid` ascending as a tiebreak, and its own
    docstring says ties are *"ordinary, not exotic ... most reconciles are entirely ties"* - so a
    loser is frequently not older at all, it merely sorts later on a hex string. An **undated**
    document loses for a third reason again, and was being told so twice in one output: once here
    as "older", once by `ReconcileReport.undated` as carrying no date.

    Recorded per loss so a surface can say which happened instead of asserting the common case.
    """

    #: The winner's document was genuinely written later.
    OLDER = "older"
    #: Same stamp. `drive_uuid` broke the tie - deterministic, and nothing to do with age.
    TIE = "tie"
    #: This document carries no date at all, so it cannot overrule one that does.
    UNDATED = "undated"


@dataclass(frozen=True, slots=True)
class NameSwap:
    """One value that lost, beside the one that replaced it. Both, or neither is legible.

    A user told *"Morning Market was not used"* cannot act; a user told *"Morning Market was
    replaced by placeholder B, from Backup B"* can. `(ahz)`
    """

    #: The value that did not survive the merge.
    lost: str
    #: The value that took its key.
    kept: str


@dataclass(frozen=True, slots=True)
class Superseded:
    """One drive's values for one section that were not used, and why.

    Structured rather than a sentence: `IMPLEMENTATION_STANDARDS` §2 leaves wording to the
    surfaces. ⚠ **A model phrasing used to live in this docstring and the CLI copied it**, which
    is how one unchecked cause reached a user - so the wording lives in `RESTORE_WORDING` and this
    type carries facts only.
    """

    section: str
    drive_label: str
    count: int
    #: Which of the three orderings put this value second. See :class:`SupersededReason`.
    #: **Required, with no default**: a default would let a new construction site describe a loss
    #: it never established, which is the whole defect this field exists to close.
    reason: SupersededReason
    #: What was lost, and what replaced it. ⚠ **This type carried a COUNT and no values until
    #: 2026-08-26**, so a user was told *"3 events were older and were not used"* and never which
    #: names - the one detail that would have made the line alarming, withheld by the one line that
    #: could have alerted them. `(ahz)`
    swaps: tuple[NameSwap, ...] = ()
    #: ⚠ **AUTHORITY decided this, not rank**: the drive the user named claimed the key over a
    #: document that OUTRANKED it. ⚠ **This field was `from_named_root` for one day** - "the loser
    #: was the drive you named" - which was the right report while rank still won. Step 2 made the
    #: named root authoritative, so it can no longer lose a key it holds and that reading became
    #: unreachable. The disagreement it marks is the same one; the direction reversed. `(ahz)`
    #:
    #: 🔑 **It is the only channel for the risk an authoritative restore carries**: a value that
    #: was genuinely newer, made on another machine, and has just been overruled.
    by_authority: bool = False


@dataclass(frozen=True, slots=True)
class ReconcileReport:
    """What the merge chose against, so a winner is never silent.

    A silent winner is the same defect as a silent skip: the user is told what came back and
    never told what did not, and the decision they are missing is the one they will look for.
    """

    superseded: tuple[Superseded, ...] = ()
    #: Drives whose document carried no `written` stamp. They contribute, but never overrule.
    undated: tuple[str, ...] = ()


def _ranked(documents: Sequence[Decisions]) -> list[Decisions]:
    """Documents newest first, and **deterministically** so.

    Two sorts rather than one key, because the two directions differ: `drive_uuid` ascending
    breaks ties, `written` descending orders the rest. Python's sort is stable, so the uuid order
    survives inside each stamp.

    **Ties are ordinary, not exotic:** one save writes to every reachable drive with a single
    stamp, so most reconciles are entirely ties. Falling back to argument order would make the
    answer depend on the order drives happened to be listed in, which is dict order wearing a
    different hat.

    **An undated document sorts last, and is not dropped.** Hand-edited or truncated, it is still
    someone's names, so it supplies anything nothing else has - but it cannot be trusted to
    overrule a document that says when it was written.

    ⚠ **AND SINCE `(ahz)`, RANK IS NOT THE LAST WORD** - `_merge_section` lets the drive the user
    NAMED claim its keys ahead of this order. **That is not the objection above returning.** The
    ruling here is about tie-breaking: falling back to *argument order* would make the answer
    depend on the order drives happened to be listed in, and it still would. What overrides rank is
    a **stated authority** - `restore <root>` is an explicit act, the user typed that path, and
    `_restore_documents_for` already rules that root special (*"read from the PATH, never from a
    lookup"*). A named root is a fact about intent; a list position is an accident of iteration.
    Both sentences are true, and they are here together so the next reader does not think the
    first one was quietly dropped.
    """
    ordered = sorted(documents, key=lambda d: d.drive_uuid)
    # `""` is lexicographically below every stamp, so descending order puts undated documents
    # last with no special case. A `bool(d.written)` component was written here first and a
    # mutation removing it killed no test - it could not, because it can never change the order.
    ordered.sort(key=lambda d: d.written, reverse=True)
    return ordered


def _why_it_lost(winner: Decisions, loser: Decisions) -> SupersededReason:
    """Which of `_ranked`'s three orderings put `loser` second. Pure.

    Mirrors `_ranked` exactly - undated first because `""` sorts below every stamp there too, so
    an undated document is never reported as merely "older".
    """
    if not loser.written:
        return SupersededReason.UNDATED
    if loser.written == winner.written:
        return SupersededReason.TIE
    return SupersededReason.OLDER


@dataclass(frozen=True, slots=True)
class _Section:
    """How one mergeable section is read, keyed and named. **Grouped because they travel together.**

    Three callables and a name arrived as four positional arguments and the linter said so at
    seven. They are one concept - *what this section is* - and splitting them across a signature is
    how a caller comes to pass `albums`' key function with `trips`' rows.
    """

    name: str
    rows_of: Callable[[Decisions], Sequence[dict[str, Any]]]
    key_of: Callable[[dict[str, Any]], object]
    #: The human-readable value, for the report. Defaults to `name`, which is right for every
    #: section a person types into.
    name_of: Callable[[dict[str, Any]], str] = lambda row: str(row.get("name") or "")


def _merge_section(
    ranked: Sequence[Decisions],
    section: _Section,
    losses: list[Superseded],
    *,
    named_root_uuid: str = "",
) -> tuple[dict[str, Any], ...]:
    """First value per identity key wins. **Per decision, never per document.**

    That is the whole distinction: "take the newest document's sections" would let a freshly
    formatted drive - whose empty document is by definition the newest - erase a full one.

    A later document holding an **identical** value is not reported. One save writes the same
    document to every drive, so most reconciles see several identical copies, and calling each a
    superseded loser would bury the one real disagreement in a list of non-events.

    🔑 **THE DRIVE THE USER NAMED CLAIMS ITS KEYS FIRST, ahead of rank.** `(ahz)` `restore <root>`
    is an explicit act - the user typed that path - and until 2026-08-26 a document found through a
    stored *hint* could outrank it purely by carrying a fresher clock. That is how re-organizing to
    recover from a lost catalog destroyed the names it was recovering: the recovery folder is
    registered as a drive, its document is published seconds later, and last-write-wins did the
    rest.

    ⚠ **PER KEY, NOT PER SECTION**, and the difference is the whole design. Authority is claimed
    one identity at a time, so another drive still contributes every trip the named root has never
    heard of. Per-section authority would silently discard those - the named root would answer for
    decisions it does not carry, which is the freshly-formatted-drive failure with a different
    name.
    """
    named = next((d for d in ranked if named_root_uuid and d.drive_uuid == named_root_uuid), None)
    # Rank position is kept so a loss can say whether AUTHORITY decided it: a value that lost to
    # the named root while OUTRANKING it is the one case a user may need to overrule.
    rank_of = {id(document): position for position, document in enumerate(ranked)}
    order = ranked if named is None else [named, *(d for d in ranked if d is not named)]

    chosen: dict[object, tuple[dict[str, Any], Decisions]] = {}
    beaten: dict[tuple[str, SupersededReason, bool], list[NameSwap]] = {}
    for document in order:
        for row in section.rows_of(document):
            key = section.key_of(row)
            if key not in chosen:
                chosen[key] = (row, document)
            elif chosen[key][0] != row:
                label = document.drive_label or document.drive_uuid
                winner = chosen[key][1]
                # The winning DOCUMENT is kept beside the winning row for this one reason: "why
                # did this lose" is a question about the two stamps, and the row does not carry
                # one. Reported rather than assumed - see `SupersededReason`.
                seat = (
                    label,
                    _why_it_lost(winner, document),
                    winner is named and rank_of[id(document)] < rank_of[id(winner)],
                )
                # ⚠ The VALUES, not a tally. Grouped by (drive, reason, by-authority) so one line
                # can name every swap it covers - a count alone is what `(ahz)` §6 was about.
                beaten.setdefault(seat, []).append(
                    NameSwap(lost=section.name_of(row), kept=section.name_of(chosen[key][0]))
                )
    losses.extend(
        Superseded(section.name, label, len(swaps), reason, tuple(swaps), by_authority)
        for (label, reason, by_authority), swaps in beaten.items()
    )
    return tuple(row for row, _ in chosen.values())


def _merge_confirmations(
    ranked: Sequence[Decisions], losses: list[Superseded]
) -> tuple[dict[str, Any], ...]:
    """Corrected dates, resolved on the ROW's ``confirmed_at`` rather than the document's stamp.

    **The exception, and it is not a detail.** A drive written last week can carry a correction a
    human made today on another machine: the document is old, the decision inside it is not.
    Every other section resolves on `written` because that is when the drive last heard about it;
    this one cannot, because a corrected date is the only decision with no second source. Losing
    it is unrecoverable - re-reading the file reproduces the wrong answer the human overruled.

    Ties on `confirmed_at` fall back to document rank, so the answer stays deterministic.
    """
    best: dict[str, tuple[str, str, dict[str, Any]]] = {}  # sha -> (confirmed_at, label, row)
    beaten: dict[str, int] = {}

    def lost(label: str) -> None:
        beaten[label] = beaten.get(label, 0) + 1

    for document in ranked:
        label = document.drive_label or document.drive_uuid
        for row in document.date_confirmations:
            sha = str(row.get("sha256") or "")
            at = str(row.get("confirmed_at") or "")
            current = best.get(sha)
            if current is None:
                best[sha] = (at, label, row)
            elif at > current[0]:
                if row != current[2]:
                    lost(current[1])
                best[sha] = (at, label, row)
            elif row != current[2]:
                lost(label)

    # OLDER is stated rather than defaulted, and it is genuinely true here: this merge orders on
    # the ROW's `confirmed_at` (see the docstring above), so a loser really did carry an earlier
    # correction. The document stamps play no part, so TIE and UNDATED cannot arise.
    # ⚠ **No swaps here, stated rather than defaulted.** This merge resolves on the ROW's
    # `confirmed_at`, and what it discards is an earlier CORRECTION of a date - there is no pair of
    # human-typed names to show, and printing a sha256 beside a sha256 would be noise wearing a
    # value's clothes. `from_named_root` is likewise false: the ranking here is not by document.
    losses.extend(
        Superseded("date_confirmations", label, n, SupersededReason.OLDER)
        for label, n in beaten.items()
    )
    return tuple(row for _, _, row in (best[sha] for sha in sorted(best)))


def _trip_key(trip: dict[str, Any]) -> object:
    """A trip's identity is its DAY SET, not its name.

    `(ack)`: the days are what survive leaving a catalog, and `trip_days.day` is a primary key so
    they are disjoint across trips. The consequence here is that **same days with a different
    name is a RENAME** - the newer name wins - rather than two trips or a conflict to escalate.
    """
    return tuple(sorted(str(day) for day in trip.get("days") or ()))


def reconcile_documents(
    documents: Sequence[Decisions], *, named_root_uuid: str = ""
) -> tuple[Decisions, ReconcileReport]:
    """Merge the documents from several drives into one set of decisions.

    **Newest wins per decision.** Every section resolves on the document's `written` stamp, with
    one exception that is not a detail: `date_confirmations` resolves on its own `confirmed_at`.
    A drive written last week can carry a correction a human made today on another machine, and a
    corrected date is the only decision with no second source - re-reading the file reproduces
    the wrong answer they overruled. Resolving it by document stamp loses it silently.

    **The drive block is not merged.** Each document describes a different drive, so there is no
    single answer; the result carries none and the caller applies each document's own. Collapsing
    them would invent a drive that does not exist.
    """
    ranked = _ranked(documents)
    losses: list[Superseded] = []
    confirmations = _merge_confirmations(ranked, losses)

    # Newest document wins per key; oldest applied first so later ones overwrite. Disagreements
    # are NOT reported: UI preferences churn per machine and per version, so a difference here is
    # not evidence of anyone's decision being overruled - the same reason `would_lose` ignores
    # them.
    settings: dict[str, str] = {}
    for document in reversed(ranked):
        settings.update(document.settings)

    skipped: dict[str, None] = {}
    for document in ranked:
        for signature in document.skipped_clusters:
            skipped.setdefault(str(signature), None)

    merged = Decisions(
        settings=settings,
        trips=_merge_section(
            ranked,
            _Section("trips", lambda d: d.trips, _trip_key),
            losses,
            named_root_uuid=named_root_uuid,
        ),
        events=_merge_section(
            ranked,
            _Section("events", lambda d: d.events, lambda e: str(e.get("signature") or "")),
            losses,
            named_root_uuid=named_root_uuid,
        ),
        skipped_clusters=tuple(sorted(skipped)),
        date_confirmations=confirmations,
        # `(acg)`: unioned rather than first-wins - see `_merge_albums` for why membership is the
        # one section with no authority to arbitrate.
        albums=_merge_albums(ranked),
        written=ranked[0].written if ranked else "",
    )
    return merged, ReconcileReport(
        superseded=tuple(losses),
        undated=tuple(d.drive_label or d.drive_uuid for d in ranked if not d.written),
    )


@dataclass(frozen=True, slots=True)
class ApplyReport:
    """What an apply changed, and what it deliberately did not."""

    applied: dict[str, int] = field(default_factory=dict)
    #: Decisions this catalog already held in a NEWER form. The drive's copy was correctly
    #: ignored and **there is nothing for the user to do**.
    already_newer_locally: dict[str, int] = field(default_factory=dict)
    #: Decisions kept in the document and not applied because this catalog has never scanned the
    #: content they belong to. **There IS an action**: plug in the drive that holds those photos,
    #: scan, re-apply. Nothing is dropped in the meantime.
    #:
    #: Separate from `already_newer_locally` since `(abx)`: they shared one field, and a restore
    #: hitting both produced one indistinguishable line for two situations needing opposite
    #: words. Counted rather than named, so a surface can say how many are waiting.
    awaiting_content: dict[str, int] = field(default_factory=dict)
    #: Event names whose signature matched nothing in this catalog. Reported, never guessed at.
    #:
    #: ⚠ **This said "so membership changed" until 2026-08-26, and that is an unchecked cause.**
    #: What is observed is only that `event_by_signature` returned nothing. It is equally
    #: consistent with this catalog holding no events at all - which is the case `restore` exists
    #: for - or holding the cluster unnamed, or a category flip. The CLI read this line and
    #: printed the guess. `(aia)`
    unmatched_events: tuple[str, ...] = ()
    #: How many events this catalog holds AT ALL, named or not. Distinguishes the two ways
    #: `unmatched_events` can be non-empty, exactly as `BakePlan.confirmed_anywhere` tells two
    #: zeroes apart: with none here, every document event misses and the reason is this catalog,
    #: not those photographs.
    events_here: int = 0
    #: Trips whose days are already claimed by a DIFFERENT trip here. A day belongs to at most one
    #: trip, so these cannot be applied at all - and a skip with no channel is how the absorbed-
    #: days defect stayed invisible. One meaning per field, deliberately.
    conflicting_trips: tuple[str, ...] = ()
    #: Trips the document carries no days for, so there is nowhere to put them. Distinct from a
    #: conflict: nothing is competing, the document simply does not say which days they are.
    trips_without_days: tuple[str, ...] = ()
    #: Sections this version carries but cannot yet apply.
    not_applied: tuple[str, ...] = ()
    #: Event names this run RE-CREATED: no row held the signature, but re-clustering this
    #: catalog's own timeline produced a group with the document's exact fingerprint, so the row
    #: and its file links were rebuilt from that group and the document's name. The restored
    #: half's detail - these count into ``applied["events"]``, never into ``withheld_count``.
    #: `(ahv)` stage 2.
    created_events: tuple[str, ...] = ()


class RestoreNote(StrEnum):
    """Every sentence `restore` prints that could state a CAUSE. `(aia)`"""

    NOTHING_NEW = "nothing_new"
    NOTHING_APPLIED = "nothing_applied"
    NO_EVENTS_HERE = "no_events_here"
    NO_SUCH_GROUP = "no_such_group"
    EVENT_CREATED = "event_created"
    CONFLICTING_TRIP = "conflicting_trip"
    TRIP_WITHOUT_DAYS = "trip_without_days"
    NOT_APPLIED = "not_applied"
    SUMMARY_PREVIEW = "summary_preview"
    SUMMARY_DONE = "summary_done"
    ALREADY_HELD = "already_held"
    AWAITING_CONTENT = "awaiting_content"
    LOST_OLDER = "lost_older"
    LOST_TIE = "lost_tie"
    LOST_UNDATED = "lost_undated"
    OVERRULED_BY_NAMED_ROOT = "overruled_by_named_root"
    DRIVE_HOLDS_MORE = "drive_holds_more"
    DRIVE_NAMES_DIFFERENTLY = "drive_names_differently"
    DRIVE_WRITTEN = "drive_written"


@dataclass(frozen=True, slots=True)
class RestoreWording:
    """One sentence a person reads, and whether it asks them to do something."""

    #: The words. `{}` placeholders are filled by the surface, never by this table.
    text: str
    #: True when the reader is being asked to act. Decides the CLI's marker - `!` against `-` -
    #: so a real loss cannot be printed in the "nothing to do" register by accident.
    actionable: bool


#: ⚠ **ONE WORDING HOME FOR EVERY SURFACE**, `STOP_WORDING`'s ruling applied to restore. `(aia)`
#:
#: **Every sentence here used to state a cause the code had not established.** They were not
#: mis-typed strings - each was a correct sentence about a situation that had not been checked,
#: which is why a test pinning the old words would have passed throughout. The census that found
#: them is in `research/backlog/aia.md`.
#:
#: ⚠ **A table rather than a derivation**, for `STOP_WORDING`'s reason (`migrate.py:160`): a member
#: added tomorrow raises `KeyError` here rather than being worded by an `else` nobody wrote for it,
#: and `test_restore_states_only_what_it_checked` asserts the table covers the enum.
#:
#: **Each entry names what the code actually checked.** If a wording asserts more than its comment
#: can justify, the wording is wrong - that is the standing rule this table exists to keep.
RESTORE_WORDING: Final[dict[RestoreNote, RestoreWording]] = {
    # Checked: `applied` is empty AND nothing was refused. Nothing to do is the whole truth.
    RestoreNote.NOTHING_NEW: RestoreWording(
        "nothing this catalog does not already have", actionable=False
    ),
    # Checked: `applied` is empty because every section was refused. ⚠ The old sentence covered
    # BOTH zeroes with the reassuring one - `NOTHING_CONFIRMED_NOTE`'s defect, in another command.
    RestoreNote.NOTHING_APPLIED: RestoreWording(
        "nothing was applied - see the reasons below", actionable=True
    ),
    # Checked: `event_by_signature` missed AND this catalog holds no events at all. The reason is
    # this catalog, and it is knowable - so it is said.
    # ⚠ **Per event, and it names the event.** A first draft aggregated this case to a count,
    # which said the knowable reason and dropped the names - and the names are the thing the user
    # came for. `test_restore_cli.py` caught it. Both arms name the event; only the reason differs.
    RestoreNote.NO_EVENTS_HERE: RestoreWording(
        "event '{name}' could not be matched: this catalog holds no events yet.\n"
        "    Its name is safe in the drive's decisions document.",
        actionable=True,
    ),
    # Checked: `event_by_signature` missed while other events DO exist here. Why is not known -
    # the photos may have been regrouped, or this group may never have been named on this machine.
    # ⚠ The old sentence picked one: "its photos have changed". Since `(ahv)` stage 2 this arm is
    # reached only after re-clustering also missed, and the sentence was already worded for
    # exactly that check - a shifted membership and a never-named group both simply lack the
    # fingerprint, and the code still cannot tell them apart, so it still does not say.
    RestoreNote.NO_SUCH_GROUP: RestoreWording(
        "event '{name}' has no match here: no group in this catalog has its fingerprint.\n"
        "    Its name is safe in the drive's decisions document.",
        actionable=True,
    ),
    # Checked: no event row had the signature, and a freshly proposed cluster of this catalog's
    # own timeline files DID - the row and its links were created from that cluster and the
    # document's name. Good news with nothing to do, so it must not read as a warning.
    RestoreNote.EVENT_CREATED: RestoreWording(
        "event '{name}' was re-created: this library's photos still form its exact group.",
        actionable=False,
    ),
    # Checked: `knows_content` is false - this catalog has not scanned the photo the correction
    # belongs to. The only sentence here that always had a remedy and was always honest; it moves
    # into the table so the CLI holds no sentences at all, not because it was wrong.
    RestoreNote.AWAITING_CONTENT: RestoreWording(
        "{count} {section} are waiting for photos this catalog has not scanned.\n"
        "    Plug in the drive holding them, scan, and restore again.",
        actionable=True,
    ),
    # Checked: every day this trip claims is already held by a DIFFERENTLY-NAMED trip here.
    # `trip_days.day` is a primary key, so this cannot be applied at all - it is not a partial.
    RestoreNote.CONFLICTING_TRIP: RestoreWording(
        "trip '{name}' could not be applied: its days already belong to a different trip\n"
        "    in this catalog. Its name is safe in the drive's decisions document.",
        actionable=True,
    ),
    # Checked: the document carries no days for this trip, so there is nowhere to put it.
    # Distinct from a conflict - nothing is competing.
    RestoreNote.TRIP_WITHOUT_DAYS: RestoreWording(
        "trip '{name}' could not be applied: the document does not say which days it covers.",
        actionable=True,
    ),
    # Checked: this version gathers the section onto a drive and cannot read it back.
    RestoreNote.NOT_APPLIED: RestoreWording(
        "{section} are carried on the drive but this version cannot restore them.\n"
        "    They are not lost - they stay in the drive's decisions document.",
        actionable=True,
    ),
    # ⚠ **BOTH HALVES IN ONE SENTENCE, ALWAYS** - including the zeroes. See `_SUMMARY_RULE`.
    RestoreNote.SUMMARY_PREVIEW: RestoreWording(
        "{restored} decision(s) would come back, {withheld} would not.", actionable=False
    ),
    RestoreNote.SUMMARY_DONE: RestoreWording(
        "{restored} decision(s) restored, {withheld} not restored.", actionable=False
    ),
    # Checked: a confirmation held here is the same age or newer. ⚠ The old sentence said "were
    # older than this machine's"; the comparison is `>=`, and ties count as already-held.
    RestoreNote.ALREADY_HELD: RestoreWording(
        "{count} {section} on the drive are the same age or older than this machine's\n"
        "    and were not applied. Nothing to do.",
        actionable=False,
    ),
    # Checked: ranked lower on a genuinely later stamp.
    RestoreNote.LOST_OLDER: RestoreWording(
        "{count} {section} on {label} were written earlier and were not used.", actionable=False
    ),
    # Checked: the SAME stamp, ordered by `drive_uuid`. ⚠ Reported as "older" until 2026-08-26,
    # and `_ranked` says ties are the ordinary case - so this was the common wrong answer.
    RestoreNote.LOST_TIE: RestoreWording(
        "{count} {section} on {label} were written at the same moment as another drive's\n"
        "    and were not used. Not an age: the drives are ordered by identity to keep the\n"
        "    answer stable.",
        actionable=False,
    ),
    # ⚠ **The drive the user NAMED lost.** `restore <root>` is an explicit act - they typed that
    # path - and a document found through a stored hint overruled it. Says WHICH values, both
    # sides, and which drive won, because the same sentence has to serve two opposite readings:
    # the recovery inversion `(ahz)` measured, AND its mirror - a genuinely newer rename made on a
    # second machine, which SHOULD win and which the user must be able to recognise as legitimate.
    # Naming both values is what lets them tell the two apart; a count never could.
    RestoreNote.OVERRULED_BY_NAMED_ROOT: RestoreWording(
        "{count} {section} on {label} were written later and were still not used:\n"
        "    {swaps}.\n"
        "    The drive you named holds the ones on the right, and a drive you name wins.\n"
        "    If the newer copy is a change you made on another machine, restore from THAT\n"
        "    drive instead - this run would replace it.",
        actionable=True,
    ),
    # Checked: the document carries no stamp. ⚠ Was reported as "older" AND separately as undated,
    # so one drive got two contradicting lines in one output.
    RestoreNote.LOST_UNDATED: RestoreWording(
        "{count} {section} on {label} were not used: that document carries no date, so it\n"
        "    cannot overrule one that does.",
        actionable=False,
    ),
    # Checked: a SET DIFFERENCE of identity keys is non-empty. ⚠ The old sentence said the
    # sections "exist there and NOT here", which is false whenever the catalog holds some of them.
    RestoreNote.DRIVE_HOLDS_MORE: RestoreWording(
        "The drive holds {sections} this catalog does not, and they will be gone.", actionable=True
    ),
    # ⚠ **A RENAME IS NOT A DISAPPEARANCE, and one sentence cannot honestly cover both.** Since
    # `would_lose` widened, a drive naming an event differently at the SAME signature counts as a
    # loss - correctly - and the sentence above would have described it as *"the drive holds events
    # this catalog does not"*, which is false: the catalog has that event, under another name. This
    # is that case, named, with both values so the reader can tell which one is theirs. `(ahz)`
    RestoreNote.DRIVE_NAMES_DIFFERENTLY: RestoreWording(
        "The drive names {count} {section} differently: {swaps}.\n"
        "    Discarding replaces the drive's names with this catalog's.",
        actionable=True,
    ),
    # Checked: the write returned success. ⚠ "The drive now matches this catalog" was contradicted
    # by `merge_onto_drive`, which deliberately PRESERVES sections this version does not know -
    # asserted by `test_restore_cli.py`'s own captions case. So state the act, not an end state.
    RestoreNote.DRIVE_WRITTEN: RestoreWording(
        "The drive's decisions were replaced with this catalog's.", actionable=False
    ),
}


#: `SupersededReason` -> the note for it. Separate from the table so the mapping is data too, and
#: a new reason with no note fails the exhaustiveness test rather than falling through.
def superseded_note(loss: Superseded) -> RestoreNote:
    """The sentence for one superseded group.

    ⚠ **The authority case outranks the reason**, deliberately. *Why* the loser ranked lower is the
    smaller fact when it did not lose on rank at all - it outranked the winner and was overruled by
    the drive the user named. That is the one case a user may need to reverse. `(ahz)`
    """
    if loss.by_authority:
        return RestoreNote.OVERRULED_BY_NAMED_ROOT
    return SUPERSEDED_NOTE[loss.reason]


def render_swaps(swaps: tuple[NameSwap, ...]) -> str:
    """``'Morning Market' -> 'placeholder B'``, joined. **One home, so both surfaces agree.**"""
    return ", ".join(f"{s.lost!r} -> {s.kept!r}" for s in swaps)


SUPERSEDED_NOTE: Final[dict[SupersededReason, RestoreNote]] = {
    SupersededReason.OLDER: RestoreNote.LOST_OLDER,
    SupersededReason.TIE: RestoreNote.LOST_TIE,
    SupersededReason.UNDATED: RestoreNote.LOST_UNDATED,
}


#: ⚠ **EVERY FIELD `ApplyReport` COMPUTES REACHES THE READER, BY LOOP AND NOT BY LIST.** `(ahx)`
#:
#: `not_applied`, `conflicting_trips` and `trips_without_days` were computed by this module and
#: printed by **nobody** - against `_print_restore_plan`'s own docstring, which promises *"the half
#: that is easy to leave out"*. Naming five fields is what produced three omissions; naming eight
#: would produce the fourth. So a surface loops `dataclasses.fields(ApplyReport)` and indexes this
#: table, and a field that is in neither this table nor `REPORT_FIELD_EXCEPTIONS` fails at import.
#:
#: 🔑 **This is the industry norm, not a local slip, which is the argument for the loop over three
#: more lines.** IBM's `RSTOBJ` restores 74 of 75 and reports *"74 restored"* - IBM's own manual
#: says *"You are not notified that 1 object was not restored."* Veeam VBO's explorer says
#: *"1 skipped, 1 restored"* while the job log and the API say *"restored successfully"* for
#: **both** - two surfaces disagreeing, and the trusted one wrong. IBM Spectrum Protect Plus
#: APAR IT31203: a partial-successful backup does not report the missing objects on restore. Adobe
#: Creative Cloud, twice: a green *"successfully restored"* for files that never appear. **Every
#: one is a report that names what it did and stays silent about what it did not, and none was
#: fixed by adding one more field.**
REPORT_FIELD_NOTE: Final[dict[str, RestoreNote]] = {
    "conflicting_trips": RestoreNote.CONFLICTING_TRIP,
    "trips_without_days": RestoreNote.TRIP_WITHOUT_DAYS,
    "not_applied": RestoreNote.NOT_APPLIED,
    "already_newer_locally": RestoreNote.ALREADY_HELD,
    "awaiting_content": RestoreNote.AWAITING_CONTENT,
}

#: Fields the loop cannot render, each with **why**. ⚠ **A declared exception is a decision; an
#: unhandled field is the shape that regrows** - so this is a table with reasons rather than a
#: skip-list, and the guard requires every field to be in exactly one of the two.
REPORT_FIELD_EXCEPTIONS: Final[dict[str, str]] = {
    "applied": (
        "a dict of section -> count rendered as an aligned table, not a sentence: it is the "
        "restored half, and the only field that is not an omission"
    ),
    "unmatched_events": (
        "needs the per-event sentence chosen by `unmatched_events_note`, because the reason is "
        "knowable only when `events_here` is zero - one field, two sentences. `(aia)`"
    ),
    "events_here": (
        "a DISCRIMINATOR, not a report: it exists to pick between the two sentences above and is "
        "never shown on its own, exactly as `BakePlan.confirmed_anywhere` is not"
    ),
    "created_events": (
        "the restored half's detail, not an omission: each name prints per event through "
        "EVENT_CREATED beside the applied table, and counting it into `withheld_count` would "
        "report a success as a loss. `(ahv)` stage 2"
    ),
}

#: ⚠ **THE PAIR RULE, taken from the one place the industry gets this right.** IBM's restore
#: messages report both halves in a single message - `CPF3773` *"&1 objects restored. &2 not
#: restored"*, and `CPF3839`/`CPF9003` the same shape. **Never a count of successes without the
#: count of omissions beside it, in the same sentence**, so silence is structurally impossible
#: rather than merely unlikely. Printed even when the second number is zero: a zero the user reads
#: is the difference between "nothing was left out" and "nobody looked".
_SUMMARY_RULE = "both halves, one sentence, zeroes included"


def withheld_count(report: ApplyReport) -> int:
    """How many decisions did NOT come back. The second half of every summary sentence.

    Derived from the fields themselves rather than a list, for `REPORT_FIELD_NOTE`'s reason: a new
    omission field joins this count without anyone remembering to add it.
    """
    total = len(report.unmatched_events)
    for name in REPORT_FIELD_NOTE:
        value = getattr(report, name)
        total += sum(value.values()) if isinstance(value, dict) else len(value)
    return total


def restored_count(report: ApplyReport) -> int:
    """How many decisions DID come back. The first half."""
    return sum(report.applied.values())


def nothing_applied_note(report: ApplyReport) -> RestoreNote:
    """Which of the two zeroes this is. `NOTHING_CONFIRMED_NOTE`'s shape, for restore.

    An empty `applied` means "there was nothing new" only when nothing was refused. A document of
    albums alone, or of events none of which match, produces the same empty dict - and saying
    *"nothing this catalog does not already have"* to that user is the reassuring half of a
    situation that has an unreassuring half.
    """
    refused = (
        report.unmatched_events
        or report.conflicting_trips
        or report.trips_without_days
        or report.not_applied
        or report.awaiting_content
    )
    return RestoreNote.NOTHING_APPLIED if refused else RestoreNote.NOTHING_NEW


def unmatched_events_note(report: ApplyReport) -> RestoreNote:
    """Whether the reason for an unmatched event is knowable. See `ApplyReport.events_here`."""
    return RestoreNote.NO_SUCH_GROUP if report.events_here else RestoreNote.NO_EVENTS_HERE


def _shared_decisions(catalog: Any) -> Decisions:
    """Every decision except the drive block, which is the only part that differs per drive.

    Split out so a save to N drives is **one pass over the catalog plus O(1) per drive** rather
    than N passes: the decision tables are catalog-wide, and re-reading them once per drive would
    make the cost of owning a second backup drive a second full read.
    """
    days_by_trip: dict[int, list[str]] = {}
    for day, trip_id in catalog.all_trip_days().items():
        days_by_trip.setdefault(int(trip_id), []).append(str(day))
    return Decisions(
        settings=publishable_settings(catalog.all_settings()),
        trips=tuple(
            {
                "name": r["name"],
                "slug": r["slug"],
                "start": r["start_date"],
                "end": r["end_date"],
                # The days, not the rowid that found them. See the module note.
                "days": sorted(days_by_trip.get(int(r["id"]), [])),
            }
            for r in catalog.all_trips()
        ),
        events=tuple(
            {
                "name": r["name"],
                "slug": r["slug"],
                "start": r["start_date"],
                "signature": r["signature"],
            }
            for r in catalog.all_events()
        ),
        skipped_clusters=tuple(str(r) for r in sorted(catalog.skipped_signatures())),
        date_confirmations=tuple(
            {
                "sha256": r["sha256"],
                "captured_at": r["captured_at"],
                "confirmed_at": r["confirmed_at"],
                "confirmed_by": r["confirmed_by"],
            }
            for r in catalog.all_date_confirmations()
        ),
        # `(acg)`: the members travel with the name. Without them the section was a bare list of
        # words - it named the albums and said nothing about what was in them, so a rebuilt
        # catalog got the vocabulary and none of the work.
        albums=_albums_with_members(catalog),
    )


def _albums_with_members(catalog: Any) -> tuple[dict[str, Any], ...]:
    """Every album, with the sha256 of every file in it. `(acg)`

    An album with no members is still written: it is a name the user made, and a section that
    dropped it would lose the vocabulary as well as the membership.
    """
    members = catalog.album_members()
    return tuple(
        {"name": name, "members": members.get(name, [])} for name in catalog.all_album_names()
    )


def _merge_albums(ranked: Sequence[Decisions]) -> tuple[dict[str, Any], ...]:
    """Album sections from every document, **unioned per name**. `(acg)`

    🔑 **UNION, NOT FIRST-WINS, AND THE REASON IS THAT MEMBERSHIP IS APPEND-ONLY.** `_merge_section`
    takes the first value per identity key and reports the rest as `Superseded`, which is right for
    a trip's days - one authority answers for them. Album membership has no authority: two drives
    routinely hold *different partial views* of one album, because each was written by the ingest
    that ran there. Taking the first would silently drop every member the other drive knew about,
    which is the exact harm `(acg)` exists to remove, reintroduced one layer up.

    ⚠ **Union cannot resurrect a removal, checked rather than assumed**: nothing deletes membership.
    `grep -rn "file_albums" packages/*/src` finds exactly two writers, both
    ``INSERT OR IGNORE``, and no ``DELETE`` anywhere. Should a remove ever ship, this merge has to
    be revisited in the same commit - a union over a table that can lose rows is how a deleted
    thing comes back.

    Nothing is superseded here, so no loss is reported: with a union there is no loser.
    """
    members: dict[str, list[str]] = {}
    for document in ranked:
        for row in document.albums:
            name = str(row.get("name") or "")
            if not name:
                continue
            known = members.setdefault(name, [])
            known.extend(s for s in row.get("members") or () if s not in set(known))
    return tuple({"name": n, "members": sorted(set(members[n]))} for n in sorted(members))


def _with_drive(shared: Decisions, drive: Any, drive_uuid: str) -> Decisions:
    """The shared decisions, addressed to one drive."""
    return replace(
        shared,
        drive_uuid=str(drive["uuid"]) if drive else drive_uuid,
        drive_label=str(drive["label"]) if drive else "",
        drive_notes=drive["notes"] if drive else None,
    )


def gather_decisions(catalog: Any, drive_uuid: str) -> Decisions:
    """Read the decisions a rescan could not recompute. **Read-only; writes nothing.**

    Column-by-column rather than ``SELECT *``, and that is the privacy guard rather than a style
    preference: a new column added to `files` or `settings` later cannot arrive on a user's drive
    by default. Every field here was chosen; nothing is inherited.
    """
    return _with_drive(_shared_decisions(catalog), catalog.drive_row(drive_uuid), drive_uuid)


def _apply_trips(
    catalog: Any,
    trips: tuple[dict[str, Any], ...],
    bump: Callable[[str], None],
    *,
    apply: bool,
) -> tuple[list[str], list[str]]:
    """Restore trips by their own days. Returns ``(conflicting, dayless)`` names.

    **A day belongs to at most one trip** (`trip_days.day` is a primary key), which is what makes
    a day list an identity rather than a hint - and what makes every outcome here decidable
    without a rowid.
    """
    conflicting: list[str] = []
    dayless: list[str] = []
    # Day -> the name of the trip holding it. Read once and kept in step as trips are created, so
    # a document that names one day twice cannot make `create_trip` fail on the day primary key.
    claimed_days: dict[str, str] = catalog.named_trip_days()

    for trip in trips:
        name = str(trip["name"])
        days = sorted(str(day) for day in trip.get("days") or ())
        if not days:
            dayless.append(name)
            continue
        holders = {claimed_days.get(day) for day in days}
        if holders == {name}:
            continue  # already restored, every day of it: a second apply is a no-op, not a clash
        if holders != {None}:
            # A partial claim is not a partial restore - it is a trip that cannot be applied at
            # all. Reported rather than skipped: silence here is what let one trip absorb
            # another's days with nothing saying so.
            conflicting.append(name)
            continue
        if apply:
            catalog.create_trip(
                name=name,
                slug=str(trip["slug"]),
                start_date=str(trip["start"]),
                end_date=str(trip["end"]),
                days=days,
            )
        for day in days:
            claimed_days[day] = name
        bump("trips")

    return conflicting, dayless


@dataclass(frozen=True, slots=True)
class _DocumentFirstSettings:
    """``get_setting`` that prefers the DOCUMENT being restored over the catalog's value.

    The floor restore re-clusters with must be the restored document's (`(ahv)` stage 2): the
    preview pass runs before any setting is written, so reading the catalog there would honour
    the pre-restore value on the one run where the document is authoritative - and would let
    the preview and apply passes propose different clusters, which `_cmd_restore` depends on
    never happening. Document first, catalog fallback, identically in both passes.
    """

    decisions: Decisions
    catalog: Any

    def get_setting(self, key: str) -> str | None:
        if key in self.decisions.settings:
            return str(self.decisions.settings[key])
        return self.catalog.get_setting(key)  # type: ignore[no-any-return]


def _restorable_clusters(catalog: Any, decisions: Decisions) -> dict[str, EventCandidate]:
    """Every current cluster by signature, so a document event can be re-created. `(ahv)`.

    Proposed over every registered drive - an event's copies live where they live - at the floor
    the DOCUMENT carries. Free at library scale: measured 0.12s over two drives of 9,189
    timeline rows each, so running it in both the preview and the apply pass costs nothing.
    """
    floor = EventSettings.from_catalog(_DocumentFirstSettings(decisions, catalog)).min_files
    clusters: dict[str, EventCandidate] = {}
    for row in catalog.registered_drives():
        for candidate in propose_from_catalog(catalog, str(row["uuid"]), min_files=floor):
            clusters.setdefault(candidate.signature, candidate)
    return clusters


def _apply_events(
    catalog: Any,
    decisions: Decisions,
    bump: Callable[[str], None],
    *,
    apply: bool,
) -> tuple[list[str], list[str]]:
    """The events section: rename on a match, CREATE on a re-clustered match, report the rest.

    `_apply_trips`'s shape, returns ``(unmatched, created)``.
    """
    unmatched: list[str] = []
    created: list[str] = []
    clusters = _restorable_clusters(catalog, decisions) if decisions.events else {}
    for event in decisions.events:
        signature = str(event["signature"])
        existing = catalog.event_by_signature(signature)
        if existing is None:
            candidate = clusters.get(signature)
            if candidate is not None:
                # No row, but this catalog's own timeline still forms EXACTLY this group - the
                # signature is a hash over member sha256s, so the match is the membership. The
                # document supplies the one thing the cluster cannot (the human's name); the
                # cluster supplies everything the document deliberately omits (members, count).
                # After a rebuild the `events` table is empty and this is every named event's
                # path back. `(ahv)` stage 2.
                if apply:
                    event_id = catalog.record_event(
                        name=str(event["name"]),
                        slug=str(event["slug"]),
                        start_date=str(event["start"]),
                        file_count=candidate.count,
                        signature=signature,
                    )
                    catalog.set_event_id([item.sha256 for item in candidate.items], int(event_id))
                created.append(str(event["name"]))
                bump("events")
                continue
            # ⚠ **Nothing here has that signature - no event row AND, since `(ahv)` stage 2, no
            # freshly proposed cluster either. WHY is still not established and must not be
            # asserted** - this said "Membership changed, so this is not that event" and the CLI
            # printed it as fact; a shifted membership and a group never named here both simply
            # lack the fingerprint. An empty `events` table alone no longer forces this branch:
            # only a group the library no longer forms does. `(aia)`
            unmatched.append(str(event["name"]))
            continue
        if existing["name"] != event["name"]:
            if apply:
                catalog.record_event(
                    name=str(event["name"]),
                    slug=str(event["slug"]),
                    start_date=str(event["start"]),
                    file_count=int(existing["file_count"] or 0),
                    signature=signature,
                )
            bump("events")
    return unmatched, created


def _apply_albums(catalog: Any, decisions: Decisions, *, apply: bool) -> tuple[int, int]:
    """Restore album membership by content. `(acg)`

    🔑 **A member is a sha256, and location never enters.** `file_albums` joins to ``files``, not
    ``file_copies``, so an album binds a name to *content*. `(aba)`'s distinction between *"not at
    the recorded path"* and *"not on this drive"* is about a **copy**, and an album has no copies -
    a member whose only copy has moved, or is on a drive in a drawer, is still a member.

    So there are two outcomes, not three. Content this catalog knows is applied. Content it does
    not know is **kept in the document and counted**, never dropped: `awaiting_content`'s own words
    are *"There IS an action: plug in the drive that holds those photos, scan, re-apply. Nothing is
    dropped in the meantime."*
    """
    changed = waiting = 0
    for album in decisions.albums:
        name = str(album.get("name") or "")
        if not name:
            continue
        members = [str(sha) for sha in album.get("members") or ()]
        here = [sha for sha in members if catalog.knows_content(sha)]
        waiting += len(members) - len(here)
        if not catalog.album_needs(name, here):
            continue
        if apply:
            catalog.record_album_members(name, here)
        changed += 1
    return changed, waiting


def apply_decisions(catalog: Any, decisions: Decisions, *, apply: bool = True) -> ApplyReport:  # noqa: PLR0912
    """Write the decisions into a catalog. **Idempotent**: a second apply changes nothing.

    Every branch asks whether the catalog already holds this decision before writing, so the count
    reported is what actually changed rather than what was offered.
    """
    applied: dict[str, int] = {}
    newer_locally: dict[str, int] = {}
    awaiting: dict[str, int] = {}

    def bump(section: str) -> None:
        applied[section] = applied.get(section, 0) + 1

    def count(where: dict[str, int], section: str) -> None:
        where[section] = where.get(section, 0) + 1

    if decisions.drive_uuid:
        row = catalog.drive_row(decisions.drive_uuid)
        if row is None or (decisions.drive_label and row["label"] != decisions.drive_label):
            if apply:
                catalog.upsert_drive(
                    uuid=decisions.drive_uuid, label=decisions.drive_label or "drive"
                )
            bump("drive")

    for key, value in decisions.settings.items():
        if catalog.get_setting(key) != value:
            if apply:
                catalog.set_setting(key, value)
            bump("settings")

    conflicting, dayless = _apply_trips(catalog, decisions.trips, bump, apply=apply)

    unmatched, created = _apply_events(catalog, decisions, bump, apply=apply)

    known_skips = catalog.skipped_signatures()
    for signature in decisions.skipped_clusters:
        if signature not in known_skips:
            if apply:
                catalog.record_skip(signature)
            bump("skipped_clusters")

    for confirmation in decisions.date_confirmations:
        sha = str(confirmation["sha256"])
        incoming_at = str(confirmation.get("confirmed_at") or "")
        held = catalog.date_confirmation_for(sha)
        if held is not None:
            # NEVER overwrite a later correction with an earlier one. This is the only decision
            # with no second source: the file reproduces the wrong answer the human corrected, so
            # an overwrite is unrecoverable. Ties count as already-held, not as a change.
            if str(held["confirmed_at"] or "") >= incoming_at:
                if str(held["captured_at"]) != str(confirmation["captured_at"]):
                    # Ours is newer and different: theirs was correctly ignored, no action.
                    count(newer_locally, "date_confirmations")
                continue
        elif not catalog.knows_content(sha):
            # The content is not in this catalog yet. The confirmation is KEPT in the document
            # and simply not applied; a later scan plus a re-apply lands it. A different
            # situation from the branch above, with a different answer for the user, which is
            # why it is counted somewhere else - see `(abx)`.
            count(awaiting, "date_confirmations")
            continue
        if apply:
            catalog.confirm_date(
                sha,
                str(confirmation["captured_at"]),
                confirmed_by=confirmation.get("confirmed_by"),
            )
        bump("date_confirmations")

    changed_albums, albums_waiting = _apply_albums(catalog, decisions, apply=apply)
    if changed_albums:
        applied["albums"] = changed_albums
    if albums_waiting:
        awaiting["albums"] = albums_waiting

    return ApplyReport(
        applied=applied,
        events_here=catalog.event_count(),
        already_newer_locally=newer_locally,
        awaiting_content=awaiting,
        unmatched_events=tuple(unmatched),
        conflicting_trips=tuple(conflicting),
        trips_without_days=tuple(dayless),
        # `(acg)`: albums are applied now, so this no longer names them. The field stays: it is
        # the channel for a section this function deliberately does not write, and emptying the
        # tuple is what "we now do this" looks like.
        not_applied=(),
        created_events=tuple(created),
    )


@dataclass(frozen=True, slots=True)
class RestoreReport:
    """Everything one restore did, and everything it deliberately did not."""

    reconciled: ReconcileReport
    applied: ApplyReport


def apply_documents(
    catalog: Any,
    documents: Sequence[Decisions],
    *,
    apply: bool = True,
    named_root_uuid: str = "",
) -> RestoreReport:
    """Reconcile the documents from several drives and apply the result. **One call, both halves.**

    **The per-drive loop is structural rather than remembered.** `reconcile_documents` returns a
    result with an empty drive block - each document is about a different drive, so there is no
    single answer - which means drive labels are restored only by walking the documents
    themselves. A restore command that had to remember that loop would one day not, and the
    symptom is a drive coming back unnamed, indistinguishable from one the user never named. So
    the loop lives here, where the merge is, and there is no sequence for a caller to get wrong.

    A label is a decision: the user typed it. It is simply the one decision that cannot be merged.
    """
    merged, reconciled = reconcile_documents(documents, named_root_uuid=named_root_uuid)
    report = apply_decisions(catalog, merged, apply=apply)

    restored_drives = 0
    for document in documents:
        if not document.drive_uuid:
            continue
        row = catalog.drive_row(document.drive_uuid)
        if row is None or (document.drive_label and str(row["label"]) != document.drive_label):
            if apply:
                catalog.upsert_drive(
                    uuid=document.drive_uuid, label=document.drive_label or "drive"
                )
            restored_drives += 1

    if restored_drives:
        report = replace(
            report,
            applied={**report.applied, "drive": report.applied.get("drive", 0) + restored_drives},
        )
    return RestoreReport(reconciled=reconciled, applied=report)


@dataclass(frozen=True, slots=True)
class DriveNotice:
    """What a surface should say about the decisions sitting on one drive.

    **Recognition and wording live here; presentation stays with each surface** - the same split
    `catalog_busy` makes, and for the same reason: `truestill-cli` and `truestill-app` share only
    core, and §4 rules that one contract written twice gets one home rather than a second test.
    """

    #: The document's own `written` stamp, read from the drive. Never stored locally: the drive's
    #: copy is the truth about the drive, and a second copy here could disagree with it.
    saved_at: str = ""
    #: Sections this drive carries that the catalog does not - the offer to restore. Empty on
    #: every ordinary re-attach, which is what keeps this signal rather than noise.
    awaiting_restore: tuple[str, ...] = ()
    #: Sections the catalog holds that this drive's copy does not - the staleness line, and the
    #: exact mirror of the offer above.
    #:
    #: **Not a timestamp comparison, because the data for one does not exist:** `trips`, `events`,
    #: `albums` and `settings` carry no date at all, so a `MAX` over the decision tables covers
    #: two sixths of them and reports a drive current while it is missing a rename made today.
    #: The stamp was only ever a proxy for "does this copy match", so the copy is compared.
    #:
    #: **Every reachable drive is meant to hold every decision** - the save writes the
    #: catalog-wide set to all of them - so a difference here is staleness rather than a drive
    #: legitimately holding less.
    stale: tuple[str, ...] = ()
    #: The three-line refusal, when this version must not read the document at all.
    refusal: str | None = None


def refusal_for(root: Path, version: int) -> str:
    """What a person sees when their drive's document is newer than this Truestill.

    **The order is the message.** Safe and readable first, because the person hitting this is
    least equipped to diagnose it and most likely to be mid-crisis - "we cannot read your backup"
    without that line reads as data loss. Then why. Then the remedy, naming the command.

    **Nothing here offers to fix, convert or overwrite it.** The dangerous action is the one an
    anxious user would most want, and it must not be on offer.
    """
    return (
        f"Your names are safe and readable: {root / DECISIONS_NAME}\n"
        "is plain text and opens in any editor, with no Truestill at all.\n"
        f"This version cannot use them - they were written by a newer Truestill "
        f"(format {version}; this one reads {FORMAT_VERSION}).\n"
        f"Upgrade Truestill, then run:  truestill restore {root}"
    )


def notice_for(root: Path, mine: Decisions) -> DriveNotice | None:
    """What to say about ``root``'s decisions, given what this catalog already holds.

    ``None`` when the drive carries no document at all, which is most folders: silence rather
    than a line reporting the absence of something.

    **The caller gathers ``mine`` once.** A listing walks every reachable drive, and gathering the
    catalog's decisions per drive would turn one full read into N.
    """
    found = read_decisions(root)
    if not found.found:
        return None
    if found.too_new:
        return DriveNotice(refusal=refusal_for(root, found.format_version))
    if found.decisions is None:
        return DriveNotice()
    return DriveNotice(
        saved_at=found.decisions.written,
        awaiting_restore=would_lose(found.decisions, mine),
        stale=would_lose(mine, found.decisions),
    )


#: The document's filename, beside `.truestill-drive.json` at a drive root. A sibling rather than
#: a section of the marker: the marker is identity - tiny, stable, read on every reach check - and
#: this churns.
DECISIONS_NAME = ".truestill-decisions.json"


@dataclass(frozen=True, slots=True)
class WriteOutcome:
    """What happened when a document was offered to a drive. **Never an exception.**"""

    written: bool
    path: Path | None = None
    #: Plain words for a person, when the drive would not take it. `None` on success.
    error: str | None = None


def write_decisions(root: Path, decisions: Decisions) -> WriteOutcome:
    """Put the document on a drive, atomically, and **never raise**.

    **Atomic, because this is the only copy of names a human typed.** Written to a sibling temp
    file, flushed, `fsync`ed, then `os.replace`d over the target - so a crash leaves either the
    previous good document or the new one, never a half of either. A truncated file at the right
    path is worse than no file, because it looks like a backup.

    **The temp sits in the SAME directory as the target**, which is what makes the rename atomic:
    a temp in the system temp directory would turn the final step into a copy across filesystems,
    which is exactly the non-atomic write this exists to avoid.

    **Nothing here may propagate into the caller.** Naming a trip must succeed even when the drive
    write does not - a decision lost because its own backup failed is the worst trade available -
    so every failure comes back as a reported outcome. A read-only disk, a full one and one pulled
    out mid-write are ordinary events for removable media, not exceptions.
    """
    if not root.is_absolute():
        # `Path("")` normalises to `Path(".")`, which IS a directory - so an `is_dir` check alone
        # lets an empty root write the document into the working directory. Caught by this
        # module's own test doing exactly that; requiring it turns a silent misfile into a
        # reported refusal.
        #
        # ⚠ **This said "a drive root is always absolute in practice" and that was FALSE**, which
        # is why nobody checked. `truestill organize src dest` stored `dest` verbatim and every
        # save here refused for the life of that drive - the document was never written and the
        # only durable copy of a user's trip and event names stayed in the catalog. `(ahu)`
        #
        # What makes the claim true now is `drive.remember_drive_path`, the single writer of
        # `path_hint.`, which stores `Path(...).absolute()` - and `test_no_site_writes_a_drive_
        # path_hint_directly` keeps it the only one. An invariant asserted here and enforced
        # nowhere is what this comment used to be.
        return WriteOutcome(written=False, error="a drive root must be a full path")
    if not root.is_dir():
        return WriteOutcome(written=False, error="the drive is not there any more")

    target = root / DECISIONS_NAME
    temp = root / f"{DECISIONS_NAME}.writing"
    try:
        payload = json.dumps(to_document(decisions), indent=2, sort_keys=True) + "\n"
        with temp.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(target)
    except OSError as error:
        # A drive that will not take the write may not take the cleanup either.
        with contextlib.suppress(OSError):
            temp.unlink(missing_ok=True)
        return WriteOutcome(written=False, error=explain_unwritable_drive(error))
    return WriteOutcome(written=True, path=target)


@dataclass(frozen=True, slots=True)
class DocumentOnDrive:
    """What is already at a drive root. **Never an exception.**"""

    #: A file is there. True even when it could not be read - which is the case that matters.
    found: bool = False
    decisions: Decisions | None = None
    #: Why it could not be read. `None` when there was nothing to read, or the read worked.
    error: str | None = None
    #: The document's own `format`. `0` when there was nothing readable to ask.
    format_version: int = 0

    @property
    def too_new(self) -> bool:
        """Written by a version this one must refuse rather than interpret.

        Derived rather than stored: two fields that can disagree about one fact is the defect
        `(abv)` was, in miniature.
        """
        return self.format_version > FORMAT_VERSION


def read_decisions(root: Path) -> DocumentOnDrive:
    """Read the document at a drive root, if there is one. **Never raises.**

    **`found` and `decisions` are separate answers on purpose.** "Nothing is there" and "something
    is there and I cannot read it" lead to opposite actions: the first may be written over freely,
    the second must not be touched. Collapsing them to `None` is how a damaged copy of somebody's
    names becomes no copy at all.

    ⚠ **Invalid UTF-8 is the second case, not an exception.** `(aje)`. ``Path.read_text`` raises
    ``UnicodeDecodeError`` (a ``ValueError``, **not** an ``OSError``), so catching only
    ``OSError`` here let one bad byte propagate. That raise is load-bearing: both
    ``catalog_session.open_catalog`` call sites - the upgrade write on entry and the dirty save on
    exit - are unguarded, because this function promised never to raise. One damaged document on a
    reachable drive then bricked every command that opens a catalog. ``drive.read_marker`` already
    caught ``UnicodeDecodeError`` beside ``OSError``; this matches that shape.
    """
    target = root / DECISIONS_NAME
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DocumentOnDrive()
    except OSError as error:
        return DocumentOnDrive(found=True, error=explain_unwritable_drive(error))
    except UnicodeDecodeError:
        # Bytes that are not UTF-8 still hold someone's names (often recoverable by hand). Same
        # refusal as unparseable JSON: found, no decisions, do not overwrite.
        return DocumentOnDrive(found=True, error="the file on the drive is not readable as text")
    try:
        document = json.loads(text)
    except ValueError:
        return DocumentOnDrive(found=True, error="the file on the drive is not readable JSON")
    return _interpret(document)


def _interpret(document: Any) -> DocumentOnDrive:
    """Version-gate a parsed document, then read it. Split from the I/O above so each half has
    one job: that one turns a disk into a value, this one decides whether we may act on it."""
    if not isinstance(document, dict):
        return DocumentOnDrive(
            found=True, error="the file on the drive is not a decisions document"
        )

    # Missing reads as current, the same way a missing section reads as empty: a hand-edited
    # document is not evidence of a newer version, and refusing it would strand names on a disk
    # the user can see.
    try:
        version = int(document.get("format", FORMAT_VERSION))
    except (TypeError, ValueError):
        return DocumentOnDrive(
            found=True, error="the file on the drive does not say which format it is"
        )

    if version > FORMAT_VERSION:
        # A bump means a reader must REFUSE - that is what `FORMAT_VERSION` is for. Refusing is
        # not the stranded-names failure: the names are still there, still readable in a text
        # editor, and the remedy is one upgrade away, which is why the message names it.
        return DocumentOnDrive(
            found=True,
            format_version=version,
            error=(
                f"these decisions were written by a newer Truestill (format {version}; "
                f"this one reads {FORMAT_VERSION}) - upgrade Truestill to use them"
            ),
        )

    return DocumentOnDrive(found=True, decisions=from_document(document), format_version=version)


#: Sections compared before a write, to refuse one that would lose decisions the drive already
#: holds. `settings` is deliberately absent: UI preferences churn per machine and per version, so
#: a difference there is not evidence of another catalog's work.
#: ⚠ **IDENTITY -> VALUE, and both halves matter.** `(ahz)` step 3
#:
#: This was identity ALONE, a set of keys, so *"the drive holds nothing this catalog is missing"*
#: was true of a drive holding `Morning Market` while the catalog held `placeholder B` **at the
#: same signature** - and the save overwrote the real name without a word. A name regression under
#: an unchanged identity is a loss; it was invisible because nothing compared values.
#:
#: 🔑 **The keys match the MERGE's keys**, deliberately. Trips key on the day set (`_trip_key`),
#: not the name - keying them by name is what made a rename look like a disappearance, and one
#: concept keyed two ways in one module is the shape this repo keeps filing letters about. ⚠ The
#: cost, stated: dayless trips all key to `()` and collapse together here, exactly as they do in
#: the merge. `ApplyReport.trips_without_days` is where that is reported.
_LOSS_KEYS: tuple[tuple[str, Callable[[Decisions], dict[object, str]]], ...] = (
    ("trips", lambda d: {_trip_key(t): str(t.get("name") or "") for t in d.trips}),
    ("events", lambda d: {str(e.get("signature")): str(e.get("name") or "") for e in d.events}),
    # No value of its own: a skipped cluster IS its signature, so it can go missing but not change.
    ("skipped_clusters", lambda d: {str(s): "" for s in d.skipped_clusters}),
    (
        "date_confirmations",
        lambda d: {
            str(c.get("sha256")): str(c.get("captured_at") or "") for c in d.date_confirmations
        },
    ),
    ("albums", lambda d: {str(a.get("name")): str(a.get("name") or "") for a in d.albums}),
)


@dataclass(frozen=True, slots=True)
class DriveHolds:
    """What one section on a drive has that a catalog does not. **Two facts, never merged.**

    ⚠ *"The drive holds events this catalog does not"* is FALSE of a rename - the catalog has that
    event, under another name - and printing it anyway is the assert-what-you-did-not-check defect
    this arc is about. So the two are carried apart and worded apart.
    """

    section: str
    #: Values whose identity the catalog has never seen.
    missing: tuple[str, ...] = ()
    #: Identities both hold, where the drive's value differs. `lost` is the drive's.
    changed: tuple[NameSwap, ...] = ()

    def any(self) -> bool:
        """Whether this section has anything at all to report."""
        return bool(self.missing or self.changed)


def document_key_text(key: object) -> str:
    """One spelling of a `_LOSS_KEYS` key, so a lease and a comparison cannot disagree.

    A trip's key is a tuple of days and an event's is a signature string; both have to survive a
    round trip through a SQLite column. **One home for the spelling** rather than a `str()` at the
    writer and another at the reader - the two would drift the first time either was corrected,
    which is the shape `(agc)` keeps naming.
    """
    return "\n".join(str(part) for part in key) if isinstance(key, tuple) else str(key)


def drive_holdings(
    existing: Decisions, fresh: Decisions, *, authored: Mapping[tuple[str, str], str] | None = None
) -> tuple[DriveHolds, ...]:
    """Per section, what ``existing`` holds that ``fresh`` does not - **missing and changed apart**.

    Sections with nothing to say are omitted, so a caller can test the tuple itself.

    ⚠ **`authored` IS A LEASE, NOT A FORCE FLAG, and the difference is the `expected` value.**
    `(aix)` stage 2b. A key appears there only when THIS catalog deliberately changed it, and it
    is skipped **only while the drive still holds what the catalog expected to find** - git's
    `--force-with-lease` rather than `--force`. A drive changed on another machine no longer
    matches, so it is refused exactly as before.
    ⚠ **`None` and an empty mapping behave identically**, which is what keeps every other caller
    and every rebuilt catalog on the pre-`(aix)` path: a rebuild authored nothing, so it leases
    nothing, so `(ahz)` step 3 refuses it in full.
    """
    leases = authored or {}
    holdings: list[DriveHolds] = []
    for section, of in _LOSS_KEYS:
        theirs, ours = of(existing), of(fresh)
        missing = tuple(value for key, value in theirs.items() if key not in ours)
        changed = tuple(
            NameSwap(lost=value, kept=ours[key])
            for key, value in theirs.items()
            if key in ours
            and ours[key] != value
            and leases.get((section, document_key_text(key))) != value
        )
        if missing or changed:
            holdings.append(DriveHolds(section, missing, changed))
    return tuple(holdings)


def refusal_detail(
    existing: Decisions, fresh: Decisions, *, authored: Mapping[tuple[str, str], str] | None = None
) -> str:
    """Why a save to this drive was refused, in one sentence. `(ahz)` step 3

    ⚠ **"this drive holds events this catalog does not" is FALSE of a rename** - the catalog has
    that event, under another name - and since `would_lose` widened, a rename reaches this
    sentence. It is the line the app renders on the drive card and the only thing a user is told
    about a refused write, so the two kinds get their own clause rather than the commoner one
    standing in for both.
    """
    holdings = drive_holdings(existing, fresh, authored=authored)
    clauses: list[str] = []
    gone = [h.section.replace("_", " ") for h in holdings if h.missing]
    if gone:
        clauses.append(f"holds {', '.join(gone)} this catalog does not")
    renamed = [h for h in holdings if h.changed]
    if renamed:
        named = ", ".join(f"{len(h.changed)} {h.section.replace('_', ' ')}" for h in renamed)
        clauses.append(f"names {named} differently")
    return f"this drive {' and '.join(clauses)}; restore first"


def would_lose(
    existing: Decisions, fresh: Decisions, *, authored: Mapping[tuple[str, str], str] | None = None
) -> tuple[str, ...]:
    """Sections where the drive holds decisions ``fresh`` does not. **`O(document)`.**

    **This is the same rule as the unknown-section merge, applied to sections we understand.** A
    re-attached drive carries names a rebuilt catalog has never seen; writing over them destroys
    the only copy, which is precisely what this feature exists to prevent. So the write does not
    happen and the caller is told which sections stopped it.

    Its one false positive is a decision the user DELETED locally: the drive still holds it, so
    the write refuses until a restore reconciles the two. Reported rather than silently resolved,
    because guessing which side is intentional is how the other direction loses data.

    ⚠ **A CHANGED value counts, not only a missing key.** `(ahz)` step 3 This compared identities
    alone until 2026-08-26, so a drive holding `Morning Market` while the catalog held
    `placeholder B` **at the same signature** returned `()` and the save overwrote the real name
    without a word - destroying the last copy rather than merely outranking it, which is worse than
    the sequence `(ahz)` measured. Callers that need to say WHICH kind ask
    :func:`drive_holdings`; this answers only *is there anything*, which is all a refusal needs.
    """
    return tuple(holds.section for holds in drive_holdings(existing, fresh, authored=authored))


def merge_onto_drive(existing: Decisions | None, fresh: Decisions) -> Decisions:
    """``fresh``, carrying forward sections only the drive's copy understands.

    **Read-merge-replace, never write.** :func:`to_document` preserves unknown sections out of a
    `Decisions` that came from a document - but a trigger's object comes from
    :func:`gather_decisions`, and the catalog has never held those sections, so its `unknown` is
    empty. Without this read, a user who downgrades and renames one trip loses the newer version's
    captions to the code written to keep them.
    """
    if existing is None or not existing.unknown:
        return fresh
    return replace(fresh, unknown={**existing.unknown, **fresh.unknown})


class SaveOutcome(StrEnum):
    """What happened to one drive. Four states, because three of them need different words."""

    WRITTEN = "written"
    UNREACHABLE = "unreachable"  # not plugged in, or something else is at the remembered path
    WOULD_LOSE = "would_lose"  # its copy holds decisions this catalog does not
    FAILED = "failed"  # read-only, full, unreadable copy, pulled out mid-write
    #: Its copy was written by a newer Truestill. Separate from `FAILED` deliberately: nothing is
    #: wrong with the drive, the remedy is an upgrade rather than a repair, and one field standing
    #: for two situations that need opposite words is `(abx)`.
    NEWER_VERSION = "newer_version"


#: Outcomes a person may need to act on, defined by EXCLUSION rather than by listing them.
#: A new `SaveOutcome` is far more likely to be a new way of not saving than a new way of
#: saving, so an unlisted member defaults to "tell them" rather than to silence. `NEWER_VERSION`
#: was added after this rule existed and needed no edit anywhere, which is the property bought.
#:
#: Lives here, beside the enum, because both surfaces need it: the CLI prints these and the
#: session layer records them. It was briefly spelled out at both call sites, which is two
#: representations of one fact and the defect `(abv)` was.
PROBLEM_OUTCOMES = frozenset(SaveOutcome) - {SaveOutcome.WRITTEN, SaveOutcome.UNREACHABLE}


@dataclass(frozen=True, slots=True)
class DriveSave:
    """One drive's result, in a form a surface can turn into a sentence."""

    uuid: str
    label: str
    outcome: SaveOutcome
    #: Plain words for a person: what stopped it, or which sections would have been lost.
    detail: str = ""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def save_decisions_to_reachable_drives(
    catalog: Any, *, stamp: str | None = None
) -> tuple[DriveSave, ...]:
    """Put the catalog's decisions on every reachable registered drive. **Never raises.**

    **One catalog pass, then `O(1)` per drive** plus one read and one write each: the decision
    tables are catalog-wide and only the drive block differs, so a second backup drive costs a
    second file write rather than a second full read.

    **One stamp for the whole run.** Restore resolves disagreement by newest `written`, so two
    drives saved by the same run must not be able to disagree about which is newer.

    **A failure here never reaches the user's own operation.** Naming a trip must succeed even
    when the backup of that name does not; the outcome is reported instead.
    """
    drives = catalog.registered_drives()
    if not drives:
        return ()

    shared = replace(_shared_decisions(catalog), written=stamp or _utc_now())
    # ⚠ **Read once for the whole run, like `shared` above.** The lease is a property of the
    # catalog, not of a drive, and re-reading it per drive would make a second backup drive cost a
    # second query for an answer that cannot have changed. `(aix)` stage 2b
    authored = catalog.authored_decisions()
    results: list[DriveSave] = []
    for row in drives:
        uuid = str(row["uuid"])
        label = str(row["label"] or "")
        hint = catalog.get_setting(drive_path_hint(uuid))
        if drive_reach(hint, uuid) is not DriveReach.CONNECTED:
            results.append(DriveSave(uuid, label, SaveOutcome.UNREACHABLE, "not connected"))
            continue

        root = Path(str(hint))
        found = read_decisions(root)
        if found.too_new:
            # The dangerous half of the format rule, and the one that was missing: preserving a
            # newer version's UNKNOWN sections while overwriting its KNOWN ones is exactly
            # backwards, and it is what happened here until the gate existed.
            results.append(DriveSave(uuid, label, SaveOutcome.NEWER_VERSION, found.error or ""))
            continue
        if found.error is not None:
            results.append(DriveSave(uuid, label, SaveOutcome.FAILED, found.error))
            continue

        fresh = _with_drive(shared, row, uuid)
        if found.decisions is not None:
            if would_lose(found.decisions, fresh, authored=authored):
                results.append(
                    DriveSave(
                        uuid,
                        label,
                        SaveOutcome.WOULD_LOSE,
                        refusal_detail(found.decisions, fresh, authored=authored),
                    )
                )
                continue
            fresh = merge_onto_drive(found.decisions, fresh)

        outcome = write_decisions(root, fresh)
        results.append(
            DriveSave(uuid, label, SaveOutcome.WRITTEN)
            if outcome.written
            else DriveSave(uuid, label, SaveOutcome.FAILED, outcome.error or "")
        )
    return tuple(results)


def ensure_decisions_on_drives(
    catalog: Any, *, stamp: str | None = None
) -> tuple[DriveSave, ...] | None:
    """The upgrade write: put the decisions on the drives ONCE for a catalog that predates this.

    Returns `None` when it has already happened, so a caller can stay silent.

    **Existing users are the ones this protects**, and a trigger of "after a decision changes"
    reaches them only when they next rename something. The user most at risk has a finished
    library and has stopped naming things, so for them that trigger never fires at all.

    **Recorded only when a drive actually took it.** A user whose drive was in a drawer at upgrade
    time must get the write when they next plug it in; recording the attempt would mean they never
    do, which is the Lightroom failure - a backup the user believes in and does not have.
    """
    if catalog.get_setting(DECISIONS_SAVED_AT_KEY):
        return None
    when = stamp or _utc_now()
    results = save_decisions_to_reachable_drives(catalog, stamp=when)
    if any(r.outcome is SaveOutcome.WRITTEN for r in results):
        catalog.set_setting(DECISIONS_SAVED_AT_KEY, when)
    return results
