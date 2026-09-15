#!/usr/bin/env python3
"""What `/api/drives` costs to build and to send, at a given library size. `(akt)`

⚠ **MEASURED AT 300,000 RATHER THAN EXTRAPOLATED.** `at_risk` grows with the number of
single-copy files, and `single_copy_shas` carries a `GROUP BY ... HAVING COUNT(*) = 1` subquery -
so "it is linear" is a guess about a query plan, not a reading. This builds a real catalog whose
files all sit on exactly one drive, which is the worst case and also the case a new user is in.

`PERFORMANCE.md` §2.1 binds the method: `perf_counter` around the call only, n >= 5, median and
observed maximum, never a mean, and the corpus size on every row.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/truestill-core/src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/truestill-app/src"))

from truestill_app.service import drives as service
from truestill_core.catalog import Catalog


def _build(path: Path, rows: int) -> None:
    """One drive, every file on it exactly once - so every file is at risk."""
    with Catalog(path) as catalog:
        conn = catalog._conn
        conn.execute("INSERT INTO drives (uuid, label) VALUES ('D1', 'BackupA')")
        files = []
        copies = []
        for index in range(rows):
            sha = f"{index:064x}"
            relative = f"2014/2014-08/2014-08-12 - Everyday/20140812_IMG_{index:06d}.jpg"
            files.append((sha, f"IMG_{index:06d}.jpg", index, f"/in/IMG_{index:06d}.jpg", relative))
            copies.append((sha, "D1", relative))
        conn.executemany(
            "INSERT INTO files (sha256, original_name, size, source_path, category, relative,"
            " upload_status, processed_at)"
            " VALUES (?, ?, ?, ?, 'Camera', ?, 'uploaded', '2026-09-15T00:00:00+00:00')",
            files,
        )
        conn.executemany(
            "INSERT INTO file_copies (sha256, drive_uuid, relative) VALUES (?, ?, ?)", copies
        )
        conn.commit()
        conn.execute("ANALYZE")
        conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        args.db.parent.mkdir(parents=True, exist_ok=True)
        _build(args.db, args.rows)

    samples = []
    for _ in range(args.runs):
        start = time.perf_counter()
        risk = service.at_risk(args.db)
        samples.append((time.perf_counter() - start) * 1000)

    # The route composes these three; `json.dumps` with no spaces is what an ASGI reply carries.
    payload = {
        "drives": service.list_drives(args.db),
        "at_risk": risk,
        "cannot_name_library": service.cannot_name_library(args.db),
    }
    blob = json.dumps(payload, separators=(",", ":"))
    risk_blob = json.dumps(risk, separators=(",", ":"))

    if not args.keep:
        args.db.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "rows": args.rows,
                "at_risk_entries": len(risk) if isinstance(risk, list) else risk.get("total"),
                "build_median_ms": round(statistics.median(samples), 1),
                "build_max_ms": round(max(samples), 1),
                "at_risk_bytes": len(risk_blob),
                "payload_bytes": len(blob),
                "at_risk_share": f"{len(risk_blob) / len(blob):.1%}",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
