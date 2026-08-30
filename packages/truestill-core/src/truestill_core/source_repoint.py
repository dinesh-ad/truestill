"""Repoint `files.source_path` after the folder it names has moved (`BACKLOG.md` ``(yy)``).

**Deliberately narrow, and the narrowing is the feature.** Organized drive trees need no repair:
their locations are `file_copies.relative` under a marker uuid, so a remounted drive verifies
clean with no user action at all. The only genuinely broken thing after a move is
`files.source_path`, which is absolute and records *where a file came from* rather than where a
copy of it lives. Inventing a reconnect flow for the drive trees would be rebuilding something
that already works - `moving-machines.md` says so, and the backlog says it twice.

**One action, all descendants.** The unit of repair is the *root*, not the file: point once at
where the folder went and every recorded path beneath it is rewritten. Fixing a library one file
at a time is the wrong unit, which is the lesson worth taking from Lightroom's Find Missing
Folder.

**Why the hash proof is not optional here, and why it is stricter than it looks.** `reclaim`
deletes `files.source_path` from disk. Its safety gate re-hashes the **destination copy on the
drive** - it proves a good copy exists elsewhere, and it never hashes the source at all
(`reclaim.plan_reclaim`: `_source_present` is an existence check). So a `source_path` rewritten
to the wrong tree would have reclaim delete a file it never verified, on the strength of a
completely different file being intact. Nothing here rewrites a row until the new root has been
proven to hold the recorded content.

The proof reuses `drive_adoption.inspect_root` rather than growing a second sampling mechanism:
structurally that function asks exactly this question - *given a candidate root and a set of
recorded relative paths with expected digests, is this that tree?* - and its thresholds were
chosen and measured for it.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath

from truestill_core.drive_adoption import (
    AdoptionVerdict,
    RecordedDrive,
    inspect_root,
)
from truestill_core.hashing import sha256_file


@dataclass(frozen=True, slots=True)
class RepointRow:
    """One recorded source, and where it would move to."""

    sha256: str
    old_path: str
    new_path: str
    #: Whether a file is actually present at ``new_path`` right now.
    present: bool


@dataclass(frozen=True, slots=True)
class RepointPlan:
    """What a repoint would change, and whether it has earned the right to change it."""

    old_root: Path
    new_root: Path
    verdict: AdoptionVerdict
    rows: list[RepointRow]
    #: Recorded sources under ``old_root`` that still exist where they are. Their presence means
    #: the root did not move, and is the reason an intact library is refused rather than "fixed".
    still_present_at_old: int
    hashed: int
    proven: int

    @property
    def movable(self) -> list[RepointRow]:
        """Rows that will actually be rewritten: only those whose new path exists.

        A row whose file is not at the new root is left pointing where it was. Rewriting it
        would trade a path that is honestly dead for one that is confidently wrong, and
        `reclaim` treats a present file at `source_path` as the thing to delete.
        """
        return [row for row in self.rows if row.present]

    @property
    def may_apply(self) -> bool:
        return self.verdict is AdoptionVerdict.PROVEN and bool(self.movable)


def _relative_to(path: str, root: Path) -> str | None:
    """``path``'s tail under ``root``, or ``None`` when it is not beneath it.

    Compared through `PurePath`, never as strings: a string prefix test says ``/photos-old`` is
    under ``/photos``, and on Windows it would also miss ``C:\\Photos`` against ``C:\\photos``.

    ⚠ **Returned in POSIX form, and that is not cosmetic.** This value becomes a key in
    `drive_adoption.RecordedDrive.digests`, whose **other** producer fills the same field from the
    catalog's ``relative`` column - which is POSIX by contract. `str()` here renders with the
    running platform's separator, so on Windows one producer of one field would have used
    backslashes and the other forward slashes. Today's consumers only ever do ``root / relative``,
    which accepts either, so nothing is broken - but a field populated two ways is the drift
    `(ais)` is about, one layer in from the test that made it visible.
    """
    try:
        return PurePath(path).relative_to(PurePath(str(root))).as_posix()
    except ValueError:
        return None


def plan_repoint(
    recorded: Sequence[tuple[str, str]],
    old_root: Path,
    new_root: Path,
    *,
    hasher: Callable[[Path], str] = sha256_file,
    cancel: threading.Event | None = None,
) -> RepointPlan:
    """Work out what moving ``old_root`` to ``new_root`` would rewrite, and prove it first.

    ``recorded`` is ``(source_path, sha256)`` for every catalogued file - `Catalog.seed_rows`
    without its perceptual column.

    **Complexity: O(n)** over the catalog to select and re-base the rows, plus the sampling
    proof, which is at most `STAT_SAMPLE` stats and `HASH_PROOF` full reads *regardless of
    library size*. Nothing walks the new tree.
    """
    rows: list[RepointRow] = []
    digests: dict[str, str] = {}
    still_present = 0
    for source_path, sha256 in recorded:
        relative = _relative_to(source_path, old_root)
        if relative is None:
            continue
        if Path(source_path).is_file():
            still_present += 1
        target = new_root / relative
        digests[relative] = sha256
        rows.append(
            RepointRow(
                sha256=sha256,
                old_path=source_path,
                new_path=str(target),
                present=target.is_file(),
            )
        )

    if not rows:
        return RepointPlan(old_root, new_root, AdoptionVerdict.NO_MATCH, [], 0, 0, 0)

    # `RecordedDrive` is used here for what it structurally is - a set of recorded relative
    # paths with the digest each should present. Reusing it keeps one sampling mechanism with
    # one set of measured thresholds; a second copy is how the two drift apart.
    offers = inspect_root(
        new_root,
        [RecordedDrive(uuid="", label=str(old_root), digests=digests)],
        hasher=hasher,
        cancel=cancel,
    )
    if not offers:
        return RepointPlan(old_root, new_root, AdoptionVerdict.NO_MATCH, rows, still_present, 0, 0)
    offer = offers[0]
    return RepointPlan(
        old_root, new_root, offer.verdict, rows, still_present, offer.hashed, offer.proven
    )
