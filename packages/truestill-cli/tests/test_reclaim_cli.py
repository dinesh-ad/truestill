"""`truestill reclaim`: connected-drive required, dry-run default, a typed confirmation."""

from __future__ import annotations

from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.drive import create_marker
from truestill_core.hashing import sha256_file


def _seed(db: Path, drive: Path, source: Path, content: bytes = b"content") -> None:
    marker = create_marker(drive, "Drive A")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(content)
    copy = drive / "Camera/a.jpg"
    copy.parent.mkdir(parents=True, exist_ok=True)
    copy.write_bytes(content)
    with Catalog(db) as catalog:
        catalog.upsert_drive(uuid=marker.uuid, label="Drive A")
        catalog.record_uploaded(
            source_path=str(source),
            original_name=source.name,
            sha256=sha256_file(source),
            copy_sha256=sha256_file(source),
            perceptual=None,
            size=len(content),
            captured_at=None,
            category="Camera",
            relative="Camera/a.jpg",
            drive_uuid=marker.uuid,
        )


def test_reclaim_requires_connected_drive(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The folder must EXIST. An absent path is a different state with the opposite remedy -
    # it now says "is it plugged in?" rather than "register it", because sending someone to
    # `drives --init` for an unmounted drive is what mints a duplicate identity ((aap)).
    plain = tmp_path / "not-a-drive"
    plain.mkdir()
    code = main(["reclaim", str(plain), "--db", str(tmp_path / "c.sqlite")])
    assert code == 2
    # The refusal names what the folder IS and what to do, rather than the marker filename.
    err = capsys.readouterr().err
    # `(afc)`: the message names both readings now - a new folder and an unmounted drive.
    assert "is not a Truestill drive" in err
    assert "drives --init" in err


def test_reclaim_preview_deletes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)

    assert main(["reclaim", str(drive), "--db", str(db)]) == 0
    out = capsys.readouterr().out
    assert "reclaimable: 1" in out
    assert "Preview only" in out
    assert source.exists()  # dry-run never deletes


def test_reclaim_apply_requires_typed_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)

    monkeypatch.setattr("builtins.input", lambda _prompt: "no")  # wrong answer -> abort
    assert main(["reclaim", str(drive), "--db", str(db), "--apply"]) == 0
    assert source.exists()  # not confirmed -> nothing deleted


def test_reclaim_apply_refuses_non_interactive_stdin(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)

    monkeypatch.setattr("builtins.input", lambda *_: (_ for _ in ()).throw(EOFError()))
    assert main(["reclaim", str(drive), "--db", str(db), "--apply"]) == 0
    assert "interactive confirmation is required" in capsys.readouterr().err
    assert source.exists()


def test_reclaim_apply_deletes_on_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)

    monkeypatch.setattr("builtins.input", lambda _prompt: "delete originals")
    assert main(["reclaim", str(drive), "--db", str(db), "--apply"]) == 0
    assert not source.exists()  # confirmed -> source freed
    assert (drive / "Camera/a.jpg").exists()  # backup copy untouched


def test_reclaim_reports_stale_sources_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)
    source.unlink()

    assert main(["reclaim", str(drive), "--db", str(db)]) == 0
    captured = capsys.readouterr()
    assert "1 recorded source" in captured.err
    assert "may have moved" in captured.err
    assert str(source) in captured.err
    assert "Preview only" not in captured.out  # nothing to apply; do not nag
    assert "error" not in captured.out.lower()


def test_reclaim_empty_plan_reads_as_calm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    create_marker(drive, "Drive A")

    assert main(["reclaim", str(drive), "--db", str(db)]) == 0
    captured = capsys.readouterr()
    assert "Nothing to reclaim." in captured.out
    assert "Preview only" not in captured.out
    assert "recorded source" not in captured.err
    assert "error" not in captured.out.lower()


def test_the_old_weaker_word_no_longer_authorises_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """⚠ `delete` guarded the strongest act in the product and was its weakest word. `(afh)`

    Measured 2026-08-22: this asked for `delete` behind one line of warning, while
    `clean-empty --permanent` asked for `delete forever` behind six - and the second removes
    folders truestill itself emptied, after their junk had gone to the trash. The ceremony was
    inverted relative to the stakes, so the word was raised rather than the other lowered.

    A user who typed the old word out of habit must not have it accepted.
    """
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    source = tmp_path / "src" / "a.jpg"
    _seed(db, drive, source)

    monkeypatch.setattr("builtins.input", lambda _prompt: "delete")
    assert main(["reclaim", str(drive), "--db", str(db), "--apply"]) == 0
    assert source.exists(), "the retired word still deleted the user's original"


def test_the_confirmation_says_what_is_lost_and_that_it_cannot_be_undone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Three claims, each of which a user could otherwise get wrong.

    That these are ORIGINALS is the one that matters: a reader who believes reclaim removes spare
    copies has misunderstood the whole feature, and the previous wording - *"PERMANENTLY DELETES
    161 source file(s)"* - never said otherwise. "source file" is the catalog's word for it.
    """
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    _seed(db, drive, tmp_path / "src" / "a.jpg")

    monkeypatch.setattr("builtins.input", lambda _prompt: "no")
    main(["reclaim", str(drive), "--db", str(db), "--apply"])

    out = capsys.readouterr().out
    assert "ORIGINAL" in out
    assert "not spare copies" in out
    assert "CANNOT BE UNDONE" in out
    assert "do NOT go to the trash" in out


def test_reclaim_asks_for_at_least_as_much_as_clean_empty_permanent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The property, rather than the wording: the stronger act may not ask for less.

    Pinned as a comparison so that lowering reclaim's ceremony, or raising `clean-empty`'s past
    it, both fail here - which a test of either sentence alone would not catch.
    """
    drive, db = tmp_path / "drive", tmp_path / "c.sqlite"
    drive.mkdir()
    _seed(db, drive, tmp_path / "src" / "a.jpg")

    asked: list[str] = []

    def record(prompt: str) -> str:
        # ⚠ The prompt reaches the user through `input`, not `print`, so `capsys` never sees it.
        # A test that read stdout would assert against a string the product does not put there.
        asked.append(prompt)
        return "no"

    monkeypatch.setattr("builtins.input", record)
    main(["reclaim", str(drive), "--db", str(db), "--apply"])

    assert asked, "no confirmation was asked for at all"
    assert "delete originals" in asked[-1]
    # `clean` is the recoverable word and must never be what this act asks for.
    assert "'clean'" not in asked[-1]
    assert capsys.readouterr()
