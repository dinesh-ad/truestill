"""`truestill restore <root>`: the command a user reaches for after losing their machine.

**The whole case is an EMPTY catalog with NO registered drives.** Every other decisions path
starts from a catalog that already knows something; this one cannot, because the catalog is what
was lost. A restore that needed a registered drive to find a drive's document would work for
everybody except the person it exists for.

**Two words, two branches, and only one of them destroys anything.** `restore` reads the drive
and writes the catalog. `discard` does the opposite and is the destructive one: it overwrites the
drive's document with this catalog's, so decisions on that drive and nowhere else are gone. The
words match the CLI's existing dialect - the operation's own verb, like `move`, `clean` and
`undo` - rather than inventing a third vocabulary on top of `(aca)`'s two.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from truestill_cli.cli import main
from truestill_core.catalog import Catalog
from truestill_core.decisions import DECISIONS_NAME
from truestill_core.drive import create_marker

_DAYS = ["2014-08-14", "2014-08-15"]


def _drive_with_decisions(tmp_path: Path, **overrides: object) -> Path:
    """A drive carrying a document, and a catalog that has never heard of either."""
    root = tmp_path / "drive"
    root.mkdir()
    marker = create_marker(root, "Output")
    document: dict[str, object] = {
        "format": 1,
        "written": "2026-08-01T00:00:00+00:00",
        "drive": {"uuid": marker.uuid, "label": "Output", "notes": None},
        "trips": [
            {
                "name": "Wayanad",
                "slug": "wayanad",
                "start": _DAYS[0],
                "end": _DAYS[1],
                "days": _DAYS,
            }
        ],
        "skipped_clusters": ["b" * 64],
    }
    document.update(overrides)
    (root / DECISIONS_NAME).write_text(json.dumps(document), encoding="utf-8")
    return root


def test_a_preview_restores_nothing_and_says_what_it_would(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry run by default, like every other command that writes. The user sees the whole picture
    before anything happens, and an accidental `truestill restore` costs them nothing."""
    root = _drive_with_decisions(tmp_path)
    db = tmp_path / "c.sqlite"

    code = main(["restore", str(root), "--db", str(db)])

    out = capsys.readouterr().out
    assert code == 0
    # Counts per section, not a list of names: trips are few but events are not, and a preview
    # that scrolls is a preview nobody reads to the end. The exceptions ARE named, because those
    # are the ones a user may want to act on - see the test below.
    assert "Read 1 decisions document(s)." in out
    assert "trips" in out
    with Catalog(db) as catalog:
        assert catalog.all_trips() == [], "a preview restored something"


