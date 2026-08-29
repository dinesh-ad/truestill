#!/usr/bin/env python3
"""Manufacture the mess a real user has, from real photographs, deterministically.

**Why this exists.** Ad's library is realistic in scale and format and **not** in mess: measured
2026-08-29, the personal material is 7,527 files of which 7,436 (98.8%) are ``.jpg``, with 54
duplicate basenames in the whole tree, and soak five put the duplication rate at 35 exact
duplicates in 10,745 files. Six soaks varied *what the product was asked to do* - scale, refusal,
deletion, reversal - while holding *the shape of the input* constant at one clean tree from one
person's devices. The field evidence says the real user's library is nothing like that. This
builds the other axis. ``docs/soak-seven-plan.md`` carries the shape table, the field evidence
each shape comes from, and the prediction written before the first run.

**The corpus is derived, never invented**: every photograph here is a copy or a transform of a
real file, so the EXIF lineage, the burst structure and the date distribution are real. Only the
*arrangement* is manufactured.

⚠ **THE SOURCE IS READ-ONLY AND THAT IS ENFORCED, NOT INTENDED.** This writes thousands of files
derived from a real library, and a wrong output root is the one mistake that cannot be undone.
:class:`CorpusWriter` owns the only path that reaches ``open(..., "wb")``, resolves every target
under its root, and raises :class:`OutsideCorpusError` on anything that escapes - including a
symlinked root, an absolute path and ``..`` traversal. Pinned by
``test_the_messy_corpus_generator.py``, which asserts the refusal rather than trusting the
intention.

**The manifest is the instrument, so it is built from what happened.** Every row is written by
the writer *after* the bytes land, from the file on disk - the real path, the real size, the real
SHA-256 - never from the plan that asked for it. A manifest generated from intentions cannot
detect the generator misbehaving, which is the one thing it exists to do.

**Determinism.** One ``--seed`` decides every sample and every shuffle; two runs with the same
seed produce the same manifest. Findings are then citable by (seed, source, commit) rather than
by the day the tree happened to be built.

⚠ **Two tiers of reproducibility, and the manifest records which one each row came from.**
``CLAUDE.md`` rules that the two format repos are *"version-controlled and reproducible anywhere,
so a finding against them is citable by commit"*, while any observation of ``TruestillLibrary`` is
*"a SNAPSHOT - never a fixture, never a design premise"*. A finding against a row whose source is
a format repo is reproducible by anyone; one against a personal-photo row is reproducible only on
this machine.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import random
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

from PIL import Image

#: What counts as a photograph worth copying. Videos are excluded on purpose: every shape here is
#: about image identity (perceptual hashing, EXIF, resizes), and a 900 MB video would dominate the
#: corpus size while exercising none of it.
IMAGE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff"}
)

#: The default output root. Never ``/tmp`` - that is tmpfs, i.e. RAM, and this tree is tens of
#: gigabytes (``suite_scratch.py``'s recorded decision, reaching one layer further).
DEFAULT_OUT: Final[Path] = Path("/data/tmp/truestill/messy")

#: How many times one photograph is copied for the many-way shape. From the field report of a
#: backup in which a single file appeared this many times.
MANY_WAY_COPIES: Final[int] = 35


class OutsideCorpusError(RuntimeError):
    """A write was attempted outside the corpus root. Always fatal, never caught here."""


@dataclass(frozen=True, slots=True)
class ManifestRow:
    """One file this generator actually produced, described from the bytes on disk.

    ``source`` is what it is a copy of, as given to the writer; ``sha256`` and ``size`` are read
    back from the written file, so a row can disagree with the plan and that disagreement is
    exactly what the manifest is for.
    """

    path: str
    shape: str
    role: str
    source: str | None
    sha256: str
    size: int


class CorpusWriter:
    """The only thing that writes, and it cannot write outside its root.

    Every shape below goes through :meth:`copy` or :meth:`write_bytes`; neither opens a path it
    has not resolved against :attr:`root` first. The root itself is resolved once, so a symlink
    cannot widen it later.
    """

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._rows: list[ManifestRow] = []

    def _target(self, relative: str) -> Path:
        """Resolve ``relative`` under the root, or refuse.

        ``Path.resolve`` collapses ``..`` and follows symlinks, and ``is_relative_to`` is then a
        containment test on the real location rather than on the spelling. An absolute
        ``relative`` fails the same way: ``root / "/etc/passwd"`` is ``/etc/passwd`` in pathlib.
        """
        candidate = (self.root / relative).resolve()
        if candidate != self.root and not candidate.is_relative_to(self.root):
            message = f"refusing to write outside the corpus root: {candidate}"
            raise OutsideCorpusError(message)
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    def _record(
        self, target: Path, relative: str, shape: str, role: str, source: Path | None
    ) -> None:
        """Describe what is ON DISK. Called only after the bytes have landed."""
        payload = target.read_bytes()
        self._rows.append(
            ManifestRow(
                path=relative,
                shape=shape,
                role=role,
                source=None if source is None else str(source),
                sha256=hashlib.sha256(payload).hexdigest(),
                size=len(payload),
            )
        )

    def copy(self, source: Path, relative: str, *, shape: str, role: str = "copy") -> Path:
        """Byte-for-byte copy. The source is only ever read."""
        target = self._target(relative)
        target.write_bytes(source.read_bytes())
        self._record(target, relative, shape, role, source)
        return target

    def write_bytes(
        self, payload: bytes, relative: str, *, shape: str, role: str, source: Path | None = None
    ) -> Path:
        """A derived file - a resize, a strip, a truncation, an artifact."""
        target = self._target(relative)
        target.write_bytes(payload)
        self._record(target, relative, shape, role, source)
        return target

    @property
    def rows(self) -> list[ManifestRow]:
        return list(self._rows)

    def write_manifest(self, relative: str = "manifest.json") -> Path:
        """The instrument itself. Written last, from the rows the writes produced."""
        target = self._target(relative)
        payload = {
            "files": len(self._rows),
            "shapes": sorted({row.shape for row in self._rows}),
            "rows": [asdict(row) for row in self._rows],
        }
        target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return target


def _decodable(path: Path) -> bool:
    """Whether Pillow can actually read this image.

    ⚠ **Not defensive padding: the source library really does contain undecodable files.**
    `metadata-extractor-images` carries **1,461 deliberately fuzzed** ones, and a sample that
    happened to draw one killed the first real run at the re-encode. The derived shapes (strip,
    resize, rotate) all decode their subject, so the sample must be drawn from what decodes -
    filtering here rather than at each shape keeps one rule in one place.

    ⚠ **`Exception` is deliberate here, and it is the narrow reading rather than the lazy one.**
    The question this function asks is *"can Pillow read this file"*, so **every** failure is a
    ``False`` - the answer does not depend on which exception a malformed file happens to
    produce. A named tuple was tried first and was wrong twice against the real fuzzed corpus:
    ``(OSError, ValueError, SyntaxError)`` missed an ``IndexError`` raised from inside
    ``PngImagePlugin.verify`` on a truncated tile list. Enumerating what a fuzzer can provoke
    from a decoder is not a list anyone can finish, which is the argument for the boundary
    rather than for the names.

    ⚠ **It DECODES rather than calling ``verify()``, and that distinction cost a run.**
    ``Image.verify()`` checks structure without decoding pixels, so it answers a different
    question from the one the shapes ask: a fuzzed TIFF passed ``verify()`` and then raised
    ``OSError: decoder error -2`` from ``convert("RGB")`` half way through a 2,000-file build.
    The derived shapes decode their subject, so the filter must decode too - the check has to be
    the work, not a cheaper proxy for it.
    """
    try:
        with Image.open(path) as image:
            image.convert("RGB").load()
    except Exception:  # any failure IS the answer - see the docstring
        return False
    return True


def sample_images(source: Path, count: int, rng: random.Random) -> list[Path]:
    """A deterministic sample of real, decodable photographs.

    ``rglob`` order is filesystem order and differs between machines, so the sort is what makes
    the seed mean anything. The candidate list is **shuffled and then filtered**, rather than
    filtered and then sampled, so that verifying decodability costs one ``Image.open`` per file
    taken instead of one per file in a 20,000-file library.
    """
    everything = sorted(
        path
        for path in source.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not everything:
        message = f"no images under {source}; this generator has no subject"
        raise SystemExit(message)
    rng.shuffle(everything)
    chosen = _take_decodable(everything, count)
    if len(chosen) < count:
        message = f"only {len(chosen)} decodable images under {source}; wanted {count}"
        raise SystemExit(message)
    return chosen


def _take_decodable(candidates: Sequence[Path], count: int) -> list[Path]:
    taken: list[Path] = []
    for path in candidates:
        if _decodable(path):
            taken.append(path)
        if len(taken) == count:
            break
    return taken


#: What fraction of the sample each shape draws. ⚠ **Slices used to be FIXED (`sample[:20]`), so
#: `--files` chose WHICH photographs and never HOW MANY** - a corpus built with `--files 2000` was
#: byte-for-byte the one built with `--files 60`, 320 files either way, and `soak-seven-plan.md`
#: carried a projection ("near 20 GB") that could never have come true. Measured and fixed
#: 2026-08-29 during soak eight's build. Fractions rather than counts so the shape MIX is
#: preserved at any scale: these are the proportions the 60-file corpus actually had.
_SHARE: Final[dict[str, float]] = {
    "S1": 1 / 3,
    "S3": 1 / 4,
    "S4": 1 / 5,
    "S5": 1 / 6,
    "S6": 2 / 15,
    "S7": 1 / 6,
    "S8": 1 / 10,
    "S15": 1 / 12,
    "S16": 1 / 4,
    "S2t": 2 / 15,
}


def _share(sample: Sequence[Path], shape: str) -> Sequence[Path]:
    """The slice of the sample this shape draws, proportional to the sample rather than fixed."""
    return sample[: max(1, int(len(sample) * _SHARE[shape]))]


def _reencode(
    source: Path, *, scale: float = 1.0, strip_exif: bool = False, rotate: int = 0
) -> bytes:
    """Re-save a photograph through Pillow, optionally scaled, stripped or rotated.

    Pillow drops EXIF unless it is handed back explicitly, so ``strip_exif`` is the *absence* of
    that hand-back rather than an erasing step - which is exactly how a web export loses it.
    """
    with Image.open(source) as image:
        frame = image.convert("RGB")
        if scale != 1.0:
            size = (max(1, int(frame.width * scale)), max(1, int(frame.height * scale)))
            frame = frame.resize(size)
        if rotate:
            frame = frame.rotate(rotate, expand=True)
        buffer = io.BytesIO()
        exif = image.info.get("exif")
        if exif is not None and not strip_exif:
            frame.save(buffer, "JPEG", quality=90, exif=exif)
        else:
            frame.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def build(writer: CorpusWriter, sample: Sequence[Path], rng: random.Random) -> None:
    """Emit every shape. Each helper is small so the shape list reads as the design does."""
    _s1_same_photo_different_names(writer, sample)
    _s2_one_photo_many_times(writer, sample)
    _s3_exif_stripped(writer, sample)
    _s4_resolutions(writer, sample)
    _s5_backup_of_a_backup(writer, sample)
    _s6_crash_rescue(writer, sample)
    _s7_picasa_beside_phone(writer, sample)
    _s8_second_root(writer, sample)
    _s9_case_collision(writer, sample)
    _s11_windows_artifacts(writer)
    _s12_zero_byte_and_truncated(writer, sample)
    _s13_deep_nesting(writer, sample)
    _s14_orphan_sidecar(writer)
    _s15_rotated(writer, sample)
    _s16_migration_folders(writer, sample, rng)


def _s1_same_photo_different_names(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """One photograph, three trees, three names. `"the same file name, but not always"`."""
    for i, source in enumerate(_share(sample, "S1")):
        writer.copy(source, f"DriveA/Pictures/{source.name}", shape="S1", role="original")
        writer.copy(source, f"DriveB/My Pictures/photo ({i + 1}){source.suffix}", shape="S1")
        writer.copy(
            source, f"DriveC/Copy of Pictures/{source.stem}_copy{source.suffix}", shape="S1"
        )


def _s2_one_photo_many_times(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """The measured backup in which one file appeared 35 times, plus a realistic tail."""
    hero = sample[0]
    for i in range(MANY_WAY_COPIES):
        writer.copy(
            hero, f"DriveB/Backups/set{i // 7:02d}/{hero.stem}_{i:02d}{hero.suffix}", shape="S2"
        )
    for tail, source in enumerate(_share(sample, "S2t")[1:], start=2):
        for i in range(tail % 5 + 2):
            writer.copy(
                source, f"DriveB/Backups/tail/{source.stem}_{tail}_{i}{source.suffix}", shape="S2"
            )


def _s3_exif_stripped(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """The highest-value bet: a stripped copy beside its dated original.

    The prediction is in ``docs/soak-seven-plan.md`` - the original dates from EXIF and the twin
    falls to ``FILENAME`` or ``Undated/``, while the perceptual tier pairs them at distance 0.
    """
    for i, source in enumerate(_share(sample, "S3")):
        writer.copy(source, f"DriveA/Originals/{source.name}", shape="S3", role="original")
        writer.write_bytes(
            _reencode(source, strip_exif=True),
            f"DriveC/WhatsApp Images/IMG-20190712-WA{i:04d}.jpg",
            shape="S3",
            role="stripped",
            source=source,
        )


def _s4_resolutions(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """The same photograph at several sizes. dHash normalises to 9x8, so these SHOULD pair."""
    for source in _share(sample, "S4"):
        writer.copy(source, f"DriveA/Full/{source.name}", shape="S4", role="original")
        for label, scale in (("half", 0.5), ("quarter", 0.25), ("web", 0.15)):
            writer.write_bytes(
                _reencode(source, scale=scale),
                f"DriveC/Exports/{label}/{source.stem}_{label}.jpg",
                shape="S4",
                role=f"resized-{label}",
                source=source,
            )


def _s5_backup_of_a_backup(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """`"75 GB of source became 220 GB of backup"` - the same tree nested inside itself."""
    for source in _share(sample, "S5"):
        writer.copy(source, f"DriveD/Backup/Pictures/{source.name}", shape="S5", role="original")
        writer.copy(source, f"DriveD/Backup/OldPC/Backup/Pictures/{source.name}", shape="S5")
        writer.copy(
            source, f"DriveD/Backup/OldPC/Backup/OldPC/Backup/Pictures/{source.name}", shape="S5"
        )


def _s6_crash_rescue(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """Real recovery-tool artifacts: Windows chkdsk and PhotoRec, not invented names."""
    for i, source in enumerate(_share(sample, "S6")):
        writer.copy(source, f"DriveE/FOUND.000/FILE{i:04d}.CHK", shape="S6")
        writer.copy(source, f"DriveE/recup_dir.1/f{i * 1117:07d}.jpg", shape="S6")


def _s7_picasa_beside_phone(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """A Picasa-era album beside an untouched phone dump - two conventions, one library."""
    for i, source in enumerate(_share(sample, "S7")):
        writer.copy(source, f"DriveA/Picasa/Album 2009/Scan{i + 1:03d}.jpg", shape="S7")
        writer.copy(source, f"DriveF/DCIM/100ANDRO/IMG_2019{i:04d}.jpg", shape="S7")
    writer.write_bytes(
        b"[Picasa]\nname=Album 2009\ntoken=\n",
        "DriveA/Picasa/Album 2009/.picasa.ini",
        shape="S7",
        role="artifact",
    )


def _s8_second_root(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """`"eight hard drives"`. Every soak used ONE source root; the roots above are the shape."""
    for source in _share(sample, "S8"):
        writer.copy(source, f"DriveG/Photos/{source.name}", shape="S8")
        writer.copy(source, f"DriveH/Pictures/{source.name}", shape="S8")


def _s9_case_collision(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """``IMG.JPG`` beside ``img.jpg``.

    ⚠ **Invisible on ext4 and emitted anyway.** On a case-sensitive filesystem these are two
    files; on Windows (NTFS) and on default APFS the second overwrites the first, so the shape
    only *means* something on the platform this product launches on. The generator emits it
    unconditionally so the corpus is complete the day someone runs it there, and the assertion
    skips on ext4 with a named reason rather than pretending to have checked. Same lane asymmetry
    `(aif)` was measured by: the instrument exists before the platform does.
    """
    source = sample[0]
    writer.copy(source, "DriveA/Mixed/IMG_0001.JPG", shape="S9")
    writer.copy(source, "DriveA/Mixed/img_0001.jpg", shape="S9")


def _s11_windows_artifacts(writer: CorpusWriter) -> None:
    """Present in Ad's library as a trace (9 ``.db``, 11 ``.ini``); here as a population."""
    for folder in ("DriveA/Pictures", "DriveB/My Pictures", "DriveA/Picasa/Album 2009"):
        writer.write_bytes(
            b"\x00\x00\x00\x00thumbs", f"{folder}/Thumbs.db", shape="S11", role="artifact"
        )
        writer.write_bytes(
            b"[.ShellClassInfo]\n", f"{folder}/desktop.ini", shape="S11", role="artifact"
        )


