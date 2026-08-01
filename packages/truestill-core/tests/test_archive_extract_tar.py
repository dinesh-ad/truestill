"""Tar, kept apart from zip because its safety depends on an argument nobody would notice ((jj)).

**Why zip and tar are not the same problem, precisely.** A blanket "archives are unsafe" is the
wrong lesson and would put pointless defences on the zip path while leaving the real difference
invisible. Measured on 3.13:

* `zipfile` **sanitises unconditionally** - ``../../x`` lands as ``x`` inside the destination -
  and **never creates symlinks**: a symlink entry extracts as an ordinary file containing the
  target string.
* `tarfile` **escapes by default**. ``../../x`` is written *outside* the destination with only a
  ``DeprecationWarning``, because ``TarFile.extraction_filter`` is ``None`` on 3.13.

So tar needs a filter and zip does not. That asymmetry is the whole reason this ships as its own
commit: the protection is one argument, and an argument is exactly what a refactor drops without
anyone noticing.

**The protections come from `tarfile.data_filter` called per member, not from
``extractall(filter="data")``.** The filter is a public function, so applying it directly keeps
tar on the *same* streaming byte counter, the *same* staging journal and the *same*
partial-then-rename as zip - rather than forking the extractor to get safety. Verified: called
directly it raises `OutsideDestinationError`, `AbsoluteLinkError` and `SpecialFileError` for the
three attacks.

**`.tgz` is the case a user actually has.** Google offers ``.zip`` and ``.tgz``, so the gzip
layer is tested, not merely ``.tar``.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest
from truestill_core.archive_extract import (
    ExtractionRefusedError,
    extract_archive_set,
    pending_staging,
)
from truestill_core.archive_set import discover_archive_set, inspect_archive_set


def _tar(path: Path, members: list[tarfile.TarInfo], data: dict[str, bytes], mode: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, mode) as archive:
        for member in members:
            payload = data.get(member.name)
            archive.addfile(member, io.BytesIO(payload) if payload is not None else None)
    return path


def _file(name: str, payload: bytes) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    return info


def _plain(path: Path, entries: dict[str, bytes], mode: str = "w:gz") -> Path:
    return _tar(path, [_file(n, d) for n, d in entries.items()], entries, mode)


# --- the format a user actually downloads --------------------------------------------------


@pytest.mark.parametrize(
    ("name", "mode"), [("t.tgz", "w:gz"), ("t.tar", "w"), ("t.tar.gz", "w:gz")]
)
def test_a_gzipped_tar_extracts(tmp_path: Path, name: str, mode: str) -> None:
    """Google offers .zip and .tgz, so the gzip layer is the real case - not bare .tar."""
    _plain(tmp_path / name, {"Takeout/Photos/IMG_1.jpg": b"\xff\xd8jpeg"}, mode)

    found = discover_archive_set([tmp_path / name])
    result = extract_archive_set(found, tmp_path / "dest")

    assert (result.staging_root / "Takeout/Photos/IMG_1.jpg").read_bytes() == b"\xff\xd8jpeg"


def test_a_tar_set_is_inspected_like_a_zip_set(tmp_path: Path) -> None:
    """The precondition report must work on tar too, or the refusals only cover half the formats."""
    _plain(tmp_path / "t.tgz", {"a/IMG_1.jpg": b"x" * 120, "a/IMG_1.jpg.json": b"{}"})

    inspection = inspect_archive_set(discover_archive_set([tmp_path / "t.tgz"]))

    assert inspection.claimed_bytes == 122
    assert inspection.entries == 2
    assert inspection.media_entries == 1


def test_multi_part_tar_gz_sets_are_grouped(tmp_path: Path) -> None:
    """`.tar.gz` has a double extension, so naive stem-splitting would miss the part number
    and treat every part as its own unnumbered set - losing the missing-part check entirely."""
    for number in (1, 2):
        _plain(tmp_path / f"takeout-{number:03d}.tar.gz", {f"a/IMG_{number}.jpg": b"x"})

    found = discover_archive_set(sorted(tmp_path.glob("*.tar.gz")))

    assert [part.number for part in found.parts] == [1, 2]


# --- the three attacks the filter blocks ---------------------------------------------------


def test_a_traversal_member_is_refused(tmp_path: Path) -> None:
    """`tarfile` writes this OUTSIDE the destination by default, with only a DeprecationWarning."""
    _plain(tmp_path / "t.tgz", {"../../escape.txt": b"abc"})

    with pytest.raises(ExtractionRefusedError, match=r"escape\.txt"):
        extract_archive_set(discover_archive_set([tmp_path / "t.tgz"]), tmp_path / "dest")

    assert not (tmp_path.parent / "escape.txt").exists()


def test_an_absolute_symlink_member_is_refused(tmp_path: Path) -> None:
    """tar carries real symlinks, which zip does not - so this is a tar-specific hazard."""
    link = tarfile.TarInfo("evil")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"
    _tar(tmp_path / "t.tgz", [link], {}, "w:gz")

    with pytest.raises(ExtractionRefusedError, match="evil"):
        extract_archive_set(discover_archive_set([tmp_path / "t.tgz"]), tmp_path / "dest")


def test_a_device_node_member_is_refused(tmp_path: Path) -> None:
    """Also tar-only. A photo export has no business carrying one."""
    node = tarfile.TarInfo("dev")
    node.type = tarfile.CHRTYPE
    _tar(tmp_path / "t.tgz", [node], {}, "w:gz")

    with pytest.raises(ExtractionRefusedError, match="dev"):
        extract_archive_set(discover_archive_set([tmp_path / "t.tgz"]), tmp_path / "dest")


def test_the_filter_is_actually_applied_not_merely_present(tmp_path: Path) -> None:
    """The test that must exist, because the protection IS an argument.

    **Asserted on the exception CHAIN, not the message.** The first version of this matched the
    word "outside" - which our own `_validate_entry_name` also says, so it passed with
    `data_filter` deleted. It was checking that *something* refused, which is not the question.

    `tarfile.FilterError` can only be raised by the filter, and the refusal re-raises `from` it,
    so this fails the moment the call is removed - which is the whole reason tar ships separately.
    """
    _plain(tmp_path / "t.tgz", {"../../escape.txt": b"abc"})

    with pytest.raises(ExtractionRefusedError) as raised:
        extract_archive_set(discover_archive_set([tmp_path / "t.tgz"]), tmp_path / "dest")

    assert isinstance(raised.value.__cause__, tarfile.FilterError), (
        "the refusal did not come from tarfile's data filter - our own name check caught it "
        f"instead, so the filter may not be applied at all: cause={raised.value.__cause__!r}"
    )


# --- one extractor, not two ----------------------------------------------------------------


def test_tar_uses_the_same_streaming_byte_counter(tmp_path: Path) -> None:
    """Not a separate path: the counter that stops a zip bomb stops a tar bomb."""
    _plain(tmp_path / "t.tgz", {"big.bin": b"x" * 5000})

    with pytest.raises(ExtractionRefusedError, match=r"expands to more than"):
        extract_archive_set(
            discover_archive_set([tmp_path / "t.tgz"]), tmp_path / "dest", budget_bytes=1000
        )


def test_tar_uses_the_same_staging_journal(tmp_path: Path) -> None:
    """Recovery must have one path for both formats, not one each."""
    _plain(tmp_path / "t.tgz", {"a/IMG_1.jpg": b"\xff\xd8x"})
    destination = tmp_path / "dest"

    extract_archive_set(discover_archive_set([tmp_path / "t.tgz"]), destination)

    assert pending_staging(destination), "a tar extraction left nothing the next run can attribute"


def test_a_mixed_set_is_not_silently_half_extracted(tmp_path: Path) -> None:
    """Cry-wolf half: a folder holding both formats is two sources, not one broken one."""
    _plain(tmp_path / "photos-001.tgz", {"a/IMG_1.jpg": b"x"})
    with zipfile.ZipFile(tmp_path / "photos-002.zip", "w") as archive:
        archive.writestr("a/IMG_2.jpg", b"y")

    found = discover_archive_set(sorted(tmp_path.iterdir()))

    assert len(found.sets) == 2, "a zip and a tar were merged into one set"
