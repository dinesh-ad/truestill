"""The run record is written a line at a time, and the cost is one entry. `(akr)`

⚠ **THE DEFECT WAS A CLIFF, NOT A CURVE.** Format 3 assembled the whole record in memory and
serialised it with one `json.dumps`, at the very end of the run - after every photograph had
already been copied. Measured with `scripts/measure_run_record_memory.py`, one process per point:

    files     RSS peak    serialisation alone
     75,000   223.8 MiB   119.3 MiB
    150,000   399.5 MiB   238.5 MiB
    225,000   574.9 MiB   357.6 MiB
    300,000   750.2 MiB   476.8 MiB

Linear in the file count, and the serialisation figure is roughly **twice** the 238 MiB the record
occupies on disk, because the encoder's `str` and its UTF-8 encoding are both live at the moment
of the write. Streaming: **48.1 MiB RSS and 0.1 MiB traced, flat across all four points.**

**Two of the three cliffs were on the READ side and nobody had named them** - `_supersede` parsed
the whole previous record to recover three header fields, then held it and its gzip image at once.
Both are covered here, because a fix nobody can see fail is a fix nobody can keep.
"""

from __future__ import annotations

import gzip
import json
import tracemalloc
from collections.abc import Iterator
from pathlib import Path

from truestill_core.app_paths import (
    LEGACY_RUN_RECORD_FILENAME,
    record_path_for,
    runs_dir_for,
)
from truestill_core.run_record import (
    FLUSH_EVERY_BYTES,
    LINE_END,
    LINE_FILE,
    LINE_RUN,
    RUN_RECORD_FORMAT,
    RunHeader,
    build_run_record,
    iter_record_entries,
    read_record,
    record_organize,
    write_run_record,
)


def _header(kind: str = "organize") -> RunHeader:
    return RunHeader(kind=kind, source="/src", destination="/dst")


def _entries(count: int) -> Iterator[dict[str, object]]:
    for index in range(count):
        yield {"source": f"/src/{index:06d}.jpg", "status": "uploaded", "detail": ""}


def _record(count: int, *, kind: str = "organize") -> object:
    return build_run_record(
        _header(kind),
        files=_entries(count),
        intended_total=count,
        attempted=count,
        stopped=None,
    )


# --- the streaming property ---------------------------------------------------------------


