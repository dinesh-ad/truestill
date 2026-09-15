"""Every inline `<svg>` in the template is accounted for by `static/LICENSE-icons.txt`.

⚠ **AN UNLICENSED ICON INSIDE A SHIPPED BUNDLE IS EXPOSURE, NOT UNTIDINESS**, and the notice has
drifted twice in three days - both times by an icon landing with no row:

* **2026-09-13** - three `.bak-job-badge` glyphs arrived on Backups. The notice gained a section
  and kept a bare literal saying the count command *"answers 12"*; the real answer was 15.
* **2026-09-14** - `9eca455` added a fourth job badge (`restore`) with the restore card and did
  not touch the notice at all. The real answer became 16 while the file still said 12, and its own
  newest section still said THREE job badges while four shipped.

**Nothing could have caught either**: a licence notice is prose, and `IMPLEMENTATION_STANDARDS.md`
§6.2's own finding is that no other gate here can see prose. `ruff`, `mypy` and the suite were
green through both.

§4's seventy-second member is the shape: **loop the DERIVED inventory, assert into the
DECLARATION.** The template is the inventory - parsed, never hand-listed - and the notice's census
table is the declaration. A guard that listed the icons itself would be a third copy, and a third
copy is the thing this exists to prevent.

⚠ **The classification lives here and the COUNTS live in the notice**, deliberately. Marker to
group name is this guard's logic; how many ship under each marker is the claim the notice makes to
a reader. A badge added in a *new* wrapper class therefore matches no group and fails loudly,
rather than being quietly absorbed into an existing row.
"""

from __future__ import annotations

import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / "packages/truestill-app/src/truestill_app/templates/index.html"
NOTICE = ROOT / "packages/truestill-app/src/truestill_app/static/LICENSE-icons.txt"

#: HTML void elements never get an end tag, so they must not be pushed onto the ancestor stack.
#: `<path/>`-style self-closing tags need no entry: `handle_startendtag` balances them itself.
_VOID = frozenset(
    [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]
)

#: Enclosing `class` token -> the group name the notice declares.
_BY_ANCESTOR_CLASS = {
    "mode-badge": "organize mode badges",
    "bak-job-badge": "backups job badges",
}

#: The key an `<svg>` gets when nothing recognises it - deliberately a name no census row uses,
#: so it also fails the count comparison rather than only the classification one.
_UNCLASSIFIED = "(no group)"

_TOTAL_ROW = "total"


