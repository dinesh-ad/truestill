"""A catalog held by another process is a refusal, not a traceback.

The condition is ordinary: an ``--apply`` run in a terminal while the app is open. SQLite
serialises the two, so nothing is corrupted -- the second writer waits out ``busy_timeout``
and raises ``sqlite3.OperationalError: database is locked``, which was caught nowhere.

**Two real processes, deliberately.** A mocked exception proves the handler runs; it cannot
prove the condition arises, which is the half that was never checked. So the holder is a
separate interpreter taking a real ``BEGIN IMMEDIATE`` lock, and the CLI is a real
``python -m truestill_cli`` that has to discover it the way a user would. The cost is the 5 s
``busy_timeout`` the CLI waits out before it gives up, and that wait *is* the behaviour under
test -- shortening it would test something else.

**Measured 2026-08-09, because these two are the slowest tests in the suite and someone will
come for them.** 5.45 s and 5.37 s, and the answer is still no: the 5 s is
``sqlite3.connect(timeout=5.0)``'s default, so it is the product's wait rather than a test-side
sleep, and a test that did not wait it out would not be testing the refusal.

What changed is that it stopped mattering. Serially these were 10.8 s of a 90 s suite - 12%, the
single biggest concentration in it. In parallel the suite is ~16 s and these run alongside
everything else, so they cost close to nothing. **They do set the floor**: no amount of hardware
takes the suite below ~5.5 s while the slowest single test is 5.45 s. That is the number to
remember if the suite ever needs to be faster than that, and nothing else here is worth touching
first.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from truestill_cli import cli
from truestill_cli.cli import CATALOG_BUSY_EXIT, CATALOG_UNWRITABLE_EXIT, main
from truestill_core.catalog import Catalog
from truestill_core.catalog_busy import CATALOG_BUSY_MESSAGE, is_catalog_busy
from truestill_core.layout import LAYOUT_TEMPLATE_KEY

#: Takes the RESERVED lock and nothing else. `BEGIN IMMEDIATE` alone is enough to block a second
#: writer, so the holder never has to know this schema -- it stays correct across migrations.
_HOLDER = textwrap.dedent(
    """
    import sqlite3, sys
    conn = sqlite3.connect(sys.argv[1], timeout=1.0)
    conn.execute("BEGIN IMMEDIATE")
    print("HELD", flush=True)
    sys.stdin.readline()
    """
)


@pytest.fixture
def catalog_path(tmp_path: Path) -> Path:
    """An existing, migrated catalog -- so the run under test fails on the lock, not on setup."""
    path = tmp_path / "catalog.sqlite"
    with Catalog(path):
        pass
    return path


def _hold(path: Path) -> subprocess.Popen[str]:
    child = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert child.stdout is not None
    assert child.stdout.readline().strip() == "HELD", "the holder never took the lock"
    return child


def _release(child: subprocess.Popen[str]) -> None:
    assert child.stdin is not None
    assert child.stdout is not None
    child.stdin.write("\n")
    child.stdin.close()
    child.stdout.close()
    child.wait(timeout=30)


def _config_write_while_held(path: Path) -> subprocess.CompletedProcess[str]:
    """Run a real `truestill config --preset` against a catalog a second process is holding.

    `config` is the cheapest command that genuinely writes: one `set_setting`, no source tree,
    no confirmation prompt. What is under test is the write meeting the lock, not the command.
    """
    holder = _hold(path)
    try:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "truestill_cli",
                "config",
                "--db",
                str(path),
                "--preset",
                "year-event",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    finally:
        _release(holder)


def test_a_catalog_another_process_holds_is_refused_with_a_next_step(catalog_path: Path) -> None:
    result = _config_write_while_held(catalog_path)

    assert result.returncode == CATALOG_BUSY_EXIT, result.stderr
    assert CATALOG_BUSY_MESSAGE in result.stderr
    # The defect itself, asserted directly: the user saw a traceback for a normal condition.
    assert "Traceback" not in result.stderr
    assert "OperationalError" not in result.stderr


def test_the_refusal_leaves_the_setting_it_would_have_written_untouched(
    catalog_path: Path,
) -> None:
    """Nothing written -- asserted on the catalog, not inferred from the exit code."""
    result = _config_write_while_held(catalog_path)

    assert result.returncode == CATALOG_BUSY_EXIT, result.stderr
    with Catalog(catalog_path) as catalog:
        assert catalog.get_setting(LAYOUT_TEMPLATE_KEY) is None


def _real_error(kind: str, path: Path) -> sqlite3.Error:
    """A genuine sqlite exception of ``kind``, raised by the module rather than constructed.

    Hand-built exceptions carry no ``sqlite_errorcode`` at all, so a test that made its own
    would agree with any implementation -- including one that discriminates on message text,
    which is the thing being ruled out.
    """
    first = sqlite3.connect(path, timeout=0.1)
    first.execute("CREATE TABLE IF NOT EXISTS probe (x)")
    first.commit()
    second = sqlite3.connect(path, timeout=0.1)
    try:
        if kind == "busy":
            first.execute("BEGIN IMMEDIATE")
            second.execute("INSERT INTO probe VALUES (1)")
        else:
            second.execute("SELECT * FROM no_such_table")
    except sqlite3.Error as exc:
        return exc
    finally:
        first.close()
        second.close()
    unreachable = f"no {kind} error was produced"
    raise AssertionError(unreachable)


def test_a_busy_catalog_is_recognised_by_its_error_code(tmp_path: Path) -> None:
    busy = _real_error("busy", tmp_path / "busy.sqlite")
    assert busy.sqlite_errorname == "SQLITE_BUSY"
    assert is_catalog_busy(busy)


def test_an_ordinary_sqlite_failure_is_not_dressed_up_as_a_busy_catalog(tmp_path: Path) -> None:
    """Cry-wolf half. A disk error or a broken schema must keep its traceback.

    `OperationalError` covers faults that will never clear, and telling someone to wait for
    another operation to finish sends them to wait out a bug. The message *"database is
    locked"* is the only honest tell in the text, and matching it would have been the obvious
    implementation -- so the discrimination is pinned on the code that distinguishes them.
    """
    ordinary = _real_error("other", tmp_path / "other.sqlite")
    assert isinstance(ordinary, sqlite3.OperationalError)  # the same class as a busy catalog
    assert ordinary.sqlite_errorname == "SQLITE_ERROR"
    assert not is_catalog_busy(ordinary)


def test_the_cli_re_raises_a_sqlite_failure_that_is_a_bug_rather_than_a_condition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cry-wolf half at the surface: only a real condition is converted.

    ``SELECT * FROM no_such_table`` is ``SQLITE_ERROR`` -- a bug of ours, not something the user
    can act on. It keeps its traceback, and that survived the 2026-08-22 change that gave the
    *unwritable* family a refusal of its own: the test below is the one that pins the family, and
    this is the one that pins the boundary of it. `(afe)`

    Patched on `truestill_cli.cli`, the module that *owns* `_cmd_config` -- `main` resolves it
    as a module global when it builds the dispatch table, so this reaches the real call
    (ENGINEERING_STANDARD.md §4, the aiming rule).
    """
    ordinary = _real_error("other", tmp_path / "other.sqlite")

    def explode(_args: object) -> int:
        raise ordinary

    monkeypatch.setattr(cli, "_cmd_config", explode)
    with pytest.raises(sqlite3.OperationalError):
        main(["config"])


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="chmod 555 does not deny the owner on Windows; this refusal has no Windows equivalent",
)
def test_a_catalog_that_cannot_be_written_is_refused_rather_than_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """⚠ The §9 hole this closed: a real read-only catalog used to reach the terminal as a stack.

    The failure is produced by ``chmod`` rather than constructed, so the code under test sees the
    same extended code SQLite really raises.
    """
    directory = tmp_path / "ro"
    directory.mkdir()
    conn = sqlite3.connect(directory / "c.sqlite")
    conn.execute("CREATE TABLE probe (x)")
    conn.commit()
    directory.chmod(0o555)
    try:
        conn.execute("INSERT INTO probe VALUES (1)")
        conn.commit()
    except sqlite3.Error as exc:
        unwritable = exc
    else:  # pragma: no cover - the chmod above did not deny the write
        pytest.fail("the catalog directory was made read-only and SQLite still wrote to it")
    finally:
        directory.chmod(0o755)
        conn.close()

    def explode(_args: object) -> int:
        raise unwritable

    monkeypatch.setattr(cli, "_cmd_config", explode)
    code = main(["config"])

    assert code == CATALOG_UNWRITABLE_EXIT
    assert code != CATALOG_BUSY_EXIT, "a fault must not exit as the condition that clears itself"
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert CATALOG_BUSY_MESSAGE not in err
    assert "could not write to the library catalog" in err
    # `config` writes no photos, so the refusal must not describe a run that placed any. `(aen)`
    assert "what it did" not in err


def test_a_busy_catalog_at_the_same_surface_is_converted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of the pair above: same seam, same injection, opposite verdict.

    Without this, the re-raise test passes just as happily against a `main` that converts
    nothing at all.
    """
    busy = _real_error("busy", tmp_path / "busy.sqlite")

    def explode(_args: object) -> int:
        raise busy

    monkeypatch.setattr(cli, "_cmd_config", explode)
    assert main(["config"]) == CATALOG_BUSY_EXIT
