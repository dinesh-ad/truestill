"""Every runtime dependency a buyer installs is argued for in the contract's inventory.

**The drift this closes.** `IMPLEMENTATION_STANDARDS.md` §7 opens with "Runtime deps must justify
themselves against stdlib" and then lists them. Three were missing: `platformdirs` (added to
`truestill-core` with the OS-conventional catalog work) and `starlette` + `uvicorn` (declared by
`truestill-app` since the UI shipped). Each of the three **was** argued in writing where it was
added - `app_paths.py`'s module docstring, `ui-v1-research.md` §C4 - so the rule was followed and
only the register drifted. That is the failure worth guarding: the inventory is the one place a
reviewer is told to look, and a dependency absent from it is one nobody will re-examine.

**§7 is whole-product, not core-only.** Ruled 2026-08-01. Its subject is what the user installs,
and that is all three packages' declared runtime dependencies. The table had never carried
`truestill-app`'s, which is why two of the three had been invisible since the app shipped rather
than since a recent change.

**THE DIRECTION IS ONE-WAY, AND THAT IS LOAD-BEARING: declared is a subset of documented.**
Every declared runtime dependency must appear in §7. The converse is deliberately **not**
asserted, because §7 legitimately documents things that are not declared dependencies and never
will be: `scipy` + `pywavelets` are transitive-and-never-imported and are listed precisely so
their ~90 MB is on the record, and `exiftool` is an external binary rather than a pip package.
A two-way check would flag all three as spurious and be switched off within a week - which is
the §4 cry-wolf failure, arriving by way of a "stricter" guard. **Do not make this bidirectional.**

**Reuse, and the one thing not reused.** `_MANIFESTS` and `_WORKSPACE` come from
`test_dependency_floors`, which already owns "which manifests exist" and "which names are
workspace members rather than resolved packages"; duplicating either would give that rule two
homes (§4). Its `_declared_floors` is deliberately *not* reused: it merges `dependency-groups`
into its result, which is right for a floor check and wrong here - it would drag `ruff`, `mypy`,
`pytest` and `playwright` into an inventory of what ships. The runtime-only projection below is
the difference, and it reads `[project].dependencies` alone.

**Measured scope** (`ENGINEERING_STANDARD.md` §4 - scoped against the real file, not a plausible
one):

=========================================  ==========================================
tree state                                 missing from §7
=========================================  ==========================================
before the fix                             **platformdirs, starlette, uvicorn**
after the fix                              **none**
=========================================  ==========================================
"""

from __future__ import annotations

import re
import tomllib

from test_dependency_floors import _MANIFESTS, _ROOT, _WORKSPACE

_CONTRACT = _ROOT / "docs" / "IMPLEMENTATION_STANDARDS.md"

_SECTION_HEAD = "## 7. Dependency inventory"

#: The leading package name of a PEP 508 spec. Enough for the forms these manifests use.
_NAME = re.compile(r"^([A-Za-z0-9._-]+)")


def _inventory_block() -> str:
    """§7's inventory **table** - its rows only, not the whole section.

    Scoped to the table because the first version of this guard was not, and it passed for the
    wrong reason: §7's version-policy note names ``starlette>=0.40`` as an example of a floor
    that had *drifted*, and a whole-section search read that sentence as a row and reported
    `starlette` documented while the table had never carried it. A guard that finds the word
    instead of the row is the §4 hazard of asserting an outcome rather than its provenance.
    """
    lines = _CONTRACT.read_text(encoding="utf-8").splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(_SECTION_HEAD)]
    if len(starts) != 1:
        return ""  # not located; the anti-vacuity assertion turns this into a failure
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(line for line in lines[start:end] if line.startswith("|"))


