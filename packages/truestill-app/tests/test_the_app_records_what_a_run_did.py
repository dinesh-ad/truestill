"""`(afu)`: an app organize run writes the record `IMPLEMENTATION_STANDARDS` §1 requires.

Three claims, deliberately separate because they fail for different reasons:

1. **The app path writes one, end to end** - driven through `organize_run`'s real job, never
   through the builder. A test that called `build_run_record` directly would have passed on the
   day the gap existed, because the builder was never the broken part: it was **unreachable** from
   this package, `truestill-app` depending on `truestill-core` only (§2). §4's thirteenth member -
   assert the subject entered the path.
2. **The two surfaces record the same fields** - the whole point of one builder. Compared key by
   key rather than by spot-checking, so a field added on one side cannot quietly not exist on the
   other.
3. **Every mutating app run is enumerated** as writing or not writing, with its reason - so the
   four that are out of `(afu)`'s scope are *recorded as absent* rather than merely missing.
"""

from __future__ import annotations

import json
import random
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image
from truestill_app.service.organize import organize_run
from truestill_core import organizer
from truestill_core.app_paths import record_path_for
from truestill_core.models import ActionStatus, Resolution, UnreadableReason
from truestill_core.progress import Phase, Progress
from truestill_core.run_record import RUN_RECORD_FORMAT, build_run_record

#: Every app service that changes the library, and whether `(afu)` gave it a run record.
#:
#: ⚠ **The absent ones are listed WITH THEIR REASON, which is the point of the table.** A guard
#: that only checked organize would be true and would say nothing about the other four, and
#: "nobody wrote a test for it" and "it was ruled out of scope" look identical from outside.
MUTATING_RUNS: dict[str, tuple[bool, str]] = {
    "organize": (True, "has a per-file ActionResult list; `(afu)` wires it"),
    "backup": (
        False,
        (
            "fail-fast: `_copy_verified_or_raise` raises, so there is no per-file outcome model "
            "to record. Whether that is right is ENGINEERING_STANDARD.md §4 Errors' "
            "'one bad file never aborts a batch'"
        ),
    ),
    "migrate": (
        False,
        "returns counts plus a per-file PLAN; its durable per-file state is `migration_journal`",
    ),
    "bake": (False, "returns counts only"),
    "organize_undo": (False, "returns counts only"),
}


def _photo(path: Path, seed: int) -> None:
    """The app suite's own helper, so this fixture is the shape every other app test uses."""
    rng = random.Random(seed)
    image = Image.new("RGB", (64, 64))
    image.putdata(
        [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(4096)]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "JPEG", quality=95)


def _library(tmp_path: Path, count: int = 1) -> tuple[Path, Path, Path]:
    source, destination = tmp_path / "src", tmp_path / "dest"
    source.mkdir(parents=True, exist_ok=True)
    destination.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        _photo(source / f"{index}.jpg", seed=index)
    return source, destination, tmp_path / "catalog.sqlite"


def _run(
    source: Path, destination: Path, db: Path, *, cancel: threading.Event | None = None
) -> object:
    """Drive the real app job, the way a route does."""
    target = organize_run(source, destination, db)
    return target(lambda _progress: None, cancel or threading.Event())


def _record(db: Path) -> dict[str, object]:
    return json.loads(record_path_for(db).read_text(encoding="utf-8"))


def test_an_app_run_writes_the_record_without_being_asked(tmp_path: Path) -> None:
    """§1's invariant, on the surface its own justification names.

    Asserts the record's CONTENT, not that a file exists: a file at the right path with a
    plausible size is exactly what a torn write leaves (§4's fiftieth member).
    """
    source, destination, db = _library(tmp_path)

    _run(source, destination, db)

    record = _record(db)
    assert record["format"] == RUN_RECORD_FORMAT
    run = record["run"]
    assert isinstance(run, dict)
    assert run["source"] == str(source)
    assert run["destination"] == str(destination)
    assert run["intended_total"] == 1
    assert run["attempted"] == 1
    assert run["stopped"] is None
    files = record["files"]
    assert isinstance(files, list)
    assert [f["source"] for f in files] == [str(source / "0.jpg")]
    assert files[0]["status"] == ActionStatus.UPLOADED.value


