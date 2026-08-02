"""Repointing `files.source_path` after its folder moved (`BACKLOG.md` ``(yy)``).

**Scope is the point.** Organized drive trees need no repair - they are drive-relative under a
marker uuid and verify clean after a remount. What breaks is `files.source_path`, which is
absolute and records where a file came from.

**Why the proof is load-bearing.** `reclaim` deletes `files.source_path`, and its gate re-hashes
the *destination copy on the drive* - it never hashes the source (`plan_reclaim` only checks the
source exists). A path rewritten to the wrong tree would therefore have reclaim delete a file it
never verified at all. Everything here refuses rather than guesses.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from truestill_core.drive_adoption import AdoptionVerdict
from truestill_core.source_repoint import plan_repoint

#: Enough files that the sampler has something to spread across.
_NAMES = [f"trip/day{i // 4}/IMG_{i:03d}.jpg" for i in range(24)]


def _tree(root: Path, names: list[str], *, content: str = "photo") -> dict[str, str]:
    """Build a source tree; return ``{relative: digest}`` under a hasher that echoes bytes."""
    digests = {}
    for name in names:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"{content}:{name}")
        digests[name] = f"{content}:{name}"
    return digests


def _recorded(root: Path, digests: dict[str, str]) -> list[tuple[str, str]]:
    """``(source_path, sha256)`` as `Catalog.seed_rows` would give it."""
    return [(str(root / name), digest) for name, digest in digests.items()]


def _echo(path: Path) -> str:
    return path.read_text()


def test_a_moved_root_is_recognised_and_every_descendant_repoints(tmp_path: Path) -> None:
    """The cascade: one root named, every recorded path beneath it rewritten.

    Fixing a library one file at a time is the wrong unit - that is the whole reason this takes
    a root rather than a path.
    """
    old, new = tmp_path / "old", tmp_path / "new"
    digests = _tree(old, _NAMES)
    recorded = _recorded(old, digests)
    shutil.move(str(old), str(new))

    plan = plan_repoint(recorded, old, new, hasher=_echo)

    assert plan.verdict is AdoptionVerdict.PROVEN
    assert len(plan.rows) == len(_NAMES)
    assert len(plan.movable) == len(_NAMES), "one repoint must fix all descendants"
    assert plan.may_apply
    moved = {r.new_path for r in plan.movable}
    assert str(new / "trip/day0/IMG_000.jpg") in moved
    assert str(new / "trip/day5/IMG_023.jpg") in moved


def test_an_intact_root_is_not_offered_a_repair(tmp_path: Path) -> None:
    """Cry-wolf half. Nothing moved, so there is nothing to repoint."""
    old = tmp_path / "old"
    digests = _tree(old, _NAMES)

    plan = plan_repoint(_recorded(old, digests), old, old, hasher=_echo)

    assert plan.still_present_at_old == len(_NAMES), (
        "every recorded source is where it always was; a caller must be able to see that"
    )


def test_an_unrelated_tree_is_refused(tmp_path: Path) -> None:
    """The failure to design against: a confident rewrite onto content nobody recorded."""
    old, other = tmp_path / "old", tmp_path / "other"
    digests = _tree(old, _NAMES)
    _tree(other, ["holiday/DSC_9000.jpg", "holiday/DSC_9001.jpg"])

    plan = plan_repoint(_recorded(old, digests), old, other, hasher=_echo)

    assert plan.verdict is AdoptionVerdict.NO_MATCH
    assert not plan.may_apply
    assert plan.movable == []


def test_matching_layout_with_different_content_is_refused(tmp_path: Path) -> None:
    """Same folder shape, different photos - a second import organized the same way.

    Paths lining up is not proof, and this is exactly where reclaim would delete the wrong file.
    """
    old, decoy = tmp_path / "old", tmp_path / "decoy"
    digests = _tree(old, _NAMES)
    _tree(decoy, _NAMES, content="a-completely-different-photo")

    plan = plan_repoint(_recorded(old, digests), old, decoy, hasher=_echo)

    assert plan.verdict is AdoptionVerdict.CONTENT_DIFFERS
    assert not plan.may_apply, "every path resolves; not one of them holds the recorded content"
    assert plan.proven == 0


def test_a_row_absent_from_the_new_root_is_left_where_it_was(tmp_path: Path) -> None:
    """A dead path is honest; a confidently wrong one is what reclaim deletes."""
    old, new = tmp_path / "old", tmp_path / "new"
    digests = _tree(old, _NAMES)
    recorded = _recorded(old, digests)
    shutil.move(str(old), str(new))
    (new / "trip/day0/IMG_001.jpg").unlink()

    plan = plan_repoint(recorded, old, new, hasher=_echo)

    assert plan.verdict is AdoptionVerdict.PROVEN
    assert len(plan.movable) == len(_NAMES) - 1
    assert all("IMG_001.jpg" not in r.new_path for r in plan.movable)


def test_rows_outside_the_named_root_are_untouched(tmp_path: Path) -> None:
    """A catalog holds imports from many folders; a repoint is about exactly one of them."""
    old, new, elsewhere = tmp_path / "old", tmp_path / "new", tmp_path / "elsewhere"
    digests = _tree(old, _NAMES)
    other = _tree(elsewhere, ["misc/A.jpg", "misc/B.jpg"])
    recorded = _recorded(old, digests) + _recorded(elsewhere, other)
    shutil.move(str(old), str(new))

    plan = plan_repoint(recorded, old, new, hasher=_echo)

    assert len(plan.rows) == len(_NAMES), "only rows under the named root are in the plan"
    assert all(str(elsewhere) not in r.old_path for r in plan.rows)


def test_a_sibling_root_sharing_a_name_prefix_is_not_swept_in(tmp_path: Path) -> None:
    """`/photos-old` is not under `/photos`, and a string prefix test would say it is.

    Comparison goes through `PurePath`, which is also what makes this correct on Windows.
    """
    root = tmp_path / "photos"
    sibling = tmp_path / "photos-old"
    digests = _tree(root, ["a.jpg"])
    extra = _tree(sibling, ["b.jpg"])
    recorded = _recorded(root, digests) + _recorded(sibling, extra)

    plan = plan_repoint(recorded, root, tmp_path / "moved", hasher=_echo)

    assert [r.old_path for r in plan.rows] == [str(root / "a.jpg")]


def test_an_empty_selection_is_not_a_proven_repoint(tmp_path: Path) -> None:
    """Anti-vacuity: nothing recorded under the root must not read as a successful match."""
    new = tmp_path / "new"
    new.mkdir()

    plan = plan_repoint([], tmp_path / "never-used", new, hasher=_echo)

    assert plan.rows == []
    assert plan.verdict is AdoptionVerdict.NO_MATCH
    assert not plan.may_apply
