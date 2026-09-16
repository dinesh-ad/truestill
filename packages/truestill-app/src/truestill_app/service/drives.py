"""Drives / Where / At-risk, reveal, attach, and library custody status."""

from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

from truestill_core import binaries
from truestill_core.app_paths import is_same_location
from truestill_core.carried import (
    CARRIES_NOTHING_EXTRA,
    FROM_RECORDS,
    FROM_RECORDS_SHORT,
    NOT_RECORDED_HERE,
    NOT_WALKED_FULL,
    NOT_WALKED_YET,
    TWO_LIBRARIES,
)
from truestill_core.catalog import Catalog
from truestill_core.catalog_session import open_catalog, problem_key
from truestill_core.catalog_startup import (
    CatalogPresence,
    CatalogStartupInfo,
    inspect_catalog,
    migrate_catalog,
    refuse_unusable_catalog,
    schema_upgrade_notice,
)
from truestill_core.decisions import Decisions, gather_decisions, notice_for
from truestill_core.drive import (
    LIBRARY_REDUNDANCY,
    DriveGhostError,
    DriveReach,
    create_marker,
    custody_freshness,
    ghost_drive_at,
    ghost_drive_refusal,
    library_independence,
    path_is_usable_dir,
    reach_of,
    read_marker,
    remember_drive_path,
    was_ever_checked,
)
from truestill_core.drive_adoption import AdoptionOffer, inspect_root, recorded_drive
from truestill_core.filesystem import folds_case
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import sha256_file
from truestill_core.progress import Phase, Progress, ProgressCallback
from truestill_core.rescan import compare_key

from truestill_app.service.drive_support import (
    drive_correction,
    drive_path_hint,
    take_live_path_hint,
)
from truestill_app.service.media_support import media_breakdown

#: Remembered paths, for prefilling fields the catalog can already answer. **Hints only.**
#: Drive *identity* is the marker's uuid and never a path (§3.1).
LIBRARY_PATH_HINT = "path_hint.library"
BACKUP_PATH_HINT = "path_hint.backup"

#: **Where the user SAID their library should live.** The counterpart to `LIBRARY_PATH_HINT`, and
#: the difference between them is a design rather than two spellings of one thing (`(abx)`):
#:
#: * `path_hint.library` is **observed** - written after a successful organize from wherever the
#:   run actually wrote, and read through `take_live_path_hint`, which **clears it** when the path
#:   is not currently a usable directory. A hint is never identity.
#: * `library.root` is **declared** - stated once, before any run, and **never auto-cleared**. An
#:   external drive that is unplugged, or a mount that is not up yet, must not make truestill
#:   forget where the user said their library lives. If it did, first run would re-arm every time
#:   the drive was out, which is the defect this key exists to close rather than re-create.
#:
#: So: never pass this through `take_live_path_hint`. Reachability is reported *beside* it, never
#: folded into it, so a screen can say "not reachable right now" instead of "never chosen".
LIBRARY_ROOT_KEY = "library.root"


class RevealOk(TypedDict):
    ok: Literal[True]
    path: str


class RevealErr(TypedDict):
    ok: Literal[False]
    error: str
    suggested_root: NotRequired[str | None]
    drive_label: NotRequired[str | None]
    can_register: NotRequired[bool]


