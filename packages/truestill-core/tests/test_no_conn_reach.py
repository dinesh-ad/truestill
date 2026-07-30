"""No production code outside Catalog may reach into ``Catalog._conn`` (audit F6)."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PACKAGES_SRC = (
    REPO / "packages/truestill-core/src",
    REPO / "packages/truestill-cli/src",
    REPO / "packages/truestill-app/src",
)
_CONN_REACH = re.compile(r"\._conn\b")
# Catalog (and HashCache) own their private connection; everything else uses public methods.
_ALLOWED = frozenset(
    {
        "packages/truestill-core/src/truestill_core/catalog.py",
        "packages/truestill-core/src/truestill_core/hash_cache.py",
    }
)


def test_no_production_code_reaches_catalog_conn() -> None:
    offenders: list[str] = []
    for root in PACKAGES_SRC:
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(REPO).as_posix()
            if rel in _ALLOWED or "__pycache__" in path.parts:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if _CONN_REACH.search(line):
                    offenders.append(f"{rel}:{n}: {line.strip()}")
    assert not offenders, "production ._conn reach(es) outside Catalog/HashCache:\n" + "\n".join(
        offenders
    )
