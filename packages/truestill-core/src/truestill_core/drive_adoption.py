"""Is this unmarked folder a library the catalog already knows?

**The failure this prevents.** A drive whose marker was lost - copied without it, restored from a
backup that skipped dotfiles - looks to truestill like an unregistered folder. Registering it
mints a *new* uuid, and the catalog then holds two drives for one library. `moving-machines.md`
names this the worst failure mode of a move, and the two surfaces fail in opposite directions:
the CLI shows the new drive with **0 files** (visibly wrong), while the app attaches by content
and shows it with all of them - so `truestill status` reports *"All catalogued content has at
least two drive copies. Nicely redundant."* about photos that exist in exactly one place. A
custody tool reassuring someone about redundancy they do not have is the worse of the two.

**Why identity cannot simply be inferred.** The evidence for *"this is that drive, moved"* and
the evidence for *"this is a second physical copy of that drive"* is **the same evidence** - a
clone is byte-identical by construction, and this product's whole point is that a second copy is
a different, better thing than one copy. Only the person holding the hardware knows which they
have. So nothing here adopts: it reports what it found and names the drive, and a caller asks.

**Paths are never compared as strings.** Presence is `(root / relative).is_file()`, so the
filesystem answers, and Windows/macOS case-insensitivity is theirs to apply rather than ours to
emulate. On a case-sensitive filesystem a case-differing tree simply reads as no match, which is
the safe direction: the cost is a missed offer, never a wrong one.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from truestill_core.hashing import sha256_file
from truestill_core.path_reach import Reach, reach

#: How many recorded paths are stat-checked per known drive.
#:
#: 40 is chosen against the slowest realistic filesystem rather than the fastest: a local stat is
#: ~2.3 us (`docs/PERFORMANCE.md` §3.2), so 40 is ~0.1 ms and irrelevant, while a network or
#: FUSE mount can take milliseconds per stat, making this ~0.4 s worst case - noticeable but bounded,
#: and the pass is cancellable. Raising it buys almost nothing: at the 50% threshold below, 40
#: samples already put a coincidental pass far out of reach.
STAT_SAMPLE = 40

#: What fraction of the sampled paths must exist before the content is worth hashing.
#:
#: Not higher, because a **partially restored or half-synced** drive is a genuine match and can
#: easily be missing half its files - demanding 90% would miss exactly the recovery case this
#: exists for. Not lower, because the sample must not pass on noise. A `file_copies.relative`
#: carries the folder path *and* the filename (`Camera/2021/2021-05/IMG_1234.jpg`), so clearing
#: this bar means ~20 of those resolving under one root; two unrelated libraries do not do that.
PRESENCE_THRESHOLD = 0.5

#: How many present files are hashed to turn a likely match into a proven one.
#:
#: Not 1: a single match can be coincidental - a stock image, an empty file, a duplicated icon.
#: Three independent full-file SHA-256 agreements at three recorded paths cannot be. Not more,
#: because each is a full read of a real photo and this runs before the user has agreed to
#: anything; three ~5 MB reads is ~30 ms locally and stays tolerable on a slow mount.
HASH_PROOF = 3


class AdoptionVerdict(StrEnum):
    """What the sample concluded about one known drive."""

    NO_MATCH = "no_match"  # too few recorded paths are present here
    PROVEN = "proven"  # present, and the bytes match what was recorded
    CONTENT_DIFFERS = "content_differs"  # the paths line up, the bytes do not


@dataclass(frozen=True, slots=True)
class RecordedDrive:
    """One known drive as the catalog holds it: identity, name, and where its copies sit."""

    uuid: str
    label: str
    #: ``relative`` -> the digest that copy should present. A Takeout-baked copy hashes to its
    #: own ``copy_sha256`` rather than to ``files.sha256``, so the caller resolves which applies.
    digests: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class AdoptionOffer:
    """What was found for one drive, with the counts behind it rather than a bare verdict."""

    uuid: str
    label: str
    verdict: AdoptionVerdict
    sampled: int
    present: int
    hashed: int
    proven: int


def recorded_drive(uuid: str, label: str, copies: Iterable[sqlite3.Row]) -> RecordedDrive:
    """Build a :class:`RecordedDrive` from ``file_copies`` rows, resolving which digest applies.

    Lives here rather than at each call site because the resolution is a *rule*, not plumbing: a
    Takeout-baked copy hashes to its own ``copy_sha256`` and not to ``files.sha256``, so a caller
    that matched only the source hash would find exactly the baked copies "different" and refuse
    to recognise a drive it has itself written. Two call sites spelling that out separately is
    how one of them ends up fixed and the other not.
    """
    return RecordedDrive(
        uuid=uuid,
        label=label,
        digests={str(c["relative"]): str(c["copy_sha256"] or c["sha256"]) for c in copies},
    )


def _stride_sample(items: Sequence[str], limit: int) -> list[str]:
    """Up to ``limit`` items spread evenly across ``items``. Deterministic, no RNG.

    Spread rather than "the first N" because a partially synced drive is typically missing a
    contiguous region: sampling one end would read a half-restored drive as either a certain
    match or no match at all, depending only on which end was taken.
    """
    if len(items) <= limit:
        return list(items)
    stride = len(items) / limit
    return [items[int(i * stride)] for i in range(limit)]


def inspect_root(
    root: Path,
    drives: Sequence[RecordedDrive],
    *,
    hasher: Callable[[Path], str] = sha256_file,
    cancel: threading.Event | None = None,
) -> list[AdoptionOffer]:
    """Which known drives, if any, this unmarked folder appears to be.

    Two stages on purpose. The stat sample is nearly free and rejects almost everything; only a
    root that already looks like a match pays for hashing. **Complexity:** at most
    ``STAT_SAMPLE`` stats plus ``HASH_PROOF`` full reads *per known drive*, independent of how
    large the library or the folder is - it never walks the tree.

    Returns every drive that is not :attr:`AdoptionVerdict.NO_MATCH`, strongest first. More than
    one is a real answer, not an error: a user with two backups of the same library has two, and
    a caller that picked the first would be guessing between them.
    """
    offers: list[AdoptionOffer] = []
    for drive in drives:
        if cancel is not None and cancel.is_set():
            break
        offer = _inspect_one(root, drive, hasher=hasher, cancel=cancel)
        if offer.verdict is not AdoptionVerdict.NO_MATCH:
            offers.append(offer)
    offers.sort(key=lambda o: (o.verdict is not AdoptionVerdict.PROVEN, -o.present, o.label))
    return offers


def _inspect_one(
    root: Path,
    drive: RecordedDrive,
    *,
    hasher: Callable[[Path], str],
    cancel: threading.Event | None,
) -> AdoptionOffer:
    relatives = sorted(drive.digests)
    sample = _stride_sample(relatives, STAT_SAMPLE)
    if not sample:
        return AdoptionOffer(drive.uuid, drive.label, AdoptionVerdict.NO_MATCH, 0, 0, 0, 0)

    present: list[str] = []
    for relative in sample:
        if cancel is not None and cancel.is_set():
            break
        # ⚠ `reach`, not `is_file()`. On 3.14 a refused path answered False, so it was counted
        # as evidence of ABSENCE - the opposite of the line below - and enough of them flip this
        # verdict to NO_MATCH for a drive that is simply not answering. `(aey)`
        found = reach(root / relative)
        if found is Reach.REFUSED:
            continue  # unreadable or dead mount: not evidence either way
        if found is Reach.FILE:
            present.append(relative)

    if len(present) < PRESENCE_THRESHOLD * len(sample):
        return AdoptionOffer(
            drive.uuid, drive.label, AdoptionVerdict.NO_MATCH, len(sample), len(present), 0, 0
        )

    # Only now is a read worth paying for. Every one sampled must agree: this verdict is what a
    # caller may act on by attaching catalog rows to this tree, and `reclaim` deletes files on
    # the strength of catalog rows. A majority would mean adopting on the strength of some
    # files matching, which is precisely the guess that must not be recorded as fact.
    to_hash = _stride_sample(present, HASH_PROOF)
    proven = 0
    for relative in to_hash:
        if cancel is not None and cancel.is_set():
            break
        try:
            if hasher(root / relative) == drive.digests[relative]:
                proven += 1
        except OSError:
            continue
    verdict = (
        AdoptionVerdict.PROVEN
        if proven and proven == len(to_hash)
        else AdoptionVerdict.CONTENT_DIFFERS
    )
    return AdoptionOffer(
        drive.uuid, drive.label, verdict, len(sample), len(present), len(to_hash), proven
    )