def reveal_in_file_manager(path: Path, db: Path) -> RevealOk | RevealErr:
    """Open a folder in the desktop's own file manager.

    A path printed on screen is a dead end: to actually look at the photos a user has to select
    it, copy it and paste it somewhere else. This is the one action that makes a displayed path
    useful.

    **Degrades honestly.** There is no cross-platform way to do this, so the opener is chosen per
    platform (`xdg-open`, `open`, `explorer`); where none exists the caller is told plainly and
    given the path, rather than being left with a button that silently does nothing.

    Only ever opens a directory that already exists, and the path goes into an argument vector
    rather than a shell, so a folder name containing shell metacharacters is just a name. A
    stale/unreachable hint returns the same drive-correction shape as verify - never a raw
    ``OSError``.
    """
    if not path_is_usable_dir(path):
        return cast(RevealErr, {"ok": False, **drive_correction(path, db)})
    opener = binaries.os_opener()
    if opener is None:
        return {
            "ok": False,
            "error": (
                "Can't open a file manager because this machine has no opener. "
                f"Open the folder yourself: {path}"
            ),
        }
    try:
        binaries.popen([opener, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {
            "ok": False,
            "error": f"Couldn't open a file manager ({exc}). Open the folder yourself in your file manager.",
        }
    return {"ok": True, "path": str(path)}


@dataclass(frozen=True, slots=True)
class DriveAttachment:
    """The result of making a folder usable as a truestill drive."""

    label: str
    registered: bool  # a marker was written now (the folder was not a drive before)
    linked: int  # already-organized files newly attached to this drive
    absent: int  # catalogued files whose copy is not actually on the drive
    #: Read failed, so the file could not be identified at all. Counted separately because a gap
    #: folded into ``linked`` would read as a clean attach (§9). Identified by content, an
    #: unreadable file has no identity: its catalog row stays counted in ``absent``.
    unreadable: int = 0
    #: On the drive, hashes to nothing the catalog knows. Counted rather than ignored so the
    #: walk is not silent about what it read; never attached, because claiming it would invent
    #: a copy of content truestill has no record of.
    unmatched: int = 0
    #: Folders on the drive that could not be listed, drive-relative and POSIX. **Named without a
    #: count**, the asymmetry `SourceScan.unreadable_dirs` already carries (§9): the walk never
    #: went inside, so any number would be invented. Whatever they hold has no copy row, which
    #: `absent` describes as *not on the drive* - true of the record and false of the disk.
    unreadable_dirs: tuple[str, ...] = ()
    #: Set when this folder was NOT registered because it already holds a library the catalog
    #: knows under another identity. Registering anyway would give one library two drive ids,
    #: and every place that counts copies would then report one copy of a photo as two.
    blocked_by: AdoptionOffer | None = None


def _copy_hash(path: Path, cache: HashCache) -> str:
    """This drive's own hash for one copy, taking a cache hit when the file has not changed.

    **It reads the cache and never writes it, and that is a correctness rule rather than a
    preference** (§8). Attach computes SHA-256 and never a perceptual hash, and ``perceptual``
    carries *"not an image"* and *"not computed"* in one value with no ``need_perceptual`` to
    tell them apart -- so a row written here comes back as a **hit** to a later organize
    preview, which then skips near-duplicate detection for that file with no message and
    nothing a user could notice.

    Measured before it was removed, on a drive holding one photograph saved at two qualities:
    ``near_dup=1`` without an attach, ``near_dup=0`` after one.

    ``scan.compute_hashes`` refuses this pairing outright with a ``ValueError``; this function
    called ``cache.put`` directly and walked around that door. The cache is now opened
    ``beside_readonly`` by the caller, so the refusal is enforced by SQLite instead of by
    everyone remembering -- writes raise and the file is never created.
    """
    stat = path.stat()
    # `need_perceptual` stays False: this pass wants SHA-256 and nothing else, so a row
    # without a perceptual hash is a perfectly good answer to the question being asked.
    cached = cache.get(path, stat.st_size, stat.st_mtime_ns, need_sha=True)
    if cached is not None and cached.sha256 is not None:
        return cached.sha256
    return sha256_file(path)


@dataclass(frozen=True, slots=True)
class _DriveWalk:
    """What one pass over the drive found: files to identify, and folders it could not open."""

    files: list[Path]
    unreadable_dirs: tuple[str, ...]


def _unrecorded_files(root: Path, recorded: set[str]) -> _DriveWalk:
    """Every file on the drive that is not already a recorded copy at that path.

    ⚠ **"AT THAT PATH" USED TO MEAN "AT THAT EXACT STRING", WHICH IS THE WRONG QUESTION ON THE
    TWO PLATFORMS MOST USERS ARE ON.** NTFS and APFS fold case, so a catalog holding
    ``Saved/Photo.JPG`` and a walk returning ``Saved/photo.jpg`` describe **one file** - and this
    comparison called it unrecorded, sending it to be hashed. The cheapness this docstring
    promises came apart exactly there: on a drive whose case had drifted, *every* file became a
    candidate. `(ala)`. The structural twin of `rescan.reconcile`, in a different package, with
    no shared code - which is the census's own finding about this comparison.

    ``recorded`` holds ``file_copies.relative`` for this drive - the **per-drive** column, which
    migration keeps current, and the only path in the catalog that can be trusted. A file sitting
    where the catalog already says it sits needs no read: that is what keeps an ordinary attach
    of an already-attached drive cheap now that identification means hashing.

    Dotfiles are skipped: the drive marker, and the catalog sidecars if someone keeps them here.

    ``Path.walk`` rather than ``rglob``, for the reason ``organizer.scan_source`` already gives on
    the source side: **rglob swallows the permission error by design**, so a folder this process
    cannot list simply does not appear, and the copies inside it get no ``file_copies`` row - no
    verify, no 3-2-1 count, no ``where``. Measured before the change: three files present on the
    drive, zero rows, ``unreadable=0`` because they never became candidates, and ``absent=3``
    saying their copies were not on a drive that was holding them. ``walk`` hands the folder to
    ``on_error`` instead. Hidden folders are pruned in place, which is also why an unreadable
    *hidden* folder is not reported: it was never in scope.

    **Complexity: O(entries on the drive)** - one pass, one stat each, no reads, plus the same
    terminal sort ``rglob`` already paid for.
    """
    unreadable: list[str] = []

    def _note_unreadable(error: OSError) -> None:
        """A folder that could not be listed. **Never raises** - one locked folder must not cost
        the rest of the drive, the partial-failure policy every other read here follows."""
        if error.filename is None:
            return
        try:
            unreadable.append(Path(error.filename).relative_to(root).as_posix())
        except ValueError:
            unreadable.append(str(error.filename))

    seen: list[Path] = []
    for dirpath, dirnames, filenames in root.walk(on_error=_note_unreadable):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            item = dirpath / name
            if item.is_file():
                seen.append(item)
    # ⚠ **THE PROBE RUNS ONCE, ON WHAT THE WALK ALREADY FOUND, AND READS NO BYTES.** It stats a
    # returned name with its case swapped and compares inodes, so the mount answers rather than a
    # table of filesystem names - which matters, because a real NTFS mount without `nocase` does
    # NOT fold and a vfat one does. `None` (no walked name carried a cased letter) falls back to
    # exact comparison, which is today's behaviour and correct on Linux.
    key = partial(compare_key, fold_case=folds_case(seen) is True)
    recorded_keys = {key(rel) for rel in recorded}
    files = [item for item in seen if key(item.relative_to(root).as_posix()) not in recorded_keys]
    return _DriveWalk(sorted(files), tuple(sorted(unreadable)))


def _adoption_block(
    path: Path, db: Path, *, cancel: threading.Event | None = None
) -> AdoptionOffer | None:
    """The known drive this unmarked folder already is, or ``None`` to go ahead and register.

    A folder whose paths line up but whose bytes do not (`CONTENT_DIFFERS`) also blocks. That is
    a stricter rule than the CLI's, and deliberately so: the app has no screen on which to
    explain the difference, and refusing to register is always recoverable while a wrong
    identity is not.
    """
    with open_catalog(db) as catalog:
        recorded = [
            recorded_drive(
                str(row["uuid"]), str(row["label"]), catalog.copies_on_drive(str(row["uuid"]))
            )
            for row in catalog.list_drives()
        ]
    offers = inspect_root(path, recorded, cancel=cancel)
    return offers[0] if offers else None


def _refuse_ghost_before_minting(path: Path, db: Path) -> None:
    """Refuse to mint where a known drive was recorded and its marker is gone. `(agr)` part 1.

    **A refusal, never a soft-fail - ruled.** A second soft-fail beside `_adoption_block`'s
    failed one would not be a guard, and the three read-only surfaces already refuse at this
    door. The check is core's one implementation (`ghost_drive_at`), called here exactly as the
    other three mint sites call it - `cli.py` `drives --init`, `cli.py` organize, and
    `service/organize._approve_registration` - so this is a fourth caller of one rule, and any
    future caller of `attach_drive` inherits it.

    Raises :class:`DriveGhostError`, whose own docstring names the delivery route: `jobs.py`
    ships ``str(exc)`` and the class name as the terminal event's message and ``code``, so the
    browser reads the same sentence the CLI prints - the drive's label, its recorded path, and
    why writing here would shadow.

    Opens the catalog read-only and only to ask, the shape `cli._ghost_at` records.
    """
    with open_catalog(db) as catalog:
        drives = [(str(d["uuid"]), str(d["label"])) for d in catalog.list_drives()]
        ghost = ghost_drive_at(path, catalog, drives)
    if ghost is not None:
        raise DriveGhostError(ghost_drive_refusal(ghost))


def attach_drive(
    path: Path,
    db: Path,
    *,
    write: bool,
    progress: ProgressCallback | None = None,
    cancel: threading.Event | None = None,
) -> DriveAttachment:
    """Make ``path`` a registered drive, attaching any library already organized into it.

    **Why this exists.** Organizing through the app used to leave its destination unregistered:
    no marker, so no ``file_copies`` rows, so the app could not verify it, could not copy it
    anywhere, and counted it as living in zero places. The whole custody half of the product
    was reachable only by running the CLI's ``drives --init`` first -- a concept a user has no
    reason to have heard of, standing between "I organized my photos" and "make me a backup".

    Two halves, because a folder can be behind in two different ways:

    * **No marker** -- write one, labelled after the folder. A ~100-byte file at the root of a
      folder the user just asked us to fill with copies of their library.
    * **No recorded copies** -- a library organized before its folder was registered has rows
      in ``files`` but none in ``file_copies``. Each is attached only after confirming the copy
      is *actually present*; anything missing is counted and reported, never assumed.

    **A copy is identified by its content, never by a remembered path.** Attach used to locate
    copies through ``files.relative``, a *per-content* column written once at organize time and
    never updated: ``migrate-layout`` rewrites ``file_copies.relative`` and leaves it behind. On
    the maintainer's real library **0 of 2,300** of those paths still existed. That cost nothing
    while a drive was fully attached -- the already-recorded check answers first -- and cost
    everything on **re-attach**, the disaster-recovery path, where it reported 2,300 files absent
    from a drive physically holding 2,269 of them. Reading another drive's path instead was
    measured at **9%**, because drives sit on different layouts. So the drive is walked and each
    file identified by its hash, which is true regardless of layout or migration history --
    the same promise the marker already makes (`IMPLEMENTATION_STANDARDS.md` §3.1: identity is
    never a path). **A drive with no recorded copies at all therefore reads nothing from the
    catalog about where its files should be**; the original case and the migrated case became
    one route, which is why the migrated one stopped being special.

    Matching accepts **every digest a copy can present**: a Takeout-baked copy hashes to its own
    ``copy_sha256`` rather than to ``files.sha256``, and matching only the source hash would
    leave exactly the baked copies unrecognisable.

    **Attach is also authoritative about this drive's hashes.** It used to record
    ``files.copy_sha256`` -- per-content again -- onto a per-drive row, which would make verify
    compare a baked copy against a pre-bake hash and report corruption on a file truestill itself
    wrote. What is recorded now is the digest that identified the file, which is by construction
    the hash of the bytes on this drive. `docs/PERFORMANCE.md` §1.1 carries the measured cost.

    **Resumable, never rolled back.** Each recorded copy is committed on its own and is
    independently true: that file was on that drive and hashed to that value. ``cancel`` stops
    between files and keeps what finished; the next attach skips what is already recorded and
    carries on. Nothing is written to the *drive* here, so there is no half-done change on disk
    to undo -- a rollback could only discard knowledge, and on a real drive it would discard
    hours of reading to reach a strictly less informative state.

    Two outcomes are counted rather than folded into a total (§9). An **unreadable** file cannot
    be identified at all, so it is named and its catalog row stays in ``absent`` -- attaching it
    would mean picking whichever row looked likely, recording a guess as fact. An **unmatched**
    file is on the drive and hashes to nothing the catalog knows; it is left alone.

    ``write=False`` reports what would happen, hashes nothing and touches nothing, so previews
    stay pure -- and its ``linked`` count is the scale the user is shown *before* agreeing to a
    read of the whole drive.

    :raises DriveWriteError: the folder would not accept its marker - read-only, full, or pulled
        out mid-write (`(aek)`). Deliberately propagated rather than folded into
        ``DriveAttachment``: ``blocked_by`` answers a different question (*this folder already
        holds a known library*), and every caller here is inside a job, so `jobs.py` renders the
        sentence and a `code` the UI can key on - the same route `DriveGhostError` already takes.
        Only reachable with ``write=True``; a preview writes no marker.
    """
    marker = read_marker(path)
    was_registered = marker is not None
    if marker is None:
        # ⚠ THIS GATE IS ABOUT THE **CONTENT** INSPECTION ONLY, and that distinction was lost
        # until `(adx)`. `_adoption_block` costs up to 40 stats and 3 full-file hashes per known
        # drive plus a full `file_copies` read, so paying it on a marked drive would be real work
        # for an offer to adopt itself - the reasoning below stands. What was also skipped here,
        # for free and by accident, was the **path** comparison: whether this drive's identity
        # already answers somewhere else. That question costs one bounded marker read, is only
        # meaningful when a marker EXISTS, and now lives at the hint write instead of behind this
        # gate. See `truestill_core.drive.second_location_note`.
        #
        # Only ever asked where a marker WOULD be minted. An already-marked drive has an
        # identity, so inspecting it could only offer to adopt itself, at the cost of real
        # reads on every backup preview.
        #
        # This refuses; it never adopts. The evidence for "this drive moved" and for "this is a
        # second physical copy of that drive" is identical, and a product whose entire promise
        # is counting how many places a photo is safe in must not resolve that by guessing.
        # The CLI's `drives --init --adopt-existing` is where a person decides.
        blocked = _adoption_block(path, db, cancel=cancel)
        if blocked is not None:
            return DriveAttachment(
                label=path.name or "Library",
                registered=False,
                linked=0,
                absent=0,
                blocked_by=blocked,
            )
    # Previews write nothing, ever - including the marker. An unregistered folder is therefore
    # counted without a uuid rather than skipped, so the preview can still state the scale.
    if marker is None and write:
        # ⚠ **THE GHOST CHECK, before the mint - the fourth mint site gets the guard the other
        # three have.** `(agr)`: this was the one place in the product that could mint an
        # identity at a known drive's recorded path while the drive was unplugged - measured
        # minting a phantom that read *connected* while the real drive read *offline* forever,
        # with every byte written here shadowed the moment the drive remounted. `_adoption_block`
        # above cannot see it and is NOT redundant beside this: the two guards are converses -
        # it recognises a folder that HOLDS a known library's content, and a ghost path holds
        # nothing; this recognises a RECORDED location, which a content scan cannot. Both stay.
        _refuse_ghost_before_minting(path, db)
        marker = create_marker(path, label=path.name or "Library")
    label = marker.label if marker is not None else (path.name or "Library")

    linked = unreadable = unmatched = 0
    with open_catalog(db) as catalog:
        if write and marker is not None:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            remember_drive_path(catalog, marker.uuid, path)
        on_drive = (
            {str(row["relative"]) for row in catalog.copies_on_drive(marker.uuid)}
            if marker is not None
            else set()
        )
        attached = (
            {str(row["sha256"]) for row in catalog.copies_on_drive(marker.uuid)}
            if marker is not None
            else set()
        )
        # Settled before any reading, so the first progress tick can say "1 of 2,269" rather
        # than counting up towards a total the user only learns when it stops.
        walk = _unrecorded_files(path, on_drive)
        candidates = walk.files
        if not write or marker is None:
            # A preview cannot know which of these will match without reading them, and reading
            # is the thing being previewed. It reports the files it would read, which is the
            # scale the user is being asked to agree to.
            # The preview walked, so it already knows which folders it could not open. Saying so
            # here costs nothing and is the honest place: this is the screen where the user is
            # still deciding, and naming a folder writes nothing, so §5 purity holds.
            return DriveAttachment(
                label=label,
                registered=not was_registered,
                linked=len(candidates),
                absent=0,
                unreadable_dirs=walk.unreadable_dirs,
            )

        by_hash = {str(row["hash"]): str(row["sha256"]) for row in catalog.attachable_hashes()}
        total = len(candidates)
        # Read-only, enforced by SQLite rather than by agreement: this pass computes
        # SHA-256 and never a perceptual hash, and a partial row is served as a hit to a
        # later full pass (§8). See `_copy_hash`.
        with HashCache.beside_readonly(db) as cache:
            for item in candidates:
                if cancel is not None and cancel.is_set():
                    break
                try:
                    digest = _copy_hash(item, cache)
                except OSError:
                    # No hash means no identity: there is nothing to attach this file to, and
                    # picking a likely row would record a guess as fact.
                    unreadable += 1
                    continue
                finally:
                    if progress is not None:
                        progress(
                            Progress(
                                linked + unreadable + unmatched + 1,
                                total,
                                Phase.HASHING,
                                item.name,
                            )
                        )
                sha = by_hash.get(digest)
                if sha is None or sha in attached:
                    unmatched += sha is None
                    continue
                catalog.record_copy(
                    sha256=sha,
                    drive_uuid=marker.uuid,
                    relative=item.relative_to(path).as_posix(),
                    # The digest that identified it: by construction the hash of these bytes.
                    copy_sha256=digest,
                    size=item.stat().st_size,
                )
                attached.add(sha)
                linked += 1
        absent = len(set(catalog.organized_sizes()) - attached)
    return DriveAttachment(
        label=label,
        registered=not was_registered,
        linked=linked,
        absent=absent,
        unreadable=unreadable,
        unmatched=unmatched,
        unreadable_dirs=walk.unreadable_dirs,
    )


class DriveDecisions(TypedDict):
    """What this drive is carrying, and what Truestill last failed to write to it.

    **One nested field on `DriveRow` rather than five flat ones**, so a consumer that does not
    care about decisions is unchanged and the browser reads one object.

    **Two kinds of fact live here and they follow different rules.** `problem` is what Truestill
    DID - a save it attempted and could not finish - recorded locally, so it survives the drive
    being unplugged exactly as `last_verified` does. Everything else is what is ON THE DRIVE, and
    the drive is the only authority for it, so those are read when it is here and absent when it
    is not. Caching them would be a second representation of a fact this machine does not own.
    """

    #: The document's own `written` stamp. `None` when the drive is not reachable.
    saved_at: str | None
    #: Sections this catalog holds that the drive's copy does not: its copy is behind.
    stale: list[str]
    #: Sections the drive holds that this catalog does not: the offer to restore.
    awaiting_restore: list[str]
    #: The three-line refusal from core, verbatim, when the document is from a newer Truestill.
    refusal: str | None
    #: Why the last save to this drive did not happen. Recorded by the save since `c5f36ff`;
    #: shown here since the drive card learned to read it.
    problem: str | None


class DriveRow(TypedDict):
    label: str
    uuid: str
    files: int
    #: Copies recorded here that a check LOOKED for and did not find. `files` still counts them:
    #: this list reports history, and a count dropping to zero destroys the only clue to what
    #: happened. `(abg)`.
    not_found: int
    #: When that was observed - the most recent, so the card can date the fact.
    not_found_at: str | None
    #: Copies on this drive a check READ and found wrong. ⚠ **Not the same as `not_found`**: that
    #: is *we looked and it was gone*, this is *we looked and the bytes were not ours*. `files`
    #: still counts them, on `not_found`'s reasoning - the row is the record that content was
    #: written here - but no custody figure does. `(aku)`
    damaged: int
    #: When that was observed - the most recent, so the card can date the fact.
    damaged_at: str | None
    photos: int
    videos: int
    audio: int
    size: int
    last_seen: str | None
    last_verified: str | None
    #: `(aes)`: whether anything has ever LOOKED at this drive's copies. `last_verified` is NULL
    #: both when nobody looked and when a check found gaps - Stats already sends this beside the
    #: date; the Backups card must read the same distinction or it prints "Never checked" after a
    #: verify that found damage.
    was_checked: bool
    path: str | None
    #: `DriveReach` value: is this drive here right now? Three states, because a boolean would
    #: have to report "we have never recorded where this drive lives" as either connected or
    #: missing, and both are lies - the second alarmingly so.
    reach: str
    #: What this drive is carrying, or `None` when there is nothing to say about it.
    decisions: DriveDecisions | None
    #: ⚠ **Is this drive a LIBRARY - somewhere an organize run has written?** From
    #: `catalog.drives_organized_into`, which is exact rather than a heuristic: `backup` and
    #: `recover` never write `organize_runs`, so a backup drive is never marked. It is what lets
    #: the screen fill in where the user's library is instead of asking for a path it knows.
    is_library: bool
    #: How many recorded copies this drive has that the library does not. ⚠ **`None` means the
    #: drive has NO ROWS - nobody walked it - which is the opposite of "it carries nothing"**;
    #: and `None` also when no single library is known, because the question has no subject then.
    #: **From records. Nothing was read from the drive**, which is why `carried_note` travels
    #: beside it and the card must render both or neither.
    carried: int | None
    #: The lead a card renders beside the number, from core. Empty where there is no state to
    #: report - the library's own card, or a screen that cannot name a library at all.
    carried_lead: str
    #: ⚠ **The always-visible qualifier.** 12 characters, and it is what makes the count safe to
    #: print: it names where the figure came from. **Never collapsed into `carried_full`** - the
    #: provenance is not an advanced detail, it is what stops the number being misread.
    carried_short: str
    #: The full explanation, reachable rather than hidden. What the short form actually means.
    carried_full: str


class WhereCopy(TypedDict):
    name: str
    drive: str
    relative: str
    last_verified: str | None
    #: When a check read this copy and found its bytes wrong, or ``None``. `(aku)`
    #:
    #: ⚠ **THE ROW IS LISTED, NOT HIDDEN, AND THAT IS DELIBERATE.** `where` is an inventory of
    #: every copy the catalog has recorded - it does not filter absent ones either, and its help
    #: is *"find which drive(s) hold a file, even when unplugged"*. Its `total` is a SEARCH RESULT
    #: count, never a custody count; the custody counters are `custody_floor`, `single_copy_count`
    #: and their siblings, which `a_place` excludes damaged copies from. Hiding this row would
    #: remove the one screen that can tell a user WHICH of their copies is the bad one.
    damaged_at: str | None
    #: ⚠ **Whether that path can be opened RIGHT NOW.** Find's own lede promises it *"works even
    #: when the drives are unplugged"*, and it then rendered a location on an unplugged drive
    #: identically to one on a connected drive - so the screen that keeps its promise about
    #: searching broke it about the answer. `DriveReach`'s three values, never a boolean: see
    #: `drive.DriveReach` for why UNKNOWN cannot be folded into either of the others.
    reach: str


class WhereResult(TypedDict):
    copies: list[WhereCopy]
    total: int
    page: int
    pages: int
    page_size: int


#: How many at-risk file NAMES travel per drive. ⚠ **A cap on the names, never on the count.**
#:
#: The screen renders three per drive (`app.js`'s `atRiskSampleLine`), so this is twice what is
#: shown: enough headroom that the sentence can grow a name without a contract change, and small
#: enough that the payload is bounded by drives rather than by files. `GRID_SAMPLE_LIMIT` is the
#: same decision one surface over, at a size that surface's job needs.
AT_RISK_SAMPLE_LIMIT = 6


class AtRiskDrive(TypedDict):
    """One drive's share of the at-risk files: how many, and a few of their names. `(akt)`"""

    drive: str
    #: ⚠ **Without this the remedy cannot be right.** `(akp)`: a file at risk on a drive that is
    #: not the library was told to *"copy your library to another drive"*, which backs up a set
    #: the file is not in. The action depends on where the one copy actually is and whether it
    #: can be reached, and neither was sent.
    reach: str
    #: ⚠ **EXACT, ALWAYS.** Never the length of ``shown`` - that is the point of the split.
    total: int
    #: At most :data:`AT_RISK_SAMPLE_LIMIT` names. ``total - len(shown)`` is what the screen
    #: renders as *"and N more"*, so a reader can always tell a sample from the whole set.
    shown: list[str]


class AtRiskSummary(TypedDict):
    """The custody claim, plus enough names to act on it. `(akt)`

    ⚠ **THE COUNT IS EXACT AND THE NAMES ARE CAPPED, AND CONFLATING THEM WAS THE DEFECT.** Until
    `(akt)` this was a flat `list[AtRiskRow]`, one entry per at-risk file, and the browser used
    **`rows.length` as the count** - so the number in *"83 files exist in only one place"* was the
    length of an array that had to carry every file to stay true. Measured: 300,000 one-copy files
    produced an **18.6 MB** response and **1.2 s** of build time, on a screen that opens by
    default, to render twelve names.

    :class:`OrganizedSample` is the same shape one surface over, and its docstring is the rule:
    *"tiles plus the count they were taken from, so truncation is never silent."*
    """

    #: ⚠ **THE PRODUCT'S CENTRAL CLAIM, AND IT IS NEVER A SAMPLE.** The band, the banner title and
    #: the chip all rest on this number. Summed from the per-drive totals, which SQLite computes
    #: exactly in the same scan that picks the names.
    total: int
    drives: list[AtRiskDrive]


def _drive_decisions(
    catalog: Catalog, uuid: str, root: Path | None, mine: Decisions | None
) -> DriveDecisions | None:
    """What to say about one drive's decisions, or `None` when there is nothing.

    ``root`` is `None` for a drive that is not reachable: the document cannot be read, and the
    last date this machine happened to see is not offered in its place.
    """
    problem = catalog.get_setting(problem_key(uuid))
    notice = notice_for(root, mine) if root is not None and mine is not None else None
    if notice is None:
        # A recorded failure outlives the drive being unplugged, so it is still worth saying.
        if not problem:
            return None
        return DriveDecisions(
            saved_at=None, stale=[], awaiting_restore=[], refusal=None, problem=problem
        )
    return DriveDecisions(
        saved_at=notice.saved_at or None,
        stale=list(notice.stale),
        awaiting_restore=list(notice.awaiting_restore),
        refusal=notice.refusal,
        problem=problem,
    )


class DrivesPayload(TypedDict):
    """What `/api/drives` returns: every registered drive, and the ones at risk. `(ahn)` stage 4a.

    Composed at the route from two typed service calls and built as a dict literal until now, so
    the two halves had types and the thing actually sent did not.
    """

    drives: list[DriveRow]
    at_risk: AtRiskSummary
    #: ⚠ **Why no card carries a count, said ONCE.** Empty in the ordinary case. It is a fact
    #: about the catalog - it has organized into more than one folder - not about any one drive,
    #: and the first version repeated all 148 characters of it on every card.
    cannot_name_library: str


def cannot_name_library(db: Path) -> str:
    """Why no drive card carries a count, or ``""`` when they all do. **Core's sentence.**

    ⚠ **Said once, because it is a fact about the CATALOG.** Organizing into two folders makes
    two libraries and `drives_organized_into` refuses to pick between them - which is right, and
    going silently blank was not. The first version returned this per drive and repeated all 148
    characters of it on every card.

    **The remedy it names was checked before the sentence was written**: Settings carries *"Where
    your library lives"*, which writes `library.root` through `set_library_root` and is reachable
    at any time - not gated on a first run, which is the state this sentence appears in.
    """
    with open_catalog(db) as catalog:
        libraries = catalog.drives_organized_into()
        declared = catalog.get_setting(LIBRARY_ROOT_KEY)
        if _the_library(catalog, libraries, declared) is not None:
            return ""
        return TWO_LIBRARIES if len(libraries) > 1 else ""


def _the_library(catalog: Catalog, libraries: set[str], declared: str | None) -> str | None:
    """Which registered drive is THE library, or ``None`` when nothing can say.

    **Three readings, in the order their evidence deserves:**

    1. **The user said so.** `library.root` is written from Settings, so a declared root that
       matches a drive's remembered path settles it even when two folders have been organized
       into. This is what makes the ambiguous case actionable rather than permanent.
    2. **Exactly one organize destination.** The usual case, and exact - `organize_runs` is
       written by both organize surfaces and by neither backup nor recover.
    3. ⚠ **Nothing.** Two destinations and no declaration is a real state, and picking one would
       be right on one machine and wrong on another. The cards say so instead; see
       `carried.TWO_LIBRARIES`.
    """
    if declared:
        # ⚠ **`is_same_location`, NEVER a string compare, and this shipped wrong.** The declared
        # root and the remembered hint are two things a person typed at different times, and on
        # this maintainer's own machine `/home/dinesh/TruestillLibrary` is a symlink to
        # `/data/TruestillLibrary` - both real, both typed, one folder. String equality ignored
        # the user's explicit declaration and left the cards blank.
        for uuid in libraries:
            remembered = catalog.get_setting(drive_path_hint(uuid))
            if remembered and is_same_location(Path(remembered), Path(declared)):
                return uuid
    return next(iter(libraries)) if len(libraries) == 1 else None


class CarriedWords(TypedDict):
    """The three strings a drive card renders about what it is carrying. **All from core.**

    A type rather than a bare dict so `**`-expanding it into `DriveRow` is checked: the keys are
    part of the payload contract, and a typo here would otherwise ship a card with a missing
    sentence and no complaint from mypy.
    """

    carried_lead: str
    carried_short: str
    carried_full: str


def _carried_words(row: object, the_library: str | None, gaps: dict[str, int]) -> CarriedWords:
    """The three strings a card renders, each a core constant. Never composed here.

    ⚠ **`IMPLEMENTATION_STANDARDS.md` §9**: the CLI's `carried` prints the long form of exactly
    these facts, and a card that worded them itself would let the two surfaces disagree about what
    a count means. The split into lead / short / full is a layout decision; the sentences are not.
    """
    uuid = str(row["uuid"])  # type: ignore[index]
    if the_library is not None and uuid == the_library:
        return CarriedWords(carried_lead="", carried_short="", carried_full="")
    if the_library is None:
        # ⚠ Speak, rather than going blank - but ONCE, at the top of the list. `DrivesPayload`
        # carries the sentence, because "this catalog cannot tell which folder is your library"
        # is a fact about the catalog and repeating it per card was 148 characters three times.
        return CarriedWords(carried_lead="", carried_short="", carried_full="")
    if not int(row["file_count"] or 0):  # type: ignore[index]
        # No rows at all: nobody walked it. NOT "it carries nothing".
        return CarriedWords(
            carried_lead=NOT_WALKED_YET, carried_short="", carried_full=NOT_WALKED_FULL
        )
    if gaps.get(uuid, 0) == 0:
        return CarriedWords(
            carried_lead=CARRIES_NOTHING_EXTRA,
            carried_short=FROM_RECORDS_SHORT,
            carried_full=FROM_RECORDS,
        )
    return CarriedWords(
        carried_lead=NOT_RECORDED_HERE,
        carried_short=FROM_RECORDS_SHORT,
        carried_full=FROM_RECORDS,
    )


def list_drives(db: Path) -> list[DriveRow]:
    with open_catalog(db) as catalog:
        mine: Decisions | None = None
        names_by_drive: dict[str, list[str]] = {}
        for row in catalog.copy_names_by_drive():
            names_by_drive.setdefault(row["drive_uuid"], []).append(row["relative"])
        drives: list[DriveRow] = []
        # ⚠ **ONE QUERY FOR THE WHOLE SCREEN, not one per card.** Measured on 376,000 rows - a
        # 40,000-file library and eight drives of 42,000 - at **292 ms for all eight against
        # 36 ms for one**, so the per-card alternative costs more and scales worse. No new index:
        # `idx_file_copies_drive` scans and `file_copies`' own primary key covers the lookup.
        libraries = catalog.drives_organized_into()
        # ⚠ **THE USER'S OWN ANSWER WINS, and checking for one is what makes the ambiguous case
        # actionable.** Settings carries *"Where your library lives"*, which writes `library.root`
        # and is reachable at any time. So two organize destinations is only ambiguous while the
        # user has not said which - and when they have, the cards work again.
        declared = catalog.get_setting(LIBRARY_ROOT_KEY)
        the_library = _the_library(catalog, libraries, declared)
        gaps = catalog.gap_by_drive(the_library) if the_library is not None else {}
        for d in catalog.list_drives():
            breakdown = media_breakdown(names_by_drive.get(d["uuid"], []))
            # The hint is READ, not taken. `take_live_path_hint` clears a dead path, which was
            # right when the hint was only a convenience for "Check now" - but it is now the one
            # thing that lets a drive be reported OFFLINE rather than UNKNOWN. Clearing it would
            # erase that after a single listing: unplug a drive, look twice, and truestill would
            # forget it ever knew where the drive was. Cost of keeping it is one marker read per
            # drive per listing, which is what `drive_reach` already does.
            hint = catalog.get_setting(drive_path_hint(d["uuid"]))
            reach = reach_of(catalog, str(d["uuid"]))
            # Offered as an actionable path only when the drive is actually there; a remembered
            # path for an absent drive must not become a "Check now" button that cannot work.
            path = hint if reach is DriveReach.CONNECTED else None
            # Gathered ONCE, lazily: a listing of offline drives never pays for it, and a
            # listing of ten connected ones pays for it once rather than ten times.
            if path is not None and mine is None:
                mine = gather_decisions(catalog, "")
            drives.append(
                {
                    "label": d["label"],
                    "uuid": d["uuid"],
                    "files": d["file_count"],
                    # RECORDED HERE, AND NOT FOUND WHEN WE LOOKED. A history gains a number
                    # rather than losing one: `files` still counts every copy ever written here,
                    # because a count that quietly drops to zero destroys the only clue to what
                    # happened. The custody SENTENCE excludes these - see `Catalog.list_drives`
                    # for the two rules and why they are opposites. `(abg)`.
                    "not_found": d["missing_count"],
                    "not_found_at": d["missing_at"],
                    "damaged": d["damaged_count"],
                    "damaged_at": d["damaged_at"],
                    "photos": breakdown["photos"],
                    "videos": breakdown["videos"],
                    "audio": breakdown["audio"],
                    "size": d["total_size"] or 0,
                    "last_seen": d["last_seen"],
                    "last_verified": d["last_verified"],
                    "was_checked": was_ever_checked(d),
                    "reach": reach.value,
                    "is_library": str(d["uuid"]) in libraries,
                    # ⚠ **`None` vs `0` is the whole point.** A drive with no `file_copies` rows
                    # is absent from `gaps`, so it stays `None` and the card says "not checked
                    # yet" - never "nothing to bring back" about a drive holding a whole library.
                    "carried": (
                        None
                        if the_library is None or str(d["uuid"]) == the_library
                        else gaps.get(str(d["uuid"]))
                        if int(d["file_count"] or 0)
                        else None
                    ),
                    **_carried_words(d, the_library, gaps),
                    # Where it was last seen, so a card can offer "Check now" for the right
                    # folder. Absent when we have never had a path for it, or the hint was
                    # stale and cleared -- in which case the card states the fact without
                    # offering an action it cannot honour.
                    "path": path,
                    "decisions": _drive_decisions(
                        catalog, str(d["uuid"]), Path(path) if path else None, mine
                    ),
                }
            )
        return drives


def _reach_per_drive(catalog: Catalog) -> Callable[[str], str]:
    """`reach_of` memoised for one request. ⚠ **ONE filesystem check PER DRIVE, NEVER PER ROW.**

    `drive.library_independence` states the same rule for its own stat, and for the same reason:
    a page of results holds up to `Catalog.FIND_PAGE_SIZE` rows and a library holds a handful of
    drives. Asking per row would put a `stat` on a possibly-absent USB mount in a loop, which is
    slow when the drive is there and slower when it is not.
    """
    seen: dict[str, str] = {}

    def reach(uuid: str) -> str:
        if uuid not in seen:
            seen[uuid] = reach_of(catalog, uuid).value
        return seen[uuid]

    return reach


def where(term: str, db: Path, *, page: int = 1) -> WhereResult:
    """One page of search results, plus what the caller needs to render a pager.

    Paged in SQL (`Catalog.find_copies`), so a page costs a page of rows however large the
    library is. The total comes from a separate `COUNT(*)`, which is what makes "page 3 of 12"
    honest rather than "more results, somewhere".
    """
    size = Catalog.FIND_PAGE_SIZE
    page = max(1, page)
    with open_catalog(db) as catalog:
        total = catalog.count_copies(term)
        rows = catalog.find_copies(term, limit=size, offset=(page - 1) * size)
        reach = _reach_per_drive(catalog)
        copies: list[WhereCopy] = [
            {
                "name": r["original_name"] or r["relative"],
                "drive": r["drive_label"],
                "relative": r["relative"],
                "last_verified": r["last_verified"],
                "damaged_at": r["damaged_at"],
                "reach": reach(str(r["drive_uuid"])),
            }
            for r in rows
        ]
    return {
        "copies": copies,
        "total": total,
        "page": page,
        "pages": max(1, -(-total // size)),
        "page_size": size,
    }


def at_risk(db: Path) -> AtRiskSummary:
    """Files whose only copy is on one drive, grouped by that drive. `(akt)`

    ⚠ **The payload is bounded by the number of DRIVES, not by the size of the library.** It was
    one entry per at-risk file until `(akt)` - 18.6 MB at 300,000 - and the screen has never shown
    more than three names per drive.
    """
    with open_catalog(db) as catalog:
        reach = _reach_per_drive(catalog)
        groups = catalog.single_copy_by_drive(sample_limit=AT_RISK_SAMPLE_LIMIT)
        return {
            # ⚠ Summed from the EXACT per-drive totals, never from the sampled names. A `total`
            # derived from `shown` would be this defect rebuilt: the browser used `rows.length`
            # as the count, which is why the whole library had to travel to keep it true.
            "total": sum(group.total for group in groups),
            "drives": [
                {
                    "drive": group.drive_label,
                    "reach": reach(group.drive_uuid),
                    "total": group.total,
                    "shown": list(group.names),
                }
                for group in groups
            ],
        }


class LibraryStatus(TypedDict):
    """Honest, catalog-driven totals for the custody strip."""

    library_path: str | None
    #: Where the user **said** the library lives, or `None` when they have never been asked.
    #: Distinct from `library_path` above, which is where a run was **observed** to write and is
    #: `None` whenever that path is unreachable. See `LIBRARY_ROOT_KEY`. `(abx)`.
    library_root: str | None
    #: Whether the first-run question is still unanswered: **no declaration AND no files.**
    #: Computed here rather than in the browser so the rule has one home and one set of tests.
    #: The second half is what keeps it off an existing library - a user who organized before this
    #: shipped has no declaration and must never be re-asked, because they answered the question
    #: by doing it.
    needs_library_root: bool
    backup_path: str | None
    files: int
    photos: int
    videos: int
    audio: int
    by_format: dict[str, dict[str, int]]
    places: int
    #: ⚠ **`custody_checked_at` WAS HERE AND WAS REMOVED 2026-08-19.** It carried the oldest
    #: check across the drives holding copies, and went null the moment any of them had never
    #: been checked, because **no single date is true of the whole claim**. The rule survives the
    #: field - it is stated by `never_checked_drives` being non-empty and by both surfaces
    #: leading with that rather than with a date. Once Stage 3 gave the surfaces
    #: `custody_dated_at` to read, nothing read this at all, and it was derivable from what
    #: remains. A payload field computed and read by nobody is how the next divergence gets in.
    #:
    #: Labels of drives that hold copies and have never been verified. Named rather than counted:
    #: the name is the only clue a reader has to what happened.
    never_checked_drives: list[str]
    #: The oldest check across the drives that HAVE one. **A never-checked drive does not blank
    #: it**, which is the point: without this, a library with a single unchecked place can say
    #: nothing about its other drives. `(abg)` Stage 3.
    custody_dated_at: str | None
    #: Whole days from `custody_dated_at` to now, or None when nothing is dated.
    custody_dated_days: int | None
    #: `fresh` / `softening` / `stale`, from the OLDEST dated drive. Computed in core and shipped
    #: rather than recomputed here: two implementations of one threshold is exactly the drift
    #: `CustodyFreshness` was put in core to avoid. Never an alarm - see `CustodyTier`.
    custody_tier: str
    single_copy: int
    #: Whether the drives holding copies can fail separately. `(aiy)`. One of
    #: `CopyIndependence`'s three values; **never a boolean** - `drive.py`'s own ruling is that
    #: both folds lie, and a screen has the same duty as a terminal.
    independence: str
    #: The sentence for that verdict, from core's `drive.LIBRARY_REDUNDANCY`. ⚠ **Handed over,
    #: never composed here** - the shape `(ajf)`'s `eject_note` established, so four screens and
    #: two commands cannot word one fact six ways.
    #:
    #: ⚠ **THE FILE COUNT IS DELIBERATELY NOT SHIPPED.** `library_independence` returns one and
    #: `truestill status` prints it, but no screen reads it - the strip already carries its own
    #: counts from `custody_floor`, and a second one here would be two numbers about one fact.
    #: `test_no_thirty_fifth_dead_payload_key` caught it as a computed key nobody reads, which is
    #: `(ahl)`'s defect, so it was removed rather than justified.
    independence_note: str
    #: Files with no recorded copy at all - invisible to `single_copy`, which reads
    #: `file_copies`, and the most exposed thing in the library.
    files_no_copy: int
    #: Files with exactly one recorded copy.
    files_one_copy: int
    #: The minimum copy count across every file. One unprotected file holds it down, which is
    #: what makes it safe to write a sentence against.
    redundancy_floor: int
    #: Files with at least one recorded copy, and the weakest of those. The strip reports on
    #: these; files with no copy at all are a Stats finding, so they must neither drag this to
    #: zero nor be papered over by a universal that quietly excludes them.
    files_on_a_drive: int
    held_floor: int
    bytes: int
    catalog_path: str
    catalog_presence: str
    catalog_detail: str
    catalog_tone: Literal["info", "notice", "alert"]
    #: What opening this catalog UPGRADED, in core's words, or `""` when nothing was migrated.
    #: `(akz)`
    #:
    #: ⚠ **`str`, REQUIRED, and empty for "nothing happened" - rather than `NotRequired`.**
    #: `(aky)` measured that a `NotRequired` field is invisible to mypy when its line is deleted
    #: from the builder, and that four such fields are drawn on a screen with nothing asserting
    #: them. A required field with an empty value costs one JSON key and keeps the type checker.
    #:
    #: ⚠ **It is the BOOT value, not a live reading, and it must be.** `inspect_catalog` is what
    #: migrates; by the second request the schema is current and a fresh reading would say
    #: nothing. Same one-way "this is what happened at boot" fact as `boot_catalog` beside it,
    #: and bounded the same way - it describes this process and dies with it.
    catalog_upgrade: str


def prepare_catalog(db: Path, *, explicit_db: bool = False) -> CatalogStartupInfo:
    """Read first-run presence, then create and migrate the catalog. Returns what was seen BEFORE.

    **The order is the contract, which is why this is one function and not two calls at a call
    site.** `migrate_catalog` creates the file, so an `inspect_catalog` after it can never report
    `WILL_CREATE` - a genuine first run would instead be told its catalog is EMPTY, whose message
    hints the user may have opened the wrong one. That is a false accusation on a first launch,
    and it is the kind of defect that arrives by someone reordering two adjacent lines.

    Pinned by `test_first_run_survives_the_startup_migration.py`, which fails if the two are
    swapped.
    """
    presence = inspect_catalog(db, explicit_db=explicit_db)
    # THE HAZARD SITE for `(adr)`: `migrate_catalog` builds the schema into whatever file it is
    # given, so on this path a failed copy becomes a valid empty catalog before any person sees
    # it. The launcher refuses first; this is here because it is the call that does the damage,
    # and an entry point that reaches `create_app` another way must still be stopped.
    refuse_unusable_catalog(presence)
    migrate_catalog(db)
    return presence


def library_status(
    db: Path, *, explicit_db: bool = False, boot_catalog: CatalogStartupInfo | None = None
) -> LibraryStatus:
    """Honest, catalog-driven totals for the custody strip.

    Always names the resolved absolute catalog path. A missing file is first-run (info), not
    an error; an empty file with registered drives is the loud wrong-catalog case.
    """
    # Inspect before Catalog() so a missing path stays will_create (Catalog would create it).
    startup = inspect_catalog(db, explicit_db=explicit_db)
    # ...and prefer what the process saw at boot when the live reading is EMPTY, because
    # `create_app` migrates the catalog before serving, so the file exists by the time any
    # request runs. Without this, a genuine first run reports EMPTY - whose message hints the
    # user may have opened the WRONG catalog, which is a false accusation on a first launch.
    #
    # ⚠ BOUNDED to the EMPTY case on purpose. Any real content makes this reading READY or
    # EMPTY_WITH_DRIVES and `boot_catalog` is ignored, so a value captured at boot cannot outlive
    # the truth. A user who deletes the catalog mid-session gets WILL_CREATE from the live
    # reading anyway - the same answer, by a different route.
    if (
        boot_catalog is not None
        and startup.presence is CatalogPresence.EMPTY
        and boot_catalog.presence is CatalogPresence.WILL_CREATE
    ):
        startup = boot_catalog
    with open_catalog(db) as catalog:
        breakdown = media_breakdown(catalog.media_names())
        total = catalog.count()
        registered = catalog.list_drives()
        drives = [d for d in registered if d["file_count"]]
        # Freshness for the claim, from the rows just fetched - no extra query, and nothing on
        # disk is touched. `last_verified` has existed on `drives` all along and is already shown
        # per drive; it simply never reached the number a person reads. `(abg)`.
        #
        # `registered` goes in as well as `drives` so a name is judged ambiguous against every
        # drive the USER owns, not merely the ones this sentence counts - `(acr)`. Same rows,
        # no second query. A collision is only qualified where one exists, so a library with
        # distinctly named drives gets byte-identical output and reads no path hint at all.
        freshness = custody_freshness(catalog, drives, registered)
        single_copy = catalog.single_copy_count()
        # Per-FILE custody, because the strip makes a per-file claim. `places` below counts
        # DRIVES and is kept only for callers that want it; it must never be the number a
        # sentence about files is written against.
        custody = catalog.custody_floor()
        # `(aiy)`. One `stat` per HOLDING drive - `holder_sets` groups by the drive combination,
        # never by file. The catalog stores no device, so this cannot be answered from it.
        independence, _ = library_independence(catalog)
        # DISTINCT CONTENT, not the sum over drives. Summing `total_size` per drive made a
        # backed-up library report twice its size - the panel said 5.2 GB where Stats said 4.9
        # about the same 1,997 photos, and the gap was exactly the backup drive.
        total_bytes = catalog.total_content_bytes()
        library_path = take_live_path_hint(catalog, LIBRARY_PATH_HINT)
        backup_path = take_live_path_hint(catalog, BACKUP_PATH_HINT)
        # Read plainly, NOT through `take_live_path_hint` - see `LIBRARY_ROOT_KEY`. Routing this
        # through the hint reader would delete the user's stated intent the first time their
        # library drive was unplugged.
        library_root = catalog.get_setting(LIBRARY_ROOT_KEY)
    return {
        "library_path": library_path,
        "library_root": library_root,
        "needs_library_root": library_root is None and total == 0,
        "backup_path": backup_path,
        "files": total,
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "by_format": breakdown["by_format"],
        "places": len(drives),
        "never_checked_drives": list(freshness.never_checked),
        "custody_dated_at": freshness.dated_at,
        "custody_dated_days": freshness.dated_days,
        "custody_tier": freshness.tier.value,
        "single_copy": single_copy,
        "independence": str(independence),
        "independence_note": LIBRARY_REDUNDANCY[independence],
        "files_no_copy": int(custody["no_copy"]),
        "files_one_copy": int(custody["one_copy"]),
        "redundancy_floor": int(custody["floor"]),
        "files_on_a_drive": int(custody["held"]),
        "held_floor": int(custody["held_floor"]),
        "bytes": total_bytes,
        "catalog_path": startup.absolute_path,
        "catalog_presence": startup.presence.value,
        "catalog_detail": startup.detail,
        "catalog_tone": startup.tone,
        # From the BOOT reading, never `startup` - see the field's own note. `(akz)`
        "catalog_upgrade": (
            schema_upgrade_notice(boot_catalog.opening) if boot_catalog is not None else ""
        ),
    }


class SetLibraryRootOk(TypedDict):
    library_root: str


class SetLibraryRootErr(TypedDict):
    error: str


def set_library_root(raw: str, db: Path) -> SetLibraryRootOk | SetLibraryRootErr:
    """Record where the user says their library should live. `(abx)`.

    **Stored expanded and absolute.** A stored `~` is a path two pieces of code will disagree
    about - the browser cannot expand it, and comparing it against a run's destination would fail
    on a string difference that is not a real one.

    **The folder need not exist yet**, and that is the ordinary case: on a first run it is exactly
    what the user is about to create. Creating it is the picker's job (`fs_browse.fs_create`,
    already used for a new backup destination), and `organize` already answers a not-yet-existing
    destination from the parent it would be created in. Refusing a path here because it is not
    there yet would refuse the first run.

    A blank is refused rather than stored: storing one would answer the question with nothing and
    then never ask again.
    """
    text = raw.strip()
    if not text:
        return {"error": "Choose a folder for your library."}
    resolved = Path(text).expanduser()
    with open_catalog(db) as catalog:
        catalog.set_setting(LIBRARY_ROOT_KEY, str(resolved))
    return {"library_root": str(resolved)}
