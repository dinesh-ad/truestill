"""Migration re-derivation must obey the warm-read rule like every other reader (audit F18).

`IMPLEMENTATION_STANDARDS.md` §8: "A warm second pass must make **zero** exiftool subprocess
calls". `migrate.rederive_rules` was exempt from that guarantee - not by decision, by omission:
it called `read_metadata` with no `HashCache`, so every preview of the same drive paid the full
exiftool cost again, forever.

**Measured before the fix** (`PERFORMANCE.md` §1.1): five previews of the real 2,224-file Output
drive at 12.27 / 12.21 / 12.22 / 12.28 / 12.25 s - spread **1.01x**. The second pass was not one
percent cheaper than the first. `plan_migration` itself is 82 ms; the remaining 12.2 s was
re-derivation nobody cached.

**Why passing a cache here is not a preview-purity violation.** §5 requires a migration preview
to write nothing, and its two guards - `test_a_preview_moves_nothing_and_writes_nothing` and
`test_drive_preview_endpoints_never_refresh_the_catalog` - assert on the **drive tree** and the
**catalog bytes**. The hash cache is neither: §8 puts it in a sidecar *beside* the catalog
precisely because it is machine-local, disposable and high-churn ("delete the file and nothing
is lost but time"). The decisive precedent is that `service.organize_preview` is also a preview
and has always opened `HashCache.beside(db)` and written to it. Migration preview was the
inconsistent one, and both §5 guards still pass unchanged after this.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import truestill_core.exif as exif_mod
from truestill_core.catalog import Catalog
from truestill_core.hash_cache import HashCache
from truestill_core.hashing import sha256_file
from truestill_core.migrate import label_routes, rederive_rules

pytestmark = pytest.mark.skipif(
    __import__("shutil").which("exiftool") is None, reason="exiftool not installed"
)


@pytest.fixture
def counted_exif(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Count real exiftool subprocess invocations (same shape as test_metadata_cache)."""
    counts = {"runs": 0}
    real = subprocess.run

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, list | tuple) and cmd and "exiftool" in str(cmd[0]):
            counts["runs"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", wrapped)
    monkeypatch.setattr(exif_mod.binaries, "run", wrapped)
    return counts


def _ambiguous_drive(db: Path, root: Path) -> str:
    """A drive whose only label is ``Camera`` - ambiguous by construction, so re-derive fires."""
    uuid = "D-CACHE"
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=uuid, label="Drive")
        for i in range(3):
            rel = f"Camera/2023/08/IMG_{i}.jpg"
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"\xff\xd8\xff\xdb" + f"photo-{i}".encode())
            sha = sha256_file(path)
            catalog.record_uploaded(
                source_path=f"/src/IMG_{i}.jpg",
                original_name=f"IMG_{i}.jpg",
                sha256=sha,
                copy_sha256=sha,
                perceptual=None,
                size=path.stat().st_size,
                captured_at="2023-08-20T14:30:00",
                category="Camera",
                relative=rel,
                drive_uuid=uuid,
            )
    return uuid


def test_a_warm_rederive_makes_zero_exiftool_calls(
    tmp_path: Path, counted_exif: dict[str, int]
) -> None:
    """The §8 rule, now applied to this path too."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    uuid = _ambiguous_drive(db, root)

    with Catalog(db) as catalog:
        routes = label_routes(catalog, uuid)
        assert any(r.needs_decision for r in routes), "fixture must actually be ambiguous"
        with HashCache.beside(db) as cache:
            cold = rederive_rules(catalog, uuid, root, routes, cache=cache).rules
        assert counted_exif["runs"] >= 1, "the cold pass must really invoke exiftool"

        counted_exif["runs"] = 0
        with HashCache.beside(db) as cache:
            warm = rederive_rules(catalog, uuid, root, routes, cache=cache).rules

    assert counted_exif["runs"] == 0, "warm re-derive still shelled out to exiftool"
    assert warm == cold, "the cache must not change the answer, only the cost"


def test_rederive_without_a_cache_still_works_and_still_reads(
    tmp_path: Path, counted_exif: dict[str, int]
) -> None:
    """Cry-wolf half: the cache is optional, and omitting it must not silently no-op the read.

    A "fix" that made ``cache=None`` skip re-derivation entirely would pass the test above and
    destroy the feature - re-derivation is what stops an ambiguous label being routed by guess.
    """
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    uuid = _ambiguous_drive(db, root)

    with Catalog(db) as catalog:
        routes = label_routes(catalog, uuid)
        first = rederive_rules(catalog, uuid, root, routes).rules
        assert counted_exif["runs"] >= 1

        counted_exif["runs"] = 0
        second = rederive_rules(catalog, uuid, root, routes).rules

    assert counted_exif["runs"] >= 1, "no cache means no caching - it must read again"
    assert second == first


def test_the_cache_does_not_change_which_rule_a_file_resolves_to(tmp_path: Path) -> None:
    """§8: the cache can only remove work, never change an answer. Pinned here too."""
    db, root = tmp_path / "c.sqlite", tmp_path / "drive"
    uuid = _ambiguous_drive(db, root)

    with Catalog(db) as catalog:
        routes = label_routes(catalog, uuid)
        uncached = rederive_rules(catalog, uuid, root, routes).rules
        with HashCache.beside(db) as cache:
            rederive_rules(catalog, uuid, root, routes, cache=cache)  # populate
            cached = rederive_rules(catalog, uuid, root, routes, cache=cache).rules

    assert cached == uncached