def test_it_works_with_an_empty_catalog_and_no_registered_drives(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE CASE THIS COMMAND EXISTS FOR. The machine is new, the catalog is empty, and nothing is
    registered - so the drive is found by the path the user typed, not by a lookup."""
    root = _drive_with_decisions(tmp_path)
    db = tmp_path / "c.sqlite"
    monkeypatch.setattr("builtins.input", lambda *_: "restore")

    code = main(["restore", str(root), "--db", str(db), "--apply"])

    assert code == 0
    with Catalog(db) as catalog:
        assert [str(r["name"]) for r in catalog.all_trips()] == ["Wayanad"]
        assert catalog.skipped_signatures() == frozenset({"b" * 64})
        assert [str(r["label"]) for r in catalog.registered_drives()] == ["Output"]
    assert "restored" in capsys.readouterr().out.lower()


def test_the_wrong_word_restores_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A typed confirm that accepts anything is a prompt, not a gate."""
    root = _drive_with_decisions(tmp_path)
    db = tmp_path / "c.sqlite"
    monkeypatch.setattr("builtins.input", lambda *_: "yes")

    code = main(["restore", str(root), "--db", str(db), "--apply"])

    assert code == 1
    with Catalog(db) as catalog:
        assert catalog.all_trips() == []


def test_it_reports_what_it_would_not_do_before_asking(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """40 APPLIED AND SILENCE ABOUT THE REST is the failure. An unmatched event signature and a
    correction for an unscanned photo are both invisible in a count of what came back, and both
    are things the user may want to act on before deciding."""
    root = _drive_with_decisions(
        tmp_path,
        events=[{"name": "Sam Wedding", "slug": "g", "start": "2015-10-25", "signature": "a" * 64}],
        date_confirmations=[
            {"sha256": "e" * 64, "captured_at": "2015-01-01T00:00:00", "confirmed_at": "2026-01-01"}
        ],
    )
    db = tmp_path / "c.sqlite"

    main(["restore", str(root), "--db", str(db)])

    out = capsys.readouterr().out
    assert "Sam Wedding" in out, "an unmatched event was not named"
    assert "scan" in out.lower(), "the awaiting-content remedy was not explained"
    assert "1 date confirmations" in out, "the awaiting-content count was not given"

    # ⚠ **A lost name is printed in the ACTIONABLE register.** `(aia)` derives the marker from
    # `RestoreWording.actionable` rather than typing it at each site, because a real loss rendered
    # with the `-` used for "Nothing to do" is reassurance where a warning belongs - which is how
    # it read before, and what `(ahz)` recorded. A mutation forcing every marker to `-` killed no
    # test until this line existed.
    lost = next(line for line in out.splitlines() if "Sam Wedding" in line)
    assert lost.lstrip().startswith("!"), f"a lost name was not flagged as actionable: {lost!r}"


def test_a_document_from_a_newer_truestill_names_the_remedy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A refusal without a remedy is the stranded-names failure this feature exists to prevent.
    The names are on the disk and readable; the user needs to be told what to run."""
    root = _drive_with_decisions(tmp_path, format=2)
    db = tmp_path / "c.sqlite"

    code = main(["restore", str(root), "--db", str(db)])

    output = capsys.readouterr()
    assert code == 2
    assert "upgrade" in (output.out + output.err).lower()


def test_a_root_with_no_document_says_so_rather_than_succeeding_emptily(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """ "Nothing to restore" and "restored nothing" read the same in a log and mean opposite
    things. A drive with no document is the first, and it is not a success."""
    root = tmp_path / "drive"
    root.mkdir()
    create_marker(root, "Output")
    db = tmp_path / "c.sqlite"

    code = main(["restore", str(root), "--db", str(db)])

    assert code == 2
    assert "no decisions" in (capsys.readouterr().err).lower()


# --- discard: the destructive branch, and (aby) -------------------------------------------


def test_discard_overwrites_the_drive_and_says_what_it_destroys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(aby) CLOSES HERE. A decision deleted locally leaves the drive holding something this
    catalog does not, so every later save refuses with WOULD_LOSE - permanently, because nothing
    reconciles the two. Discard is the user saying "mine is right": one forced write, after which
    the drive matches the catalog and the guard has nothing left to fire on.

    It is the destructive branch and its word says so - the trip name on that drive and nowhere
    else is gone once this runs.
    """
    root = _drive_with_decisions(tmp_path)
    db = tmp_path / "c.sqlite"
    monkeypatch.setattr("builtins.input", lambda *_: "discard")

    code = main(["restore", str(root), "--db", str(db), "--discard", "--apply"])

    assert code == 0
    document = json.loads((root / DECISIONS_NAME).read_text(encoding="utf-8"))
    assert document["trips"] == [], "the drive still holds the discarded decisions"
    with Catalog(db) as catalog:
        assert catalog.all_trips() == [], "discard restored the decisions it was told to drop"


def test_discard_refuses_the_restore_word(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The safe word must not authorise the destructive branch. `clean-empty` learned this: a
    word typed once, understood to mean one thing, cannot silently authorise another."""
    root = _drive_with_decisions(tmp_path)
    db = tmp_path / "c.sqlite"
    before = (root / DECISIONS_NAME).read_text(encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda *_: "restore")

    code = main(["restore", str(root), "--db", str(db), "--discard", "--apply"])

    assert code == 1
    assert (root / DECISIONS_NAME).read_text(encoding="utf-8") == before


def test_discard_previews_without_writing(tmp_path: Path) -> None:
    """Dry run by default on the destructive branch too, and this is where it matters most."""
    root = _drive_with_decisions(tmp_path)
    db = tmp_path / "c.sqlite"
    before = (root / DECISIONS_NAME).read_text(encoding="utf-8")

    code = main(["restore", str(root), "--db", str(db), "--discard"])

    assert code == 0
    assert (root / DECISIONS_NAME).read_text(encoding="utf-8") == before


def test_discard_keeps_sections_a_newer_truestill_wrote(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Discard drops the decisions this catalog disagrees with - not the ones it cannot read.

    A section from a newer version is not a decision this catalog is overruling; it is one it
    does not understand. Destroying it here would be the write-side loss the merge exists to
    prevent, arriving through the one command that is allowed to overwrite.
    """
    root = _drive_with_decisions(tmp_path, captions={"a" * 64: "on the ferry"})
    db = tmp_path / "c.sqlite"
    monkeypatch.setattr("builtins.input", lambda *_: "discard")

    main(["restore", str(root), "--db", str(db), "--discard", "--apply"])

    document = json.loads((root / DECISIONS_NAME).read_text(encoding="utf-8"))
    assert document["captions"] == {"a" * 64: "on the ferry"}
    assert document["trips"] == []


def test_a_second_discard_has_nothing_to_do_and_does_not_ask(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """ONLY THE SECOND INVOCATION TELLS THESE APART. Once the drive matches the catalog there is
    nothing to discard, and asking for a destructive word when nothing is at stake teaches the
    user to type it without reading - which is how the word stops being a gate.
    """
    root = _drive_with_decisions(tmp_path)
    db = tmp_path / "c.sqlite"
    monkeypatch.setattr("builtins.input", lambda *_: "discard")
    main(["restore", str(root), "--db", str(db), "--discard", "--apply"])
    capsys.readouterr()

    def refuse_to_ask(*_: object) -> str:
        pytest.fail("a second discard asked for the destructive word again")

    monkeypatch.setattr("builtins.input", refuse_to_ask)
    code = main(["restore", str(root), "--db", str(db), "--discard", "--apply"])

    assert code == 0
    assert "nothing to discard" in capsys.readouterr().out.lower()
