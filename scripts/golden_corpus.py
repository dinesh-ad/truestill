#!/usr/bin/env python3
"""The golden corpus differential: what the date resolver decides over Input, as one snapshot.

`record` walks the corpus read-only - `scan_source` -> `read_metadata` -> `plan`, the exact
pipeline the CLI preview drives (`cli.py:3403`), takeout sidecars absent for the same reason
they are absent there - and writes one sorted line per media file: relative path, resolved
date, `DateSource`, the resolver's `date_tag`, and the placement `plan` would produce. The
header carries the machine, the filesystem, the file count and the full source distribution,
so the census travels with the data and a distribution shift shows up in the first screen of
any diff.

`check` re-runs the same pipeline and prints the SUMMARY BEFORE THE DATA: files added and
removed, then every `source -> source` transition as a count, then date-only and target-only
drift counts, then at most `EXAMPLE_CAP` example lines per bucket. A rule change that moves
40,000 files must read as one line saying so, never as 40,000 lines.

⚠ **ON DEMAND ONLY, NEVER CI.** The corpus is a real machine's `/data/TruestillLibrary/Input`;
a runner does not have it, so the committed snapshot is evidence, not coverage -
`tests/golden/README.md` is the statement of that limit. Moves nothing, writes nothing under
the root; the only write is the snapshot file, and only under `record`.
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "truestill-core" / "src"))

from truestill_core.exif import read_metadata
from truestill_core.organizer import plan, scan_source
from truestill_core.progress import Progress

DEFAULT_ROOT = Path("/data/TruestillLibrary/Input")
DEFAULT_SNAPSHOT = ROOT / "tests" / "golden" / "input-dates.tsv"

#: Per-bucket example ceiling in `check` output. The summary is the deliverable; examples are
#: orientation. Elision is announced, never silent.
EXAMPLE_CAP = 5

UNDATED = "-"


@dataclass(frozen=True, slots=True)
class Row:
    """One file's answer: everything the differential compares."""

    relative: str
    date: str
    source: str
    tag: str
    target: str

    def line(self) -> str:
        return "\t".join((self.relative, self.date, self.source, self.tag, self.target))


def _filesystem_of(path: Path) -> str:
    """`df` on the root, so the header states the medium rather than implying one."""
    out = subprocess.run(
        ["df", "--output=fstype,source", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    fstype, device = out.stdout.strip().splitlines()[-1].split()
    return f"{fstype} ({device})"


def snapshot_rows(root: Path) -> list[Row]:
    """The pipeline, read-only: scan, read dates, plan. Sorted so the file diffs by position."""
    scan = scan_source(root)
    files = sorted(scan.media)

    def progress(p: Progress) -> None:
        if p.done % 500 == 0:
            print(f"  read {p.done}/{p.total}", file=sys.stderr)

    metadata = read_metadata(files, progress=progress)
    rows = [
        Row(
            relative=str(d.source.relative_to(root)),
            date=d.captured_at.isoformat() if d.captured_at is not None else UNDATED,
            source=str(d.date_source),
            tag=d.date_tag or UNDATED,
            target=str(d.relative),
        )
        for d in plan(files, metadata)
    ]
    rows.sort(key=lambda r: r.relative)
    return rows


def distribution(rows: list[Row]) -> Counter[str]:
    return Counter(r.source for r in rows)


def render(rows: list[Row], root: Path) -> str:
    dist = distribution(rows)
    dist_line = " ".join(f"{source}={count}" for source, count in sorted(dist.items()))
    header = [
        "# golden corpus snapshot - what the date resolver decided, file by file",
        "# regenerate: uv run python scripts/golden_corpus.py record",
        "# compare:    uv run python scripts/golden_corpus.py check",
        "# ON DEMAND ONLY - the corpus is one real machine's Input; CI never runs this and",
        "# this file is not CI coverage. tests/golden/README.md states the limit.",
        f"# root: {root}",
        f"# machine: {platform.node()} {platform.system().lower()} {platform.release()}",
        f"# filesystem: {_filesystem_of(root)}",
        f"# files: {len(rows)}",
        f"# distribution: {dist_line}",
        "# columns: relative<TAB>date<TAB>source<TAB>tag<TAB>target",
    ]
    return "\n".join(header) + "\n" + "\n".join(r.line() for r in rows) + "\n"


def parse_snapshot(text: str) -> dict[str, Row]:
    """Body lines only; the header is prose for humans and is not compared."""
    rows: dict[str, Row] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        relative, date, source, tag, target = line.split("\t")
        rows[relative] = Row(relative, date, source, tag, target)
    return rows


@dataclass(slots=True)
class Drift:
    """The differential, aggregated before it is ever itemized."""

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    #: (old source, new source) -> the files that made that move.
    source_moves: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    #: Same source, different resolved date.
    date_only: list[str] = field(default_factory=list)
    #: Same source and date, different planned placement.
    target_only: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (
            self.added or self.removed or self.source_moves or self.date_only or self.target_only
        )


def diff_rows(old: dict[str, Row], new: dict[str, Row]) -> Drift:
    drift = Drift()
    drift.added = sorted(set(new) - set(old))
    drift.removed = sorted(set(old) - set(new))
    for relative in sorted(set(old) & set(new)):
        was, now = old[relative], new[relative]
        if was == now:
            continue
        if was.source != now.source:
            drift.source_moves.setdefault((was.source, now.source), []).append(relative)
        elif was.date != now.date:
            drift.date_only.append(relative)
        elif was.target != now.target:
            drift.target_only.append(relative)
        else:  # only the tag moved - same mechanism family, still drift
            drift.date_only.append(relative)
    return drift


def _bucket(label: str, members: list[str]) -> list[str]:
    lines = [f"{label}: {len(members)} files"]
    lines += [f"    {m}" for m in members[:EXAMPLE_CAP]]
    if len(members) > EXAMPLE_CAP:
        lines.append(f"    ... and {len(members) - EXAMPLE_CAP} more not shown")
    return lines


def format_drift(drift: Drift) -> str:
    """Summary first, counts before names, elision announced. The wall of text is the failure."""
    if drift.clean:
        return "clean: the corpus resolves exactly as the committed snapshot says."
    lines = ["DRIFT - summary first, examples capped:"]
    if drift.added:
        lines += _bucket("  files added to the corpus", drift.added)
    if drift.removed:
        lines += _bucket("  files no longer in the corpus", drift.removed)
    for (was, now), members in sorted(drift.source_moves.items()):
        lines += _bucket(f"  source {was} -> {now}", members)
    if drift.date_only:
        lines += _bucket("  same source, different date (or tag)", drift.date_only)
    if drift.target_only:
        lines += _bucket("  same date and source, different placement", drift.target_only)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("record", "check"))
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        print(f"error: corpus root {args.root} is not here - this tool runs where the corpus is")
        return 2

    started = time.monotonic()
    rows = snapshot_rows(args.root)
    elapsed = time.monotonic() - started

    if args.mode == "record":
        args.snapshot.parent.mkdir(parents=True, exist_ok=True)
        args.snapshot.write_text(render(rows, args.root), encoding="utf-8")
        print(f"recorded {len(rows)} files in {elapsed:.1f}s -> {args.snapshot}")
        for source, count in sorted(distribution(rows).items()):
            print(f"  {source}: {count}")
        return 0

    committed = parse_snapshot(args.snapshot.read_text(encoding="utf-8"))
    drift = diff_rows(committed, {r.relative: r for r in rows})
    print(f"compared {len(rows)} files in {elapsed:.1f}s against {args.snapshot.name}")
    print(format_drift(drift))
    return 0 if drift.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
