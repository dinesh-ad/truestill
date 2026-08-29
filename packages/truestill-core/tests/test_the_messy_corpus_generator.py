"""The messy-corpus generator: it cannot escape its root, and its manifest describes reality.

`scripts/make_messy_corpus.py` writes thousands of files derived from a real photo library. Two
properties carry all the risk, and both are asserted here rather than intended:

* **It cannot write outside the corpus root.** A wrong root is the one mistake that cannot be
  undone, and "the source is read-only" is a claim about a path check, so the path check is what
  gets tested - including the spellings that defeat a naive one.
* **The manifest is built from what the generator DID.** Every row's ``sha256`` and ``size`` are
  read back from the file on disk after the write. A manifest generated from the plan would agree
  with itself forever and could never detect the generator misbehaving, which is the only thing it
  exists to do - so the tests below assert on rows whose written bytes DIFFER from their source.

Fixtures are tiny generated JPEGs, never the real library: this file runs in `make check`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

import make_messy_corpus
from make_messy_corpus import CorpusWriter, OutsideCorpusError


def _library(root: Path, count: int = 12) -> Path:
    """A small source library of real JPEGs, one carrying EXIF so the strip shape has a subject."""
    root.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        image = Image.new("RGB", (64, 48), (i * 9 % 256, 60, 120))
        image.save(root / f"IMG_{i:04d}.jpg", "JPEG", quality=92)
    return root


# --- the root is a fence, not an intention -------------------------------------------------


@pytest.mark.parametrize(
    "escape",
    [
        pytest.param("../outside.jpg", id="parent"),
        pytest.param("a/../../outside.jpg", id="parent-through-a-child"),
        pytest.param("/etc/passwd", id="absolute"),
    ],
)
def test_no_write_lands_outside_the_corpus_root(tmp_path: Path, escape: str) -> None:
    """The refusal, in the spellings that defeat a naive check.

    An absolute path is included because `root / "/etc/passwd"` is `/etc/passwd` in pathlib - a
    join that silently discards the root, which reads as safe and is not.
    """
    writer = CorpusWriter(tmp_path / "corpus")

    with pytest.raises(OutsideCorpusError):
        writer.write_bytes(b"x", escape, shape="S0", role="artifact")

    assert not (tmp_path / "outside.jpg").exists()


def test_a_symlinked_escape_is_refused_by_the_resolved_location(tmp_path: Path) -> None:
    """Containment is tested on the REAL location, so a symlink out of the tree cannot widen it."""
    corpus = tmp_path / "corpus"
    writer = CorpusWriter(corpus)
    (tmp_path / "elsewhere").mkdir()
    (corpus / "door").symlink_to(tmp_path / "elsewhere")

    with pytest.raises(OutsideCorpusError):
        writer.write_bytes(b"x", "door/escaped.jpg", shape="S0", role="artifact")

    assert not (tmp_path / "elsewhere" / "escaped.jpg").exists()


def test_the_generator_refuses_an_output_root_inside_the_source(tmp_path: Path) -> None:
    """The whole-run version of the same rule: the corpus may not be built into its own source."""
    source = _library(tmp_path / "library")

    assert make_messy_corpus.main(["--source", str(source), "--out", str(source / "out")]) == 2


def test_a_real_run_leaves_the_source_byte_identical(tmp_path: Path) -> None:
    """The property the fence exists for, asserted end to end rather than argued."""
    source = _library(tmp_path / "library")
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.iterdir())}

    assert (
        make_messy_corpus.main(
            ["--source", str(source), "--out", str(tmp_path / "corpus"), "--files", "8"]
        )
        == 0
    )

    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.iterdir())}
    assert after == before


# --- the manifest describes what happened, not what was planned ----------------------------


def _manifest(root: Path) -> list[dict[str, object]]:
    payload = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = payload["rows"]
    return rows


def test_every_manifest_row_matches_the_file_on_disk(tmp_path: Path) -> None:
    """The instrument check. Read every row back and compare against the bytes it describes.

    ⚠ **This is the test the "manifest from the plan" mutation must fail.** It passes trivially
    for byte-for-byte copies, so the assertions below single out the DERIVED rows - a resize and a
    strip - whose size and hash necessarily differ from their source. A manifest built from
    intentions would carry the source's numbers there and be caught here.
    """
    source = _library(tmp_path / "library")
    corpus = tmp_path / "corpus"
    make_messy_corpus.main(["--source", str(source), "--out", str(corpus), "--files", "8"])

    rows = _manifest(corpus)
    assert rows, "the generator produced no manifest rows"
    for row in rows:
        written = corpus / str(row["path"])
        payload = written.read_bytes()
        assert row["size"] == len(payload), row["path"]
        assert row["sha256"] == hashlib.sha256(payload).hexdigest(), row["path"]

    derived = [r for r in rows if str(r["role"]).startswith("resized-") or r["role"] == "stripped"]
    assert derived, "no derived rows, so this test proves nothing about a plan-shaped manifest"
    for row in derived:
        origin = Path(str(row["source"]))
        assert row["sha256"] != hashlib.sha256(origin.read_bytes()).hexdigest(), row["path"]


def test_a_resized_row_records_its_own_size_not_its_source_s(tmp_path: Path) -> None:
    """The sharpest form of the same guarantee: a downscale is smaller, and the row must say so."""
    source = _library(tmp_path / "library")
    corpus = tmp_path / "corpus"
    make_messy_corpus.main(["--source", str(source), "--out", str(corpus), "--files", "8"])

    resized = [r for r in _manifest(corpus) if r["role"] == "resized-quarter"]
    assert resized
    for row in resized:
        assert int(str(row["size"])) < Path(str(row["source"])).stat().st_size, row["path"]


# --- determinism -----------------------------------------------------------------------------


def test_the_same_seed_builds_the_same_corpus(tmp_path: Path) -> None:
    """Two runs, one seed, identical manifests - what makes a finding citable by seed.

    Mutation proof: break the seed's grip (drop it, or reseed between the sample and the shapes)
    and the two manifests diverge.
    """
    source = _library(tmp_path / "library", 24)
    first, second = tmp_path / "one", tmp_path / "two"

    for out in (first, second):
        make_messy_corpus.main(
            ["--source", str(source), "--out", str(out), "--files", "10", "--seed", "4242"]
        )

    assert _manifest(first) == _manifest(second)


def _sampled_sources(root: Path) -> set[str]:
    return {str(row["source"]) for row in _manifest(root) if row["source"] is not None}


def test_a_different_seed_selects_different_photographs(tmp_path: Path) -> None:
    """Anti-vacuity, and it must assert on the SAMPLE rather than on the whole manifest.

    ⚠ **The first version of this test compared whole manifests and was worthless**: `_s16` calls
    `rng.choice`, so two seeds produce different folder assignments even when they select the
    identical photographs. A mutation replacing the seeded shuffle with a plain sort survived it.
    Asserting on the set of chosen SOURCES is what pins the claim the seed actually makes.
    """
    source = _library(tmp_path / "library", 24)
    first, second = tmp_path / "one", tmp_path / "two"

    make_messy_corpus.main(
        ["--source", str(source), "--out", str(first), "--files", "10", "--seed", "1"]
    )
    make_messy_corpus.main(
        ["--source", str(source), "--out", str(second), "--files", "10", "--seed", "2"]
    )

    assert _sampled_sources(first) != _sampled_sources(second)


# --- the shapes are all present ---------------------------------------------------------------


def test_every_declared_shape_is_emitted(tmp_path: Path) -> None:
    """The corpus is only an instrument if it contains what the design says it contains."""
    source = _library(tmp_path / "library", 24)
    corpus = tmp_path / "corpus"
    make_messy_corpus.main(["--source", str(source), "--out", str(corpus), "--files", "16"])

    shapes = {str(row["shape"]) for row in _manifest(corpus)}
    assert shapes == {f"S{n}" for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16)}


def test_one_photograph_really_does_appear_thirty_five_times(tmp_path: Path) -> None:
    """S2 is the field-reported backup, and the number is the point."""
    source = _library(tmp_path / "library", 24)
    corpus = tmp_path / "corpus"
    make_messy_corpus.main(["--source", str(source), "--out", str(corpus), "--files", "16"])

    rows = [r for r in _manifest(corpus) if r["shape"] == "S2"]
    by_hash: dict[str, int] = {}
    for row in rows:
        by_hash[str(row["sha256"])] = by_hash.get(str(row["sha256"]), 0) + 1
    assert max(by_hash.values()) == make_messy_corpus.MANY_WAY_COPIES


def _case_insensitive(root: Path) -> bool:
    """Ask the filesystem rather than the platform name.

    ``sys.platform`` is a guess about a filesystem: macOS runners are usually case-INsensitive
    APFS and Linux usually ext4, but either can be mounted the other way, and this test's whole
    subject is what the filesystem does. So it is measured here, on the directory the test will
    actually write into.
    """
    probe = root / "CaseProbe"
    probe.write_bytes(b"")
    try:
        return (root / "caseprobe").exists()
    finally:
        probe.unlink()


def test_the_case_collision_collapses_to_one_file(tmp_path: Path) -> None:
    """On a case-insensitive filesystem `IMG_0001.JPG` and `img_0001.jpg` are one file.

    ⚠ **Skips on ext4 with a named reason, and the generator emits S9 anyway.** On a
    case-sensitive filesystem the two names are simply two files and the collision cannot be
    observed at all - so this asserts nothing here rather than pretending to have checked. The
    shape exists in the corpus for the day someone runs it on Windows or APFS: the same lane
    asymmetry `(aif)` was measured by, where the instrument is built before the platform that
    can answer it.
    """
    if not _case_insensitive(tmp_path):
        pytest.skip(
            "this filesystem is case-SENSITIVE, so S9's two names are two files; the shape is "
            "emitted regardless and is observable only on Windows/APFS"
        )
    source = _library(tmp_path / "library", 24)
    corpus = tmp_path / "corpus"
    make_messy_corpus.main(["--source", str(source), "--out", str(corpus), "--files", "16"])

    mixed = sorted((corpus / "DriveA" / "Mixed").iterdir())
    assert len(mixed) == 1


def test_the_corpus_grows_with_the_sample(tmp_path: Path) -> None:
    """`--files` must decide HOW MANY, not only WHICH.

    ⚠ **This is the guard for a defect that shipped.** Every shape used a fixed slice
    (`sample[:20]`), so `--files 2000` built byte-for-byte the same 320-file corpus as
    `--files 60` - measured while building soak eight, after `soak-seven-plan.md` had already
    published a projection ("near 20 GB") that could never have come true. The shares in
    `_SHARE` are proportional now, and this asserts the property rather than the arithmetic.
    """
    source = _library(tmp_path / "library", 60)
    small, large = tmp_path / "small", tmp_path / "large"

    make_messy_corpus.main(["--source", str(source), "--out", str(small), "--files", "12"])
    make_messy_corpus.main(["--source", str(source), "--out", str(large), "--files", "48"])

    assert len(_manifest(large)) > len(_manifest(small)) * 2
