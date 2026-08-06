"""What a move left in the source, counted per folder and worded once.

The gap this closes was found by `test_overlapping_organize_runs.py`: a move whose source
overlaps an earlier run reports `organized: 5, duplicates: 3` and leaves those three where they
are. The source is PARTIALLY emptied - which is harder to read than "nothing happened" - and
nothing on either surface says so.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from truestill_core.left_behind import (
    describe_left_behind,
    files_left_in_source,
    will_remain_line,
)
from truestill_core.models import (
    ActionResult,
    ActionStatus,
    CategoryMatch,
    Confidence,
    DateSource,
    Decision,
    DuplicateKind,
    DuplicateMatch,
    DuplicateOrigin,
    FileHashes,
    Resolution,
    RuleName,
)

_CATEGORY = CategoryMatch(
    label="Camera", reason="test", confidence=Confidence.HIGH, rule=RuleName.CAMERA_FILENAME
)


def _result(
    source: Path,
    status: ActionStatus,
    *,
    origin: DuplicateOrigin | str | None = None,
) -> ActionResult:
    match = (
        None
        if origin is None
        else DuplicateMatch(kind=DuplicateKind.EXACT, matched_path="library/x.jpg", origin=origin)
    )
    decision = Decision(
        source=source,
        category=_CATEGORY,
        captured_at=datetime(2021, 1, 1),
        date_source=DateSource.EXIF,
        date_tag=None,
        relative=Path("Camera/2021/01/x.jpg"),
    )
    resolution = Resolution(
        decision=decision,
        hashes=FileHashes(sha256="a" * 64, perceptual=None),
        exact_duplicate=match,
        near_duplicate=None,
    )
    return ActionResult(resolution=resolution, status=status, final_relative=None)


def _write(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    return path


# ------------------------------------------------------------------------------ the fact


def test_a_skipped_duplicate_that_is_still_on_disk_is_counted_in_its_folder(
    tmp_path: Path,
) -> None:
    """The shape the fixtures found: five moved, three left in one subfolder."""
    root = tmp_path / "A"
    left = [_write(root / "D" / "E" / f"IMG_{i}.jpg") for i in range(3)]
    results = [
        *(_result(p, ActionStatus.DUPLICATE, origin=DuplicateOrigin.CATALOG) for p in left),
        *(_result(root / "B" / f"g{i}.jpg", ActionStatus.MOVED) for i in range(5)),
    ]

    behind = files_left_in_source(results, root)

    assert behind is not None
    assert behind.total == 3
    assert behind.already_in_library == 3
    assert [(f.folder, f.files) for f in behind.folders] == [("D/E", 3)]


def test_a_file_that_was_moved_is_not_reported_as_remaining(tmp_path: Path) -> None:
    """CRY-WOLF HALF. A run with nothing left behind must say nothing at all."""
    root = tmp_path / "A"
    results = [_result(root / "B" / f"g{i}.jpg", ActionStatus.MOVED) for i in range(5)]
    assert files_left_in_source(results, root) is None


def test_a_duplicate_whose_source_has_since_gone_is_not_claimed_to_remain(tmp_path: Path) -> None:
    """`remain` is a claim about the disk, so it is read from the disk.

    A DUPLICATE result means `execute` never wrote and never deleted - but "never deleted by
    this run" is not "still there", and the sentence says the second thing.
    """
    root = tmp_path / "A"
    here = _write(root / "D" / "keep.jpg")
    gone = root / "D" / "vanished.jpg"  # never created
    results = [
        _result(here, ActionStatus.DUPLICATE, origin=DuplicateOrigin.CATALOG),
        _result(gone, ActionStatus.DUPLICATE, origin=DuplicateOrigin.CATALOG),
    ]

    behind = files_left_in_source(results, root)

    assert behind is not None
    assert behind.total == 1, "a file that is not there was counted as remaining"


def test_a_failed_file_is_not_folded_into_the_files_that_remain(tmp_path: Path) -> None:
    """FAILED is already counted and named on its own, and it means something else.

    A failure is "this file is not in your library and here is why"; a leftover is "this file
    IS in your library, which is why the original was not touched". Folding them together
    would tell a user their photo may be lost when it is safely stored.
    """
    root = tmp_path / "A"
    _write(root / "broken.jpg")
    results = [_result(root / "broken.jpg", ActionStatus.FAILED)]
    assert files_left_in_source(results, root) is None


def test_the_two_reasons_are_counted_apart(tmp_path: Path) -> None:
    """ "Already in your library" and "matched another file in this batch" are different facts.

    The first says the source copy is redundant; the second says nothing about the library -
    the twin was moved in by this very run.
    """
    root = tmp_path / "A"
    library = _write(root / "old.jpg")
    batch = _write(root / "twin.jpg")
    results = [
        _result(library, ActionStatus.DUPLICATE, origin=DuplicateOrigin.CATALOG),
        _result(batch, ActionStatus.DUPLICATE, origin=DuplicateOrigin.RUN),
    ]

    behind = files_left_in_source(results, root)

    assert behind is not None
    assert (behind.already_in_library, behind.within_this_batch) == (1, 1)
    assert behind.total == 2


def test_an_origin_this_build_does_not_recognise_is_still_counted(tmp_path: Path) -> None:
    """The parts must sum to the whole - the same bargain `split_by_origin` makes."""
    root = tmp_path / "A"
    odd = _write(root / "odd.jpg")
    behind = files_left_in_source(
        [_result(odd, ActionStatus.DUPLICATE, origin="somewhere-else")], root
    )
    assert behind is not None
    assert behind.total == 1
    assert behind.already_in_library + behind.within_this_batch + behind.unclassified == 1


def test_folders_are_ordered_by_how_much_is_in_them(tmp_path: Path) -> None:
    """A user reads the first name. It should be where most of their files are."""
    root = tmp_path / "A"
    files = [_write(root / "small" / "a.jpg")]
    files += [_write(root / "big" / f"b{i}.jpg") for i in range(4)]
    results = [_result(p, ActionStatus.DUPLICATE, origin=DuplicateOrigin.CATALOG) for p in files]

    behind = files_left_in_source(results, root)

    assert behind is not None
    assert [f.folder for f in behind.folders] == ["big", "small"]


def test_a_file_left_in_the_source_root_itself_gets_an_empty_folder_name(tmp_path: Path) -> None:
    """There is no relative name for the root, and inventing one would name a folder that is
    not there. The surfaces word this case; the fact stays empty."""
    root = tmp_path / "A"
    behind = files_left_in_source(
        [
            _result(
                _write(root / "loose.jpg"), ActionStatus.DUPLICATE, origin=DuplicateOrigin.CATALOG
            )
        ],
        root,
    )
    assert behind is not None
    assert [f.folder for f in behind.folders] == [""]


def test_a_long_tail_of_folders_is_capped_and_says_it_was(tmp_path: Path) -> None:
    """Same bargain as `DUPLICATE_SAMPLE_LIMIT`: a truncated list that does not admit it reads
    as a complete one."""
    root = tmp_path / "A"
    results = [
        _result(
            _write(root / f"f{i:03d}" / "x.jpg"),
            ActionStatus.DUPLICATE,
            origin=DuplicateOrigin.CATALOG,
        )
        for i in range(30)
    ]

    behind = files_left_in_source(results, root, folder_limit=5)

    assert behind is not None
    assert len(behind.folders) == 5
    assert behind.folders_total == 30, "the cap hid how many folders there really are"
    assert behind.total == 30, "the cap changed the file count"


def test_a_source_outside_the_root_keeps_its_own_path_rather_than_being_dropped(
    tmp_path: Path,
) -> None:
    """`discover` walks the source, so this should not arise - and if it ever does, dropping
    the file would make the count stop matching the disk."""
    root = tmp_path / "A"
    root.mkdir()
    stray = _write(tmp_path / "elsewhere" / "x.jpg")
    behind = files_left_in_source(
        [_result(stray, ActionStatus.DUPLICATE, origin=DuplicateOrigin.CATALOG)], root
    )
    assert behind is not None
    assert behind.total == 1
    assert behind.folders[0].folder == str(stray.parent)


# ---------------------------------------------------------------------------- the wording


def _behind(tmp_path: Path, layout: dict[str, int], origin: DuplicateOrigin | str) -> object:
    root = tmp_path / "A"
    results = []
    for folder, count in layout.items():
        for i in range(count):
            base = root / folder if folder else root
            results.append(
                _result(_write(base / f"x{i}.jpg"), ActionStatus.DUPLICATE, origin=origin)
            )
    return files_left_in_source(results, root)


def test_one_folder_one_reason_reads_as_the_single_sentence(tmp_path: Path) -> None:
    """The sentence this whole change exists to produce."""
    behind = _behind(tmp_path, {"D/E": 3}, DuplicateOrigin.CATALOG)
    assert describe_left_behind(behind) == [  # type: ignore[arg-type]
        "3 files remain in D/E because they were already in your library."
    ]


def test_one_file_is_grammatical(tmp_path: Path) -> None:
    behind = _behind(tmp_path, {"D/E": 1}, DuplicateOrigin.CATALOG)
    lines = describe_left_behind(behind)  # type: ignore[arg-type]
    assert lines[0].startswith("1 file remains in D/E"), lines


def test_the_source_root_is_named_as_the_folder_the_user_chose(tmp_path: Path) -> None:
    behind = _behind(tmp_path, {"": 2}, DuplicateOrigin.CATALOG)
    assert describe_left_behind(behind) == [  # type: ignore[arg-type]
        "2 files remain in the folder you selected because they were already in your library."
    ]


def test_several_folders_are_named_with_a_count_each(tmp_path: Path) -> None:
    """ "3 files remain" is weaker than "3 files remain in D/E", and the data is there."""
    behind = _behind(tmp_path, {"D/E": 3, "C": 5}, DuplicateOrigin.CATALOG)
    lines = describe_left_behind(behind)  # type: ignore[arg-type]
    assert "C (5)" in lines[0], lines
    assert "D/E (3)" in lines[0], lines
    assert lines[0].startswith("8 files remain"), lines


def test_two_reasons_are_split_onto_their_own_line_rather_than_guessed_at(tmp_path: Path) -> None:
    """With both reasons present, no single "because" clause is true of every file, so the
    sentence stops claiming one and states the split instead."""
    root = tmp_path / "A"
    results = [
        _result(
            _write(root / "D" / "a.jpg"), ActionStatus.DUPLICATE, origin=DuplicateOrigin.CATALOG
        ),
        _result(_write(root / "D" / "b.jpg"), ActionStatus.DUPLICATE, origin=DuplicateOrigin.RUN),
    ]
    lines = describe_left_behind(files_left_in_source(results, root))  # type: ignore[arg-type]
    assert "because" not in lines[0], lines
    joined = " ".join(lines)
    # The counted lines come from `describe_split`, so the phrasing here is the phrasing the
    # duplicate tally already used - one home, no second vocabulary.
    assert "1 already in your library" in joined, lines
    assert "1 matched another file earlier in this batch" in joined, lines


def test_nothing_left_behind_says_nothing() -> None:
    """A zero prints no line - never-silent is about what happened, not what did not."""
    assert describe_left_behind(None) == []


def test_the_truncated_folder_list_says_how_many_it_did_not_name(tmp_path: Path) -> None:
    root = tmp_path / "A"
    results = [
        _result(
            _write(root / f"f{i:03d}" / "x.jpg"),
            ActionStatus.DUPLICATE,
            origin=DuplicateOrigin.CATALOG,
        )
        for i in range(9)
    ]
    lines = describe_left_behind(files_left_in_source(results, root, folder_limit=3))
    assert "6 more folders" in " ".join(lines), lines


def test_one_named_folder_still_admits_the_ones_the_cap_cut(tmp_path: Path) -> None:
    """The bare "in D/E" is only honest when D/E is the whole story."""
    root = tmp_path / "A"
    results = [
        _result(
            _write(root / f"f{i}" / "x.jpg"), ActionStatus.DUPLICATE, origin=DuplicateOrigin.CATALOG
        )
        for i in range(3)
    ]
    lines = describe_left_behind(files_left_in_source(results, root, folder_limit=1))
    assert "2 more folders" in lines[0], lines


# ------------------------------------------------------------------- the preview sentence


def test_the_preview_line_says_the_files_will_not_be_moved() -> None:
    line = will_remain_line(5)
    assert line is not None
    assert "5" in line, line
    assert "already in your library" in line, line
    assert "not be moved" in line, line


def test_the_preview_line_is_grammatical_for_one_file() -> None:
    assert will_remain_line(1) == (
        "1 file here is already in your library and will not be moved. It stays where it is."
    )


def test_the_preview_line_is_absent_when_nothing_is_already_in_the_library() -> None:
    assert will_remain_line(0) is None
