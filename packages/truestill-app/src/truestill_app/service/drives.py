"""Drives / Where / At-risk, reveal, attach, and library custody status."""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, cast

from truestill_core import binaries
from truestill_core.catalog import Catalog
from truestill_core.catalog_session import open_catalog, problem_key
from truestill_core.catalog_startup import inspect_catalog
from truestill_core.decisions import Decisions, gather_decisions, notice_for
from truestill_core.drive import (
    DriveReach,
    create_marker,
    path_is_usable_dir,
    reach_of,
    read_marker,
)
from truestill_core.drive_adoption import AdoptionOffer, inspect_root, recorded_drive
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import sha256_file
from truestill_core.progress import Phase, Progress, ProgressCallback

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


class RevealOk(TypedDict):
    ok: Literal[True]
    path: str


class RevealErr(TypedDict):
    ok: Literal[False]
    error: str
    suggested_root: NotRequired[str | None]
    drive_label: NotRequired[str | None]
    can_register: NotRequired[bool]


def reveal_in_file_manager(path: Path) -> RevealOk | RevealErr:
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
        return cast(RevealErr, {"ok": False, **drive_correction(path)})
    opener = {"darwin": "open", "win32": "explorer"}.get(sys.platform, "xdg-open")
    if shutil.which(opener) is None:
        return {
            "ok": False,
            "error": (
                f"Can't open a file manager because this machine has no '{opener}'. "
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
    """Every file on the drive that is not already a recorded copy at that exact path.

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
    files: list[Path] = []
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

    for dirpath, dirnames, filenames in root.walk(on_error=_note_unreadable):
        dirnames[:] = [name for name in dirnames if not name.startswith(".")]
        for name in filenames:
            if name.startswith("."):
                continue
            item = dirpath / name
            if item.is_file() and item.relative_to(root).as_posix() not in recorded:
                files.append(item)
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
    """
    marker = read_marker(path)
    was_registered = marker is not None
    if marker is None:
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
        marker = create_marker(path, label=path.name or "Library")
    label = marker.label if marker is not None else (path.name or "Library")

    linked = unreadable = unmatched = 0
    with open_catalog(db) as catalog:
        if write and marker is not None:
            catalog.upsert_drive(uuid=marker.uuid, label=marker.label)
            catalog.set_setting(drive_path_hint(marker.uuid), str(path))
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
    photos: int
    videos: int
    audio: int
    size: int
    last_seen: str | None
    last_verified: str | None
    path: str | None
    #: `DriveReach` value: is this drive here right now? Three states, because a boolean would
    #: have to report "we have never recorded where this drive lives" as either connected or
    #: missing, and both are lies - the second alarmingly so.
    reach: str
    #: What this drive is carrying, or `None` when there is nothing to say about it.
    decisions: DriveDecisions | None


class WhereCopy(TypedDict):
    name: str
    drive: str
    relative: str
    last_verified: str | None


class WhereResult(TypedDict):
    copies: list[WhereCopy]
    total: int
    page: int
    pages: int
    page_size: int


class AtRiskRow(TypedDict):
    name: str
    drive: str


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


def list_drives(db: Path) -> list[DriveRow]:
    with open_catalog(db) as catalog:
        mine: Decisions | None = None
        names_by_drive: dict[str, list[str]] = {}
        for row in catalog.copy_names_by_drive():
            names_by_drive.setdefault(row["drive_uuid"], []).append(row["relative"])
        drives: list[DriveRow] = []
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
                    "photos": breakdown["photos"],
                    "videos": breakdown["videos"],
                    "audio": breakdown["audio"],
                    "size": d["total_size"] or 0,
                    "last_seen": d["last_seen"],
                    "last_verified": d["last_verified"],
                    "reach": reach.value,
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
        copies: list[WhereCopy] = [
            {
                "name": r["original_name"] or r["relative"],
                "drive": r["drive_label"],
                "relative": r["relative"],
                "last_verified": r["last_verified"],
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


def at_risk(db: Path) -> list[AtRiskRow]:
    with open_catalog(db) as catalog:
        return [
            {"name": r["original_name"] or r["sha256"][:12], "drive": r["drive_label"]}
            for r in catalog.single_copy_shas()
        ]


class LibraryStatus(TypedDict):
    """Honest, catalog-driven totals for the custody strip."""

    library_path: str | None
    backup_path: str | None
    files: int
    photos: int
    videos: int
    audio: int
    by_format: dict[str, dict[str, int]]
    places: int
    single_copy: int
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


def library_status(db: Path, *, explicit_db: bool = False) -> LibraryStatus:
    """Honest, catalog-driven totals for the custody strip.

    Always names the resolved absolute catalog path. A missing file is first-run (info), not
    an error; an empty file with registered drives is the loud wrong-catalog case.
    """
    # Inspect before Catalog() so a missing path stays will_create (Catalog would create it).
    startup = inspect_catalog(db, explicit_db=explicit_db)
    with open_catalog(db) as catalog:
        breakdown = media_breakdown(catalog.media_names())
        total = catalog.count()
        drives = [d for d in catalog.list_drives() if d["file_count"]]
        single_copy = catalog.single_copy_count()
        # Per-FILE custody, because the strip makes a per-file claim. `places` below counts
        # DRIVES and is kept only for callers that want it; it must never be the number a
        # sentence about files is written against.
        custody = catalog.custody_floor()
        # DISTINCT CONTENT, not the sum over drives. Summing `total_size` per drive made a
        # backed-up library report twice its size - the panel said 5.2 GB where Stats said 4.9
        # about the same 1,997 photos, and the gap was exactly the backup drive.
        total_bytes = catalog.total_content_bytes()
        library_path = take_live_path_hint(catalog, LIBRARY_PATH_HINT)
        backup_path = take_live_path_hint(catalog, BACKUP_PATH_HINT)
    return {
        "library_path": library_path,
        "backup_path": backup_path,
        "files": total,
        "photos": breakdown["photos"],
        "videos": breakdown["videos"],
        "audio": breakdown["audio"],
        "by_format": breakdown["by_format"],
        "places": len(drives),
        "single_copy": single_copy,
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
    }