def _s12_zero_byte_and_truncated(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """Failed copies across `"three or four PC upgrades"`."""
    writer.write_bytes(b"", "DriveE/FOUND.000/FILE9999.CHK", shape="S12", role="artifact")
    head = sample[1].read_bytes()[:2048]
    writer.write_bytes(
        head, "DriveE/recup_dir.1/f9999999.jpg", shape="S12", role="truncated", source=sample[1]
    )


def _s13_deep_nesting(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """Deep paths and long names, which `(aid)` is open on with no corpus behind it."""
    deep = "/".join(f"level-{i:02d}" for i in range(12))
    writer.copy(sample[2], f"DriveD/{deep}/{sample[2].name}", shape="S13")
    long_name = "a-holiday-photograph-with-a-very-long-descriptive-filename" * 3
    writer.copy(sample[3], f"DriveD/Long/{long_name[:200]}.jpg", shape="S13")


def _s14_orphan_sidecar(writer: CorpusWriter) -> None:
    """A sidecar whose media is gone - the residue of a multi-tool history."""
    writer.write_bytes(
        b'{"title": "IMG_4242.jpg", "photoTakenTime": {"timestamp": "1467331200"}}',
        "DriveC/Exports/IMG_4242.jpg.json",
        shape="S14",
        role="artifact",
    )


def _s15_rotated(writer: CorpusWriter, sample: Sequence[Path]) -> None:
    """A copy whose pixels are turned.

    ``hashing.perceptual_hash`` never calls ``exif_transpose``, so a turned copy hashes as a
    different photograph. Included to measure that, not to assert it is wrong.
    """
    for source in _share(sample, "S15"):
        writer.write_bytes(
            _reencode(source, rotate=90),
            f"DriveC/Rotated/{source.stem}_rot90.jpg",
            shape="S15",
            role="rotated",
            source=source,
        )


def _s16_migration_folders(
    writer: CorpusWriter, sample: Sequence[Path], rng: random.Random
) -> None:
    """Folder names that encode the migration, which is what `suggest_name` reads."""
    folders = ("Old PC", "Desktop backup", "To Sort", "New folder (2)", "Camera Uploads")
    for source in _share(sample, "S16"):
        folder = rng.choice(folders)
        writer.copy(source, f"DriveG/{folder}/{source.name}", shape="S16")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, required=True, help="READ-ONLY library to derive from"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="corpus root (created)")
    parser.add_argument("--seed", type=int, default=20260829, help="decides every sample; cite it")
    parser.add_argument("--files", type=int, default=60, help="base photographs to sample")
    args = parser.parse_args(argv)

    source = args.source.resolve()
    out = args.out.resolve()
    if out == source or out.is_relative_to(source):
        print(f"error: the corpus root {out} is inside the source {source}", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    sample = sample_images(source, args.files, rng)
    writer = CorpusWriter(out)
    build(writer, sample, rng)
    manifest = writer.write_manifest()

    total = sum(row.size for row in writer.rows)
    print(f"corpus: {len(writer.rows)} files, {total / 1_000_000:.1f} MB, seed {args.seed}")
    print(f"shapes: {', '.join(sorted({row.shape for row in writer.rows}))}")
    print(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