def test_the_record_names_a_file_the_run_could_not_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`(aac)`'s conflation, fixed inside the record before anything relied on it.

    Without `unreadable`, a file the run never reached recorded ``"not attempted"`` and a null
    ``sha256`` - which is **also** what the size pre-filter's legitimate skip looks like. This
    asserts the two are distinguishable in the document.
    """
    source, destination, db = _library(tmp_path)
    real_resolve = organizer.resolve

    def unreadable(*args: object, **kwargs: object) -> list[Resolution]:
        resolutions = real_resolve(*args, **kwargs)  # type: ignore[arg-type]
        return [
            replace(r, hashes=replace(r.hashes, unreadable=UnreadableReason.PERMISSION))
            for r in resolutions
        ]

    monkeypatch.setattr("truestill_app.service.organize.resolve", unreadable)
    _run(source, destination, db)

    files = _record(db)["files"]
    assert isinstance(files, list)
    assert files[0]["unreadable"] == UnreadableReason.PERMISSION.value


def test_a_cancelled_run_records_the_reason_it_actually_stopped_for(tmp_path: Path) -> None:
    """⚠ The branch the CLI could never reach, and the reason `stopped=` is passed explicitly.

    `stop_block` reads the reason off the last result, which works for the two stops that record
    a `FAILED` row and **not** for a cancel, which records nothing. Driven through a real `cancel`
    event rather than a fabricated `stopped` dict, because the fabricated one would pass whether
    or not the plumbing existed.
    """
    source, destination, db = _library(tmp_path, count=4)

    # ⚠ **Set MID-RUN, not before it.** Cancelling before the plan exists leaves nothing planned
    # either, so `never_attempted` is legitimately 0 and the fixture proves nothing - the first
    # version of this test did exactly that. A user presses stop while files are being copied.
    cancel = threading.Event()

    def stop_after_the_first_copy(progress: Progress) -> None:
        # ⚠ **Gated on the PHASE, and that is not decoration.** The same callback is handed to
        # `resolve`, so a bare `done >= 1` cancels during PLANNING - which truncates `resolutions`
        # and `results` equally and leaves `never_attempted` at 0. The first version of this test
        # did that and passed alone, then failed when another file's run warmed the cache and
        # moved where the count landed. Only ORGANIZING is the copying loop.
        if progress.phase == Phase.ORGANIZING and progress.done >= 1:
            cancel.set()

    target = organize_run(source, destination, db)
    target(stop_after_the_first_copy, cancel)

    stopped = _record(db)["run"]
    assert isinstance(stopped, dict)
    block = stopped["stopped"]
    assert isinstance(block, dict), "a cancelled run recorded no stop block"
    assert block["reason"] == "you stopped this run", block
    assert block["never_attempted"] >= 1


def test_a_failed_write_reaches_the_completion_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The record must not fail the run, and its absence must not be silent - `(acc)`'s shape."""
    source, destination, db = _library(tmp_path)

    monkeypatch.setattr(
        "truestill_app.service.organize.write_run_record",
        lambda _path, _payload: "No space left on device",
    )
    done = _run(source, destination, db)

    assert isinstance(done, dict)
    assert done["organized"] == 1, "the paperwork failing must not fail the run"
    assert done["record_error"] == "No space left on device"


def test_a_successful_write_says_nothing(tmp_path: Path) -> None:
    """Cry-wolf half: the key is present ONLY on failure, or it becomes noise on every run."""
    source, destination, db = _library(tmp_path)

    done = _run(source, destination, db)

    assert isinstance(done, dict)
    assert "record_error" not in done


def test_both_surfaces_record_the_same_fields(tmp_path: Path) -> None:
    """One builder, so the two surfaces cannot drift - compared key by key, not spot-checked.

    ⚠ **This is the claim the move exists to make.** Before `(afu)` the app had no record at all,
    so "the surfaces agree" was vacuously true in the worst way. Comparing the full key sets means
    a field added for one caller cannot quietly not exist for the other.
    """
    source, destination, db = _library(tmp_path)

    _run(source, destination, db)
    from_app = _record(db)

    # The CLI's own payload, from the same builder both surfaces now call.
    from_cli = build_run_record(
        [],
        [],
        source=str(source),
        destination=str(destination),
    )

    assert from_app.keys() == from_cli.keys()
    app_run, cli_run = from_app["run"], from_cli["run"]
    assert isinstance(app_run, dict)
    assert isinstance(cli_run, dict)
    assert app_run.keys() == cli_run.keys()

    files = from_app["files"]
    assert isinstance(files, list)
    expected = {
        "source",
        "status",
        "detail",
        "landed_at",
        "planned_relative",
        "category",
        "confidence",
        "rule",
        "reason",
        "captured_at",
        "date_source",
        "date_tag",
        "needs_review",
        "sha256",
        "perceptual",
        "unreadable",
        "should_upload",
        "is_unique",
        "exact_duplicate",
        "near_duplicate",
    }
    assert files[0].keys() == expected, (
        "the per-file shape changed; both surfaces read this builder, so update the expectation "
        "deliberately rather than to make this pass"
    )


def test_every_mutating_app_run_is_accounted_for() -> None:
    """⚠ The four out of `(afu)`'s scope are recorded as absent WITH A REASON, not merely missing.

    §4's fifty-second member in spirit: a guard that checks only the surface that works says
    nothing about the four that do not, and silence there is what let `(afl)` ship on one surface.
    """
    service = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "service"
    for name, (writes, reason) in MUTATING_RUNS.items():
        module = service / f"{name}.py"
        assert module.is_file(), f"{name} is listed here and does not exist"
        source = module.read_text(encoding="utf-8")
        wires_it = "write_run_record" in source
        assert wires_it is writes, (
            f"service/{name}.py {'writes' if wires_it else 'does not write'} a run record, and "
            f"this table says the opposite. If that is deliberate, change the table and its "
            f"reason - recorded reason: {reason}"
        )