def test_entries_reach_disk_before_the_iterator_is_exhausted(tmp_path: Path) -> None:
    """**The structural proof of streaming, and it needs no timing and no memory reading.**

    If the writer materialised the entries, the file would still be empty when the generator was
    drained. Instead the generator looks at the file it is being written into, on its own last
    item, and finds earlier entries already there. A test that only measured memory could pass on
    a buffered implementation that happened to fit; this cannot.
    """
    path = tmp_path / "last-run.jsonl"
    seen_mid_stream: list[int] = []
    # Enough entries to cross several flush boundaries whatever the entry size works out at.
    count = (FLUSH_EVERY_BYTES // 64) * 4

    def watching(total: int) -> Iterator[dict[str, object]]:
        for index in range(total):
            if index == total - 1:
                seen_mid_stream.append(path.stat().st_size if path.exists() else 0)
            yield {"source": f"/src/{index:06d}.jpg", "status": "uploaded", "detail": ""}

    record = build_run_record(
        _header(), files=watching(count), intended_total=count, attempted=count, stopped=None
    )
    assert write_run_record(path, record) is None
    assert seen_mid_stream, "the generator was never walked, so this asserts nothing"
    assert seen_mid_stream[0] > 0, (
        "nothing was on disk while the last entry was still being generated, so the writer "
        "buffered the whole record - which is the defect this change removed"
    )


def test_peak_memory_does_not_grow_with_the_number_of_entries(tmp_path: Path) -> None:
    """Ten times the entries must not cost ten times the memory.

    ⚠ **The bar is deliberately loose (under 2x for a 10x input) rather than exact.** An exact
    figure would be a test written in terms of an allocator's behaviour, which drifts with the
    interpreter; what is being pinned is the *shape* - constant, not linear. Format 3 was 4.0x
    across this same pair and would fail this by a wide margin.
    """
    small, large = 2_000, 20_000

    def peak_for(count: int, name: str) -> int:
        tracemalloc.start()
        assert write_run_record(tmp_path / name, _record(count)) is None  # type: ignore[arg-type]
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        return peak

    small_peak = peak_for(small, "small.jsonl")
    large_peak = peak_for(large, "large.jsonl")
    assert large_peak < small_peak * 2, (
        f"{large:,} entries peaked at {large_peak:,} bytes against {small_peak:,} for {small:,} - "
        f"a {large // small}x input must not cost a proportional amount of memory"
    )


# --- the format ----------------------------------------------------------------------------


def test_the_record_is_one_self_contained_object_per_line(tmp_path: Path) -> None:
    """Every line parses alone. This is what makes a torn write cost one line, not the file."""
    path = tmp_path / "r.jsonl"
    assert write_run_record(path, _record(3)) is None  # type: ignore[arg-type]
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [line["type"] for line in lines] == [LINE_RUN, LINE_FILE, LINE_FILE, LINE_FILE, LINE_END]
    assert lines[0]["format"] == RUN_RECORD_FORMAT
    assert lines[0]["run"]["kind"] == "organize"
    # ⚠ The counts are on the TRAILER, never the opening line: they are not true until the last
    # entry is written, and a header asserting them would promise what the run has not yet done.
    assert "attempted" not in lines[0]["run"]
    assert lines[-1]["attempted"] == 3
    assert lines[-1]["entries"] == 3


def test_a_record_with_no_trailer_reads_as_interrupted(tmp_path: Path) -> None:
    """**The behaviour format 3 could not have at all.** A run that died wrote no record; now it
    writes everything it reached and says, by the trailer's absence, that it did not finish."""
    path = tmp_path / "r.jsonl"
    assert write_run_record(path, _record(5)) is None  # type: ignore[arg-type]
    kept = path.read_text(encoding="utf-8").splitlines()[:-1]  # drop the end line
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    loaded = read_record(path)
    assert loaded.interrupted, "a record with no end line reported itself as complete"
    assert loaded.summary is None
    assert len(loaded.entries) == 5, "the entries that did land were lost with the trailer"


def test_a_torn_last_line_costs_that_line_and_nothing_else(tmp_path: Path) -> None:
    """A half-written final line is skipped; every complete line before it survives."""
    path = tmp_path / "r.jsonl"
    assert write_run_record(path, _record(5)) is None  # type: ignore[arg-type]
    text = path.read_text(encoding="utf-8")
    path.write_text(text[: len(text) - 20], encoding="utf-8")  # cut mid-line

    loaded = read_record(path)
    assert loaded.header, "the opening line is the first thing written and must survive"
    assert 3 <= len(loaded.entries) <= 5, (
        f"a torn tail cost more than the line it tore: {len(loaded.entries)} entries left"
    )


def test_an_entry_can_never_shadow_the_line_kind(tmp_path: Path) -> None:
    """``type`` discriminates the line kinds, so an entry carrying one must not displace it.

    ⚠ **This replaced a test that could not fail.** The first version ended in ``or True``, which
    is the vacuity this repo keeps finding - it asserted nothing and passed over any code at all.
    The check that bites is behavioural: hand the writer an entry with a hostile ``type`` and
    require the line to still read as a file entry.
    """
    path = tmp_path / "r.jsonl"
    hostile = [{"source": "/a.jpg", "status": "uploaded", "type": "not-a-line-kind"}]
    record = build_run_record(_header(), files=hostile, intended_total=1, attempted=1, stopped=None)
    assert write_run_record(path, record) is None

    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [line["type"] for line in lines] == [LINE_RUN, LINE_FILE, LINE_END], (
        "an entry's own `type` displaced the discriminator, so its line no longer reads as an entry"
    )
    assert read_record(path).entries[0]["source"] == "/a.jpg", "the entry itself was lost"


# --- the read side: supersession and compression ----------------------------------------


def test_superseding_reads_only_the_opening_line(tmp_path: Path) -> None:
    """The rotated name comes from line one, so a huge record costs one `readline` to file.

    Proven by making every line *after* the first unreadable: if supersession parsed the whole
    document it would fall back to `unknown-run.jsonl`, and the name would say so.
    """
    catalog = tmp_path / "c.sqlite"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    path = record_path_for(catalog)
    assert write_run_record(path, _record(4, kind="organize")) is None  # type: ignore[arg-type]
    head = path.read_text(encoding="utf-8").splitlines()[0]
    path.write_text(head + "\n" + "{ not json at all\n" * 50, encoding="utf-8")

    assert record_organize(catalog, _record(1, kind="backup")) is None  # type: ignore[arg-type]

    demoted = sorted(runs_dir_for(catalog).glob("*organize*"))
    assert demoted, (
        f"the record was not named from its opening line: "
        f"{sorted(p.name for p in runs_dir_for(catalog).iterdir())}"
    )


def test_a_demoted_record_round_trips_through_gzip(tmp_path: Path) -> None:
    """Compression is streamed, and the reader opens a `.gz` transparently."""
    catalog = tmp_path / "c.sqlite"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    assert write_run_record(record_path_for(catalog), _record(6)) is None  # type: ignore[arg-type]
    assert record_organize(catalog, _record(1, kind="backup")) is None  # type: ignore[arg-type]

    demoted = sorted(runs_dir_for(catalog).glob("*organize*.jsonl.gz"))
    assert len(demoted) == 1, f"expected one demoted record, got {demoted}"
    assert gzip.decompress(demoted[0].read_bytes()), "the demoted record is empty"
    assert len(list(iter_record_entries(demoted[0]))) == 6, (
        "a demoted record does not read back through gzip"
    )


def test_a_pre_format_4_record_is_rotated_aside_and_never_parsed(tmp_path: Path) -> None:
    """**`(akr)`'s answer to the old records on disk.** A `last-run.json` from before the change
    is moved into `runs/` under its own mtime - not read, not migrated, not left to sit there
    beside the new name looking current."""
    catalog = tmp_path / "c.sqlite"
    catalog.parent.mkdir(parents=True, exist_ok=True)
    legacy = catalog.parent / LEGACY_RUN_RECORD_FILENAME
    # Deliberately unparseable as JSON Lines: the point is that nothing tries.
    legacy.write_text('{"format": 3, "run": {"kind": "organize"},\n "files": []}', encoding="utf-8")

    assert record_organize(catalog, _record(1, kind="backup")) is None  # type: ignore[arg-type]

    assert not legacy.exists(), "the pre-format-4 record was left beside the new one"
    moved = sorted(runs_dir_for(catalog).glob("*format3*"))
    assert len(moved) == 1, (
        f"the old record was not filed: {sorted(p.name for p in runs_dir_for(catalog).iterdir())}"
    )


def test_the_unflushed_tail_stays_under_our_own_bound(tmp_path: Path) -> None:
    """What a crash can cost is bounded, and the bound is **ours**, not the interpreter's.

    ⚠ **THIS TEST EXISTS BECAUSE THE FIRST VERSION OF THE FLUSH WAS INERT AND A MUTATION SAID SO.**
    It was ``FLUSH_EVERY_ENTRIES = 1000``; deleting the flush outright killed no test, because
    `io.DEFAULT_BUFFER_SIZE` is 131,072 bytes and had already flushed seven times over by entry
    1000. A surviving mutation is a claim about the test *and* about the mutant, and here the
    mutant was right: the constant did nothing.

    ⚠ **Two mechanisms bound this tail and they are not equal** - §4's *where two defences catch
    the same case, assert PROVENANCE*. The interpreter's buffer is a machine state that can change
    release to release; `FLUSH_EVERY_BYTES` is a decision this repo owns. The assertion is against
    ours, which is why the ceiling below is 64 KiB and not 128 KiB.
    """
    path = tmp_path / "r.jsonl"
    lags: list[int] = []
    produced = 0

    def watching(total: int) -> Iterator[dict[str, object]]:
        nonlocal produced
        for index in range(total):
            entry = {"source": f"/src/{index:06d}.jpg", "status": "uploaded", "detail": ""}
            produced += len(json.dumps({**entry, "type": LINE_FILE}, sort_keys=True)) + 1
            on_disk = path.stat().st_size if path.exists() else 0
            lags.append(produced - on_disk)
            yield entry

    count = (FLUSH_EVERY_BYTES // 64) * 4
    record = build_run_record(
        _header(), files=watching(count), intended_total=count, attempted=count, stopped=None
    )
    assert write_run_record(path, record) is None

    assert lags, "nothing was sampled, so this asserts nothing"
    worst = max(lags)
    # One line of slack: the lag is sampled after the line is counted and before it is written.
    ceiling = FLUSH_EVERY_BYTES + 512
    assert worst <= ceiling, (
        f"up to {worst:,} bytes sat unwritten at once, above the {ceiling:,} this writer "
        f"promises - the periodic flush is not bounding the tail"
    )
