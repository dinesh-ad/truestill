"""What a drive is carrying that this catalog does not have. **Reads; writes nothing.**

Stage 1 of the restore arc, and deliberately only a reader. Nothing here copies a file, writes a
catalog row, or touches a drive. The engine that would do the copying already exists and is
already direction-agnostic - `backup.copy_to_drive`'s only directional refusal is that the two
sides are not the same drive - so what was missing was never the engine. It was the question.

⚠ **THE ANSWER IS A COUNT OF RECORDED COPIES, NOT A COUNT OF FILES OBSERVED ON THE DRIVE, AND
THAT DISTINCTION IS THE WHOLE HONESTY OF THIS MODULE.** `dedup.credible_copies` states the cost of
confusing them: *"A `file_copies` row is a claim, not an observation... the row is written when the
bytes are handed to the kernel, so an interruption leaves rows describing copies the medium never
took - measured on removable media as **836 zero-byte files on exFAT and 304 unreadable on NTFS**
against confident rows."* `backup.py` measures the same thing from the other side: *"429 rows
against 124 files actually there, **305 false custody claims**."*

So every figure this module produces is labelled with what produced it, and
:func:`render` never prints a row count as a promise about bytes.

**Three states a reader must tell apart, because two of them look like the third:**

1. **A real zero** - the drive's recorded copies are all recorded here too.
2. ⚠ **A drive nobody has walked.** `truestill drives --init` writes a marker and does not walk, so
   `file_copies` can be empty while the drive is full. The gap then reads **0 for a drive holding
   everything**, which is the worst wrong answer available - it tells a user with no backup that
   they have nothing to recover. :attr:`Carried.drive_walked` separates it and
   :func:`render` says so instead of printing a number.
3. **A library this process could not look at.** The drive half always comes from the catalog and
   answers with the drive unplugged, which is the design `date-provenance-design.md` states
   outright: *"a drive can be disconnected. The catalog answers instantly and offline."* The
   library half can be *checked* when the library is reachable, and cannot when it is not - so
   which half was observed is reported rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from truestill_core.catalog import Catalog
from truestill_core.dedup import credible_copies
from truestill_core.destinations import LocalDestination
from truestill_core.drive import DriveMarker
from truestill_core.units import format_bytes

#: ⚠ **WHAT A COUNT ON A DRIVE CARD IS, and it is not what it looks like.** A number beside a
#: drive reads as a fact about that drive; this one is a fact about this catalog's RECORDS of it,
#: with no stat and no read. `render` already says the long form - *"Counted from records, not
#: from a fresh look at the drive"* - and this is the short form a card has room for.
FROM_RECORDS = "from this catalog's records, not from a fresh look at the drive"

#: The state that must never render as a count. `drives --init` writes a marker and does not walk,
#: so `file_copies` is empty while the drive is full - and "0 to bring back" told to somebody who
#: has just lost a library, about a drive holding all of it, is the worst sentence in the product.
NOT_WALKED_YET = "not checked yet, so this catalog cannot say what is on it"

#: ⚠ **"RECORD", NEVER "HAVE", AND THE VERB IS THE HONESTY.** This count is records against
#: records - no stat on either side - so a library that lost files from its disk still *records*
#: them and this reads zero. `recover`'s own preview DOES stat the library and will find them, so
#: "nothing your library does not already **have**" would put the card and the preview in flat
#: contradiction. Measured: a library with 20 rows and 14 files on disk reads 0 here and 6 there.
CARRIES_NOTHING_EXTRA = "nothing here that your library does not already record"

#: The count's own phrase, for the same reason. The card renders this with the number and
#: :data:`FROM_RECORDS` beside it; neither half is composed by a surface.
CARRIES_UNRECORDED = "your library does not record"


@dataclass(frozen=True, slots=True)
class DriveRef:
    """One side of the comparison, named. **Identity only - never proof the drive is there.**

    ⚠ **Deliberately NOT a `DriveMarker`**, which is *"the identity of a destination drive, as
    stored in its marker file"* - a shape that can only be filled by reading the drive. The whole
    point of this module is that the drive may be **absent**, in which case its identity comes
    from the ``drives`` table and nothing was read from the drive at all. Filling a marker from a
    catalog row to get past a type would be this module's own subject, committed in its
    signature.
    """

    uuid: str
    label: str

    @classmethod
    def of(cls, marker: DriveMarker) -> DriveRef:
        """The drive that was actually read, here and now."""
        return cls(uuid=marker.uuid, label=marker.label)


@dataclass(frozen=True, slots=True)
class Carried:
    """What one drive carries that this catalog does not record here.

    Every count carries its provenance in its own name: ``recorded_*`` came from the catalog,
    ``contradicted_here`` came from looking. There is no field that merges the two, because a
    merged number is exactly what cannot be labelled.
    """

    drive_label: str
    library_label: str
    #: Rows in ``file_copies`` for the drive. **Records, not a look at the drive.**
    recorded_on_drive: int
    #: Rows in ``file_copies`` for the library, before any check against the disk.
    recorded_here: int
    #: Recorded on the drive and not credibly here. The answer, in records.
    gap: int
    #: Bytes the catalog recorded for those copies. ⚠ **A FLOOR, not a total**, whenever
    #: :attr:`gap_bytes_unknown` is non-zero - a ``file_copies`` row may carry a NULL ``size``,
    #: and counting those as zero would quietly shrink the figure a person is about to size a
    #: disk against.
    gap_bytes: int
    #: How many of the gap's rows carried no size at all. ``0`` means the figure above is whole.
    gap_bytes_unknown: int
    #: ⚠ False when ``file_copies`` holds nothing for this drive - which means nobody has walked
    #: it, **not** that it is empty. See the module docstring, state 2.
    drive_walked: bool
    #: Whether the library was reachable and could be stat'd. When false, ``gap`` rests entirely
    #: on records for both halves.
    library_observed: bool
    #: Rows for the library that its own disk contradicted - recorded here, and not actually
    #: there at the recorded size. Always ``0`` when :attr:`library_observed` is false, and that
    #: zero means "not looked", never "none found".
    contradicted_here: int


def carried_by(
    catalog: Catalog,
    *,
    drive: DriveRef,
    library: DriveRef,
    library_root: Path | None,
) -> Carried:
    """Compare two drives' recorded copies. **One catalog read each; no file is opened.**

    ``library_root`` is the one optional input and the only thing that costs a syscall: given a
    reachable path, the library's recorded rows are checked against what is actually at them, so
    a row the disk contradicts stops counting as "already here" and its content re-enters the
    gap. Pass ``None`` - or an unreachable path - and the comparison is records against records,
    which is still a true answer to a narrower question.

    Cost: two indexed reads. `file_copies`' own ``PRIMARY KEY (sha256, drive_uuid)`` serves them,
    and `catalog.copies_on_drive` is a bare ``SELECT ... WHERE drive_uuid = ?``. The sibling
    constant in `Catalog` records the scale this is expected at: *"the caller here is a preview
    over a whole folder, so 40,000 is an ordinary size."*
    """
    drive_rows = catalog.copies_on_drive(drive.uuid)
    here_rows = catalog.copies_on_drive(library.uuid)

    # `sizes()` is the stat pass, and it is the only place this module touches a filesystem.
    # A root that is not there answers `None`, which `credible_copies` treats as "cannot say
    # cheaply" rather than as "nothing is there" - its own rule, kept rather than restated.
    sizes = None
    if library_root is not None and library_root.is_dir():
        sizes = LocalDestination(library_root).sizes()

    recorded_here = {str(r["sha256"]): str(r["relative"]) for r in here_rows}
    credible = credible_copies(
        recorded_here,
        sizes=sizes,
        expected={
            str(r["sha256"]): (None if r["size"] is None else int(r["size"])) for r in here_rows
        },
    )
    present = set(credible)
    gap_rows = [r for r in drive_rows if str(r["sha256"]) not in present]

    return Carried(
        drive_label=drive.label,
        library_label=library.label,
        recorded_on_drive=len(drive_rows),
        recorded_here=len(here_rows),
        gap=len(gap_rows),
        gap_bytes=sum(int(r["size"]) for r in gap_rows if r["size"] is not None),
        gap_bytes_unknown=sum(1 for r in gap_rows if r["size"] is None),
        drive_walked=bool(drive_rows),
        library_observed=sizes is not None,
        contradicted_here=len(recorded_here) - len(credible) if sizes is not None else 0,
    )


def render(carried: Carried, *, drive_path: str | None) -> str:
    """The report, worded once. `IMPLEMENTATION_STANDARDS.md` §9.

    Wording lives in core for `catalog_busy`'s reason - the CLI and the app answer the same
    condition and must not drift - even though only the CLI reads it today. Presentation (an exit
    code, a screen) stays with each surface.

    ``drive_path`` is ``None`` when the drive is **not connected** and was named by its label out
    of the ``drives`` table. The answer is just as true - the drive half is records on both paths
    - but what the reader can do next is different, and so is what a number means to someone
    holding no disk. So the absence is stated rather than papered over with a path that is not
    there.
    """
    lines: list[str] = []

    if not carried.drive_walked:
        # ⚠ State 2. Printing "0 files" here would tell somebody who has just lost a disk that
        # their backup holds nothing to recover, which is both false and the most expensive
        # moment in the product to be wrong. So the number is withheld and the reason given.
        lines.append(
            f"This catalog has no record of anything on '{carried.drive_label}', so it cannot say"
            f"\nwhat the drive is carrying. That is not the same as the drive being empty: a drive"
            f"\nregistered with `truestill drives --init <path> --label <name>` has a marker"
            f"\nand was never walked."
        )
        lines.append(
            f"\nWalk it and find out:  truestill rescan {drive_path}"
            if drive_path is not None
            else "\nConnect it and walk it:  truestill rescan <the drive's folder>"
        )
        return "\n".join(lines)

    lines.append(
        f"'{carried.drive_label}' carries {carried.gap:,} file(s) this catalog does not record"
        f" on '{carried.library_label}'."
    )
    if carried.gap_bytes or carried.gap_bytes_unknown:
        # `units.format_bytes` rather than a local division: the first hand-rolled version
        # divided by 1e9 and printed "About 0.0 GB" for a real gap of six photographs, which is
        # worse than printing nothing. One formatter, so two surfaces cannot disagree.
        lines.append(
            f"       {format_bytes(carried.gap_bytes)}, by the sizes recorded"
            + (
                f" - AT LEAST, because {carried.gap_bytes_unknown:,} of those"
                f"\n       rows carry no size."
                if carried.gap_bytes_unknown
                else "."
            )
        )

    # ⚠ THE PROVENANCE LINE, and it is not optional garnish. The two halves of this answer come
    # from different places and a reader who assumes both were looked at is reading a different
    # fact from the one that was measured.
    lines.append(
        f"\n       Counted from records, not from a fresh look at the drive:"
        f"\n       {carried.recorded_on_drive:,} recorded on '{carried.drive_label}',"
        f" {carried.recorded_here:,} recorded here."
    )
    if carried.library_observed:
        lines.append(
            "       This library WAS checked against its own disk"
            + (
                f", and {carried.contradicted_here:,} recorded file(s) were not there."
                if carried.contradicted_here
                else " and every recorded file was there."
            )
        )
    else:
        lines.append(
            "       This library was NOT checked against its own disk, so 'recorded here'"
            "\n       means recorded, not present."
        )
    if drive_path is None:
        lines.append(
            f"       '{carried.drive_label}' is NOT CONNECTED. Nothing was read from it; this is"
            f"\n       the catalog's record of it. Connect it and check:  truestill rescan"
            f" <its folder>"
        )
    else:
        lines.append(
            f"       Nothing was read from '{carried.drive_label}' itself. To check what is"
            f" really\n       there:  truestill rescan {drive_path}"
        )
    return "\n".join(lines)