def _declared_runtime_dependencies() -> dict[str, set[str]]:
    """``{package: {package names of the manifests declaring it}}`` for runtime deps only.

    `[project].dependencies` and nothing else - a dev-group entry is not something the buyer
    installs, and §7 does not claim to cover one.
    """
    found: dict[str, set[str]] = {}
    for manifest in _MANIFESTS:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
        for spec in data.get("project", {}).get("dependencies", []):
            match = _NAME.match(spec.strip())
            if match is None:
                continue
            name = match.group(1).lower().replace("_", "-")
            if name in _WORKSPACE:
                continue  # source, not a resolved package; §7 says so in its own row
            found.setdefault(name, set()).add(manifest.parent.name)
    return found


def _documents(name: str, block: str) -> bool:
    """Is `name` the subject of a row, rather than a substring of one?

    Anchored on the opening backtick and terminated by a version operator or the closing one,
    because a bare containment test lets `pillow-heif` answer for `pillow` - the guard would
    then pass while the row it claims to have found does not exist.
    """
    return re.search(rf"`{re.escape(name)}(?=[`>=<~!])", block) is not None


def test_every_declared_runtime_dependency_is_in_the_contract_inventory() -> None:
    """The rule, one assertion: declared is a subset of documented."""
    declared = _declared_runtime_dependencies()
    block = _inventory_block()

    # Anti-vacuity on both sides: a moved heading or an emptied manifest set would otherwise
    # make this pass by finding nothing to check.
    assert block, f"could not locate exactly one {_SECTION_HEAD!r} heading in {_CONTRACT.name}"
    assert declared, "no runtime dependencies parsed; the manifests moved or the reader is wrong"

    missing = sorted(name for name in declared if not _documents(name, block))
    assert not missing, (
        "§7's dependency inventory does not carry "
        + ", ".join(f"{name} (declared by {', '.join(sorted(declared[name]))})" for name in missing)
        + ".\n\n§7 is where a reviewer is told to check that a dependency earned its place, so "
        "one that is absent is one nobody re-examines. Add a row with the argument against the "
        "stdlib alternative - the argument itself belongs at the site, but the register belongs "
        "here."
    )


def test_the_inventory_check_is_reading_the_real_manifests() -> None:
    """Anti-vacuity from the other side: the well-known runtime deps are actually parsed."""
    declared = _declared_runtime_dependencies()

    assert {"imagehash", "pillow", "pillow-heif", "platformdirs"} <= set(declared)
    assert {"starlette", "uvicorn"} <= set(declared), (
        "the app's runtime deps are not being read; §7 is whole-product, so a reader scoped to "
        "truestill-core would silently check two thirds of the product"
    )
    assert not (set(declared) & _WORKSPACE), "workspace members are source, not resolved packages"
    assert "pytest" not in declared, "a dev-group entry leaked in; §7 covers what ships"


def test_the_row_match_does_not_accept_a_substring() -> None:
    """The guard aimed at itself, and at the one collision this repo actually contains.

    `pillow` is a prefix of `pillow-heif`. A containment test would report `pillow` documented
    by `pillow-heif`'s row, so deleting the real row would not turn this red.
    """
    only_heif = "| `pillow-heif>=1.5.0` (`truestill-core`) | Registers a HEIF opener. |"
    assert _documents("pillow-heif", only_heif)
    assert not _documents("pillow", only_heif), "a prefix answered for a row that is not there"

    real = "| `pillow>=12.3.0` (`truestill-core`) | Image decoding. |"
    assert _documents("pillow", real)
    assert not _documents("uvicorn", real)


def test_only_the_table_counts_not_prose_elsewhere_in_the_section() -> None:
    """The regression for the defect this guard shipped with, and the reason it is table-scoped.

    §7's version-policy note cites ``starlette>=0.40`` as an example of a floor that had drifted.
    That is prose about a mistake, not a row claiming the dependency was justified - and a
    section-wide search accepted it, reporting `starlette` documented while the table had never
    carried it. Pinned so a later "simplification" back to a whole-section read goes red here
    rather than silently restoring the false pass.
    """
    block = _inventory_block()

    assert block, "the table did not resolve"
    assert all(line.startswith("|") for line in block.splitlines()), "prose leaked into the block"
    assert "every test ran on" not in block, "the floors note is being read as inventory rows"