class _IconCensus(HTMLParser):
    """Collects one row per `<svg>` start tag, with the wrapper classes enclosing it."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ancestors: list[tuple[str, frozenset[str]]] = []
        self.found: list[tuple[frozenset[str], frozenset[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: (value or "") for key, value in attrs}
        classes = frozenset(attr.get("class", "").split())
        if tag == "svg":
            own = frozenset(key for key in attr if key.startswith("data-")) | classes
            enclosing = frozenset().union(*(c for _, c in self._ancestors), frozenset())
            self.found.append((own, enclosing))
        if tag not in _VOID:
            self._ancestors.append((tag, classes))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._ancestors) - 1, -1, -1):
            if self._ancestors[index][0] == tag:
                del self._ancestors[index:]
                return


def _groups_for(own: frozenset[str], enclosing: frozenset[str]) -> frozenset[str]:
    """Every group this `<svg>` matches. Pure: one match is the healthy case, and the tests
    below are what insist on it - zero means unlicensed, more than one means the markers
    stopped being disjoint and the census can no longer count each icon exactly once."""
    matched = {group for token, group in _BY_ANCESTOR_CLASS.items() if token in enclosing}
    if any(marker.startswith("data-brand") for marker in own):
        matched.add("brand mark")
    if "ico" in own:
        matched.add("nav icons")
    return frozenset(matched)


def _shipped() -> list[tuple[frozenset[str], frozenset[str], frozenset[str]]]:
    parser = _IconCensus()
    parser.feed(TEMPLATE.read_text(encoding="utf-8"))
    parser.close()
    return [(_groups_for(own, enc), own, enc) for own, enc in parser.found]


def _counts() -> dict[str, int]:
    """Derived counts keyed by group. An anomalous `<svg>` gets a key no row declares, so it
    fails the count comparison too rather than relying on one test alone."""
    keys = []
    for groups, _, _ in _shipped():
        keys.append("+".join(sorted(groups)) if groups else _UNCLASSIFIED)
    return dict(Counter(keys))


#: A census row: two spaces of indent, then columns separated by two or more spaces.
_ROW = re.compile(r"^ {2}(?P<group>\S.*?) {2,}(?P<rest>\S.*)$")
_INTEGER = re.compile(r"(?<![\w.-])(\d+)(?![\w.-])")


def _declared() -> dict[str, int]:
    """The census table in the notice, as `{group: count}` - the `total` row included."""
    text = NOTICE.read_text(encoding="utf-8")
    start = text.find("THE CENSUS")
    assert start != -1, (
        f"{NOTICE.name} no longer has a 'THE CENSUS' section. If it was renamed, rename it here "
        f"too; if it was deleted, this guard has no declaration to assert into and must be "
        f"deleted with it rather than left green over nothing."
    )
    declared: dict[str, int] = {}
    for paragraph in text[start:].split("\n\n"):
        for line in paragraph.splitlines():
            match = _ROW.match(line)
            if match is None:
                continue
            group = match.group("group").strip()
            if group in {"group", "badge"} or set(group) <= {"-"}:
                continue
            counts = _INTEGER.findall(match.group("rest"))
            if counts and group not in declared:
                declared[group] = int(counts[0])
        if declared:
            break  # the first table under the heading is the census; later ones are per-badge
    return declared


def test_the_template_is_actually_parsed() -> None:
    """Non-emptiness first: a parse that found nothing would satisfy every equality below.

    §4 - *a guard must prove its subject is non-empty before it proves anything about it.* Proven
    rather than asserted: blinding `handle_starttag` to `svg` leaves
    `test_every_shipped_svg_falls_into_exactly_one_group` **passing** over an empty inventory, and
    only this test fails. That mutation pair is the reason this test exists.
    """
    shipped = _shipped()
    assert len(shipped) >= 10, (
        f"only {len(shipped)} <svg> elements parsed out of {TEMPLATE.name}; the template's shape "
        f"changed or the parser stopped seeing them. Nothing below means anything until they agree."
    )
    raw = TEMPLATE.read_text(encoding="utf-8").count("<svg")
    assert len(shipped) == raw, (
        f"the parser found {len(shipped)} <svg> elements and a plain text count finds {raw}. "
        f"One of them is wrong, and the census cannot be trusted until they agree."
    )


def test_the_notice_declares_a_census_at_all() -> None:
    """The declaration half, proven non-empty for the same reason as the inventory half."""
    declared = _declared()
    assert len(declared) >= 3, (
        f"parsed only {declared} out of {NOTICE.name}'s census table. A declaration this small "
        f"means the table's shape changed, and every comparison below is then vacuous."
    )
    assert _TOTAL_ROW in declared, f"the census table has no '{_TOTAL_ROW}' row: {declared}"


def test_every_shipped_svg_falls_into_exactly_one_group() -> None:
    """The 2026-09-14 failure: a badge in a wrapper nothing recognises must not be silent.

    Both directions are one question - an `<svg>` the census can count exactly once. Zero matches
    is an icon nobody licensed; two matches means the markers overlap, so some icon is counted
    twice and another row is short by one.
    """
    unmatched = [(sorted(o), sorted(e)) for g, o, e in _shipped() if not g]
    ambiguous = [(sorted(g), sorted(o)) for g, o, _ in _shipped() if len(g) > 1]
    assert not unmatched, (
        f"{len(unmatched)} <svg> element(s) in {TEMPLATE.name} match no group this guard knows: "
        f"{unmatched}. An icon nobody classified is an icon nobody licensed - add its marker to "
        f"_BY_ANCESTOR_CLASS and give it a row in {NOTICE.name}."
    )
    assert not ambiguous, (
        f"{len(ambiguous)} <svg> element(s) match several groups at once: {ambiguous}. The "
        f"markers stopped being disjoint, so the census counts some icon twice."
    )


def test_each_group_ships_the_number_the_notice_declares() -> None:
    """The count half. This is the assertion that was false from 2026-09-13 to 2026-09-15."""
    shipped = _counts()
    declared = {k: v for k, v in _declared().items() if k != _TOTAL_ROW}
    assert shipped == declared, (
        f"the template ships {shipped} and {NOTICE.name}'s census declares {declared}. Every icon "
        f"that ships needs a row that covers it, and a row for icons that no longer ship is a "
        f"licence claim about nothing."
    )


def test_the_total_row_is_the_sum_of_the_groups() -> None:
    """A per-group table whose total disagrees is the same drift one level up, so pin both."""
    declared = _declared()
    groups = {k: v for k, v in declared.items() if k != _TOTAL_ROW}
    assert declared[_TOTAL_ROW] == sum(groups.values()), (
        f"the census totals {declared[_TOTAL_ROW]} and its rows sum to {sum(groups.values())} "
        f"({groups}). The notice read '12' for three days while its own rows said otherwise."
    )
