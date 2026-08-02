"""`truestill repoint-sources`: preview, prove, then a typed word (`BACKLOG.md` ``(yy)``).

The command exists because `files.source_path` is absolute and a moved folder leaves every
recorded source dangling - reclaim reports missing rows instead of offering deletes, and Find
cites paths that no longer resolve.

**It refuses far more readily than it rewrites**, because `reclaim` deletes `source_path` and
its safety gate re-hashes the *drive copy*, never the source. A path pointed at the wrong tree
would be a file deleted without ever having been verified.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.hashing import sha256_file


def _catalogued(db: Path, root: Path, names: list[str]) -> None:
    """A library imported from ``root``, recorded the way organize records it."""
    for i, name in enumerate(names):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"photo-{i}".encode())
    with Catalog(db) as catalog:
        for name in names:
            catalog.record_uploaded(
                source_path=str(root / name),
                original_name=Path(name).name,
                sha256=_digest(root / name),
                perceptual=None,
                size=8,
                captured_at=None,
                category="Camera",
                relative=f"Camera/{Path(name).name}",
            )


def _digest(path: Path) -> str:
    return sha256_file(path)


def _sources(db: Path) -> list[str]:
    with Catalog(db) as catalog:
        return sorted(source for source, _sha, _p in catalog.seed_rows())


_NAMES = [f"trip/day{i // 4}/IMG_{i:03d}.jpg" for i in range(12)]


@pytest.fixture
def moved(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A catalogued library whose source folder has been moved. Returns (old, new, db)."""
    old, new, db = tmp_path / "old", tmp_path / "new", tmp_path / "c.sqlite"
    _catalogued(db, old, _NAMES)
    shutil.move(str(old), str(new))
    return old, new, db


def test_preview_changes_nothing_and_says_what_it_would_do(
    moved: tuple[Path, Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    old, new, db = moved
    before = _sources(db)

    assert main(["repoint-sources", str(old), str(new), "--db", str(db)]) == 0
    out = capsys.readouterr().out

    assert "PREVIEW" in out
    assert f"rows recorded under the old root : {len(_NAMES)}" in out
    assert f"found at the new root            : {len(_NAMES)}" in out
    assert "sampled files match" in out
    assert "Re-run with --apply" in out
    assert _sources(db) == before, "a preview must write nothing"


def test_apply_rewrites_every_descendant_after_the_typed_word(
    moved: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One root named, all twelve recorded paths rewritten."""
    old, new, db = moved
    monkeypatch.setattr("builtins.input", lambda _prompt: "repoint")

    assert main(["repoint-sources", str(old), str(new), "--apply", "--db", str(db)]) == 0
    out = capsys.readouterr().out

    assert f"Repointed {len(_NAMES)} recorded source path(s)" in out
    after = _sources(db)
    assert all(source.startswith(str(new)) for source in after)
    assert all(Path(source).is_file() for source in after), (
        "every rewritten path must name a file that is actually there"
    )


def test_declining_the_typed_word_changes_nothing(
    moved: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old, new, db = moved
    before = _sources(db)
    monkeypatch.setattr("builtins.input", lambda _prompt: "yes")

    assert main(["repoint-sources", str(old), str(new), "--apply", "--db", str(db)]) == 0
    out = capsys.readouterr().out

    assert "Aborted. Nothing was changed." in out
    assert _sources(db) == before


def test_a_tree_holding_different_content_is_refused(
    moved: tuple[Path, Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The dangerous case: the layout lines up and the bytes do not.

    Refusing is what stops `reclaim` deleting an unverified file later.
    """
    old, new, db = moved
    decoy = tmp_path / "decoy"
    for name in _NAMES:
        target = decoy / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"a completely different photo")
    before = _sources(db)
    monkeypatch.setattr("builtins.input", lambda _prompt: "repoint")

    code = main(["repoint-sources", str(old), str(decoy), "--apply", "--db", str(db)])
    captured = capsys.readouterr()

    assert code == 2
    assert "does not hold the files recorded under" in captured.err
    assert "Nothing was changed" in captured.err
    assert _sources(db) == before
    assert new.is_dir(), "fixture check: the real tree is still where it was"


def test_a_root_nothing_was_imported_from_is_a_clean_no_op(
    moved: tuple[Path, Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Cry-wolf half: naming an unrelated folder is answered, not treated as a failure."""
    _old, new, db = moved
    stranger = tmp_path / "never-imported"
    stranger.mkdir()

    assert main(["repoint-sources", str(stranger), str(new), "--db", str(db)]) == 0
    out = capsys.readouterr().out

    assert "Nothing to repoint" in out


def test_a_new_root_that_is_not_there_is_refused_before_anything_is_read(
    moved: tuple[Path, Path, Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    old, _new, db = moved
    before = _sources(db)

    code = main(["repoint-sources", str(old), str(tmp_path / "nowhere"), "--db", str(db)])

    assert code == 2
    assert "is not a folder" in capsys.readouterr().err
    assert _sources(db) == before
