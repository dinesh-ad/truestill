#!/usr/bin/env python3
"""Peak memory of writing one run record, at a given file count. `(akr)`

⚠ **ONE PROCESS PER POINT, AND THAT IS NOT A CONVENIENCE.** `ru_maxrss` is a high-water mark for
the life of the process, so measuring 75k and then 300k in one process reports the larger figure
twice and a flat line looks like constant memory. The caller runs this once per point.

**Entries are shaped from a REAL record**, not invented: `Test 1/look-2026-09-05/last-run.json`
holds 3,826 organize entries at 942 bytes each, and `_template` is one of them with the paths
varied per index so no key is accidentally constant-folded by the encoder.

Two numbers, because they answer different questions:

* ``rss_peak_mib`` - what the machine actually paid, from `resource.getrusage`. This is the one
  the cliff is about.
* ``traced_peak_mib`` - Python-level allocation during the write call alone, from `tracemalloc`,
  with the entries already built. This isolates **serialisation** from the cost of holding the
  data, which is the caller's and is not what this change is about.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import tracemalloc
from collections.abc import Iterator
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/truestill-core/src"))

from truestill_core.run_record import (
    RUN_RECORD_FORMAT,
    RunHeader,
    build_run_record,
    write_run_record,
)

#: One real organize entry, from the 3,826-file record. Varied per index by `_entries`.
_TEMPLATE: dict[str, Any] = {
    "source": "/data/TruestillLibrary/Input/2014/IMG_20140812_180155.jpg",
    "status": "uploaded",
    "detail": "",
    "landed_at": "2014/2014-08/2014-08-12 - Wayanad/20140812_180155_IMG_20140812_180155.jpg",
    "planned_relative": "2014/2014-08/2014-08-12 - Wayanad/20140812_180155_IMG_20140812_180155.jpg",
    "category": "Camera",
    "confidence": "high",
    "rule": "device",
    "reason": "Make/Model present (Motorola XT1033)",
    "captured_at": "2014-08-12T18:01:55",
    "date_source": "exif",
    "date_tag": "EXIF:DateTimeOriginal",
    "needs_review": False,
    "sha256": "9f2c4a1b8e7d6c5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f",
    "perceptual": "d4c3b2a190807060",
    "unreadable": None,
    "should_upload": True,
    "is_unique": True,
    "exact_duplicate": None,
    "near_duplicate": None,
}


def _entries(count: int) -> Iterator[dict[str, Any]]:
    for index in range(count):
        entry = dict(_TEMPLATE)
        entry["source"] = f"/data/TruestillLibrary/Input/2014/IMG_2014{index:08d}.jpg"
        entry["landed_at"] = f"2014/2014-08/2014-08-12 - Wayanad/2014{index:08d}.jpg"
        entry["planned_relative"] = entry["landed_at"]
        entry["sha256"] = f"{index:064x}"
        yield entry


#: ⚠ **IMPORTED THROUGH `importlib`, AND THAT IS FOR THE TYPE CHECKER, NOT FOR STYLE.** `resource`
#: is POSIX-only and does not exist on Windows, so a plain `import resource` is red under
#: `make typecheck`, which runs mypy over `--platform linux darwin win32`. `hashing._FADVISE` is
#: the recorded precedent for the same problem one module over (`4759efd`).
_RESOURCE = importlib.import_module("resource") if sys.platform != "win32" else None


def _rss_mib() -> float:
    """Peak RSS so far, in MiB. ``0.0`` where the platform cannot answer.

    ⚠ **`ru_maxrss` is KiB on Linux and BYTES on macOS**, so the same number means a thousandfold
    different thing on the two platforms this can run on. The measurement lane is Linux and the
    figures in `(akr)` are Linux; a macOS reading from this script would be wrong by 1024 and is
    refused rather than silently scaled, because a scale factor nobody checked is how a
    measurement becomes a claim.
    """
    if _RESOURCE is None or sys.platform == "darwin":
        return 0.0
    usage = _RESOURCE.getrusage(_RESOURCE.RUSAGE_SELF)
    return float(usage.ru_maxrss) / 1024


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--files", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mode", choices=["legacy", "stream"], required=True)
    parser.add_argument(
        "--materialise",
        action="store_true",
        help="build the entries into a list first (what a caller holding a list costs)",
    )
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    header = RunHeader(kind="organize", source="/data/TruestillLibrary/Input", destination="/x")
    supplied: Any = list(_entries(args.files)) if args.materialise else _entries(args.files)
    rss_before = _rss_mib()

    tracemalloc.start()
    if args.mode == "legacy":
        # The shape as it stood before `(akr)`: whole payload assembled, then one dumps().
        payload = {
            "format": RUN_RECORD_FORMAT,
            "run": {"kind": header.kind, "intended_total": args.files, "attempted": args.files},
            "files": supplied if isinstance(supplied, list) else list(supplied),
        }
        partial = args.out.with_name(args.out.name + ".partial")
        partial.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        partial.replace(args.out)
        written = args.files
    else:
        error = write_run_record(
            args.out,
            build_run_record(
                header,
                files=supplied,
                intended_total=args.files,
                attempted=args.files,
                stopped=None,
            ),
        )
        if error is not None:
            print(f"write failed: {error}", file=sys.stderr)
            return 1
        written = args.files
    traced_peak = tracemalloc.get_traced_memory()[1] / 1024 / 1024
    tracemalloc.stop()

    print(
        json.dumps(
            {
                "mode": args.mode,
                "materialised": args.materialise,
                "files": args.files,
                "entries": written,
                "bytes_on_disk": args.out.stat().st_size,
                "rss_before_mib": round(rss_before, 1),
                "rss_peak_mib": round(_rss_mib(), 1),
                "traced_peak_mib": round(traced_peak, 1),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
