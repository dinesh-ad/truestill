#!/usr/bin/env python3
"""What `find` costs, per term and per row. `(abj)`

⚠ **MEASURED AT 300,000 RATHER THAN EXTRAPOLATED FROM 2,574.** A leading-wildcard `LIKE` is a full
scan by construction, so the shape *ought* to be linear - but "ought" is how a claim gets into a
document without evidence behind it. This builds a real catalog at the size in question and asks
it, which also catches anything that is not linear (cache effects, the `ORDER BY` temp B-tree).

`PERFORMANCE.md` §2.1 binds the method: `perf_counter` around the query only, n >= 5, median and
observed maximum, never a mean, and the corpus size stated on every row.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packages/truestill-core/src"))

from truestill_core.catalog import Catalog, _search_where, parse_search_terms

#: Shaped like the real corpus: `IMG_xxxx.jpg` under a dated tree, which is exactly the pair of
#: terms `(abj)` is about - a name token and a year token that never appear adjacent.
_YEARS = (2013, 2014, 2015, 2016, 2017)


def _build(path: Path, rows: int) -> None:
    with Catalog(path) as catalog:
        conn = catalog._conn
        conn.execute("INSERT INTO drives (uuid, label) VALUES ('D1', 'dest-one')")
        files = []
        copies = []
        for index in range(rows):
            sha = f"{index:064x}"
            year = _YEARS[index % len(_YEARS)]
            month = (index % 12) + 1
            relative = (
                f"{year}/{year}-{month:02d}/{year}-{month:02d} - Everyday/"
                f"{year}{month:02d}15_120000_IMG_{index:06d}.jpg"
            )
            files.append(
                (
                    sha,
                    f"IMG_{index:06d}.jpg",
                    index,
                    f"/src/incoming/IMG_{index:06d}.jpg",
                    "Camera",
                    relative,
                    "uploaded",
                    "2026-09-15T00:00:00+00:00",
                )
            )
            copies.append((sha, "D1", relative))
        conn.executemany(
            "INSERT INTO files (sha256, original_name, size, source_path, category, relative,"
            " upload_status, processed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            files,
        )
        conn.executemany(
            "INSERT INTO file_copies (sha256, drive_uuid, relative) VALUES (?, ?, ?)", copies
        )
        conn.commit()
        conn.execute("ANALYZE")
        conn.commit()


def _timed(conn: sqlite3.Connection, sql: str, params: list[object], runs: int) -> dict[str, float]:
    samples = []
    for _ in range(runs):
        start = time.perf_counter()
        conn.execute(sql, params).fetchall()
        samples.append((time.perf_counter() - start) * 1000)
    return {
        "median_ms": round(statistics.median(samples), 2),
        "max_ms": round(max(samples), 2),
        "min_ms": round(min(samples), 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--runs", type=int, default=7)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        args.db.parent.mkdir(parents=True, exist_ok=True)
        _build(args.db, args.rows)

    out = []
    # ⚠ **THE STATEMENT THAT SHIPS, NEVER A RETYPED TWIN** - audit F11's rule, which is why
    # `find_copies_query` is public in the first place. A hand-written copy here would measure a
    # query the product does not run, and would go stale the first time the real one changed.
    with Catalog(args.db) as catalog:
        conn = catalog._conn
        for terms in ("IMG", "2014 IMG", "2014 IMG Everyday", "a b c d"):
            page_sql, page_params = catalog.find_copies_query(terms, limit=50, offset=0)
            where, params = _search_where(parse_search_terms(terms))
            count_sql = (
                "SELECT COUNT(*) FROM file_copies fc JOIN files f ON f.sha256 = fc.sha256 "
                f"JOIN drives d ON d.uuid = fc.drive_uuid WHERE {where}"
            )
            out.append(
                {
                    "rows": args.rows,
                    "terms": len(parse_search_terms(terms)),
                    "query": terms,
                    "matches": conn.execute(count_sql, params).fetchone()[0],
                    "page": _timed(conn, page_sql, page_params, args.runs),
                    "count": _timed(conn, count_sql, params, args.runs),
                }
            )
    if not args.keep:
        args.db.unlink(missing_ok=True)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
