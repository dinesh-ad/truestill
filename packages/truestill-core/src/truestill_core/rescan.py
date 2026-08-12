"""Reconcile a drive's recorded copy locations against what is actually on it.

Report only. Nothing here writes to a catalog or to a drive, and no caller of it may.

**Four outcomes, disjoint and exhaustive over both inputs.**

* **PLACED** -- the catalog's path has a file at it. **Never read.** That rule is the whole
  design: location is a question about paths, and re-hashing every copy to answer it would cost
  the entire library (~15 h for 196 GiB at the 3.9 MB/s measured on a cloud mount) to learn what
  a stat already said (~14 s for 33,000 files). Integrity is a different question, it belongs to
  `verify`, and `verify` reads every byte on purpose.
* **MOVED** -- the recorded path is empty and that content is on the drive somewhere else.
  Identified by **content hash, never by name or size.** That evidence is precisely what makes
  correcting a recorded location safe rather than a guess; a weaker match would turn a
  corrective operation into a destructive one. It also makes a case-only rename ordinary here,
  where in Lightroom the same input reports one image as missing *and* new.
* **STRAY** -- a file on the drive that no record accounts for. Includes a *second* copy of
  content that is already placed: the catalog can hold one path per content per drive
  (``file_copies`` is keyed ``(sha256, drive_uuid)``), so the extra one is genuinely unaccounted
  for and saying otherwise would invent a record.
* **UNACCOUNTED** -- a record whose path is empty and whose content is nowhere on this drive.

**UNACCOUNTED is a question, not an answer.** Deleted, moved to another drive, inside a folder
that could not be listed, or on a file that could not be read -- those are indistinguishable
from here, and guessing is the failure that makes Lightroom's Synchronize Folder unusable. When
anything was unreadable, :attr:`RescanReport.complete` is ``False`` and the bucket is a floor
rather than a count.

**Complexity: O(records + files on the drive)** -- one pass over each and dictionary lookups
throughout; no nested iteration over the library. The expensive part is the caller's: hashing
the candidates, which is bounded by what actually *changed* rather than by library size.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class MovedCopy:
    """Content whose recorded path is empty and which is on the drive somewhere else.

    ``found`` is a tuple because content can sit at more than one path. A single value would
    have to pick one, and picking is the thing this module refuses to do -- a later repair must
    treat more than one as ambiguous and decline it rather than choose.
    """

    sha256: str
    recorded: str
    found: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RescanReport:
    """What one reconciliation found. Every field is a fact; none is an instruction."""

    placed: tuple[str, ...]
    moved: tuple[MovedCopy, ...]
    stray: tuple[str, ...]
    unaccounted: tuple[str, ...]
    #: Staged copies truestill wrote and then failed to remove (`safe_copy.STAGING_SUFFIX`).
    #: **Its own field rather than part of `stray`, because the two need opposite words**
    #: (`(acz)`, and `(ach)`'s lesson applied where it would otherwise be repeated): a stray may
    #: be a photograph the user wants adopted, while this is truestill's own failed write and the
    #: only sane action is removing it. One count meaning both would be unactionable.
    debris: tuple[str, ...] = ()
    #: Folders the walk could not list. **Named without a count** -- it never went inside, so a
    #: number would be invented (the asymmetry `SourceScan.unreadable_dirs` already carries).
    unreadable_dirs: tuple[str, ...] = ()
    #: Files present but unhashable, so their content could not be identified either way.
    unreadable_files: tuple[str, ...] = field(default=())

    @property
    def complete(self) -> bool:
        """Whether the walk saw everything, so :attr:`unaccounted` can be read as a count.

        False means a folder or a file was unreadable, and any record whose content lives there
        is in ``unaccounted`` for a reason that has nothing to do with the file being gone.
        """
        return not self.unreadable_dirs and not self.unreadable_files

    @property
    def reconciled(self) -> bool:
        """Whether every record and every file agreed -- nothing moved, strayed or went missing.

        **``debris`` is deliberately not part of this**, and the omission is a decision rather
        than an oversight. This property drives the CLI's exit code, and a leftover
        ``.partial`` is not a disagreement between the record and the disk -- it is litter beside
        them. Failing a run for it would turn a successful copy into a scripted failure. It is
        reported instead, which is what `(acz)` said was owed.
        """
        return not self.moved and not self.stray and not self.unaccounted and self.complete


def reconcile(  # noqa: PLR0913 - each argument is a distinct class of observation
    *,
    recorded: Mapping[str, str],
    on_disk: Collection[str],
    identified: Mapping[str, str],
    unreadable_dirs: Collection[str] = (),
    unreadable_files: Collection[str] = (),
    debris: Collection[str] = (),
) -> RescanReport:
    """Classify a drive's records and files. Pure: no I/O, no catalog, no filesystem.

    ``recorded`` maps a drive-relative POSIX path to the content hash the catalog holds there.
    ``on_disk`` is every media path the walk found. ``identified`` maps the paths the caller
    chose to hash -- the candidates, which by the PLACED rule are exactly the files *not* at a
    recorded path -- to the hash it read.

    A path in ``identified`` that is also in ``recorded`` is accepted and treated as a candidate
    anyway; this function does not police the caller's choice of what to read, because doing so
    would make it depend on the very rule it exists to express.
    """
    disk = set(on_disk)
    placed = tuple(sorted(rel for rel in recorded if rel in disk))
    absent_records = sorted(rel for rel in recorded if rel not in disk)

    where: defaultdict[str, list[str]] = defaultdict(list)
    for relative, sha in identified.items():
        where[sha].append(relative)

    moved: list[MovedCopy] = []
    unaccounted: list[str] = []
    for relative in absent_records:
        sha = recorded[relative]
        found = where.get(sha)
        if found:
            moved.append(MovedCopy(sha, relative, tuple(sorted(found))))
        else:
            unaccounted.append(relative)

    # Whatever no move claimed and no record already explains. Derived by subtraction rather
    # than by a second rule, so the buckets cannot overlap or leave a gap however the inputs are
    # shaped -- the same discipline `models.partition_for_report` applies to the organize tally.
    #
    # ``placed`` is subtracted too, and it is not redundant: the PLACED rule means a caller
    # should never hash a file that is where the catalog says, but a caller that does anyway
    # would otherwise see its own library reported as stray. A bucket that depends on the
    # caller having obeyed an unenforced rule is one wrong call away from a false alarm.
    claimed = {path for entry in moved for path in entry.found}
    stray = tuple(sorted(set(identified) - claimed - set(placed)))

    return RescanReport(
        placed=placed,
        moved=tuple(moved),
        stray=stray,
        unaccounted=tuple(unaccounted),
        unreadable_dirs=tuple(sorted(unreadable_dirs)),
        unreadable_files=tuple(sorted(unreadable_files)),
        debris=tuple(sorted(debris)),
    )
