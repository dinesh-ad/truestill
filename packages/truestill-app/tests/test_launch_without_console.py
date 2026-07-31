"""Launching with no console must not kill the app ((aad)).

**The bug.** A double-clicked desktop app has no console: `pythonw.exe`, a PyInstaller
``--noconsole`` build and a packaged GUI app all leave ``sys.stdout`` and ``sys.stderr`` set to
``None``. ``uvicorn.run`` then configures its default logging, whose formatter asks the stream
whether it is a terminal::

    ValueError: Unable to configure formatter 'default'
      caused by AttributeError: 'NoneType' object has no attribute 'isatty'

The process dies **before the server binds**. No window, no error, nothing to report - the user
sees "nothing happens when I open it", which is the least diagnosable failure there is, and the
one that would arrive by email rather than as a bug report.

**What was *not* the bug, checked rather than assumed.** ``print()`` is a silent no-op when
``sys.stdout`` is ``None`` - it does not raise. So the console writes never needed guarding;
they degrade quietly on their own. The crash is entirely uvicorn's logging configuration, which
is why the fix replaces that config instead of wrapping every write in a try block.

**Where startup output goes when there is no console: nowhere, for now, and deliberately.**
Dropping it is honest at this step - there is no channel yet, and inventing one here would
duplicate the durable home the URL file gives it next. What matters is that the *decision* is
stated rather than inherited from `print`'s accidental behaviour.
"""

from __future__ import annotations

import logging
import logging.config
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn
from truestill_app.__main__ import main, uvicorn_log_config


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    """``dictConfig`` mutates global logging state; put it back so the suite stays isolated."""
    saved = logging.root.manager.loggerDict.copy()
    yield
    logging.root.manager.loggerDict.clear()
    logging.root.manager.loggerDict.update(saved)


def _no_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exactly what a windowed build hands the interpreter.

    **A plain helper, called in the test body - deliberately not a fixture.** pytest's capture
    plugin re-assigns ``sys.stdout`` / ``sys.stderr`` for the call phase, *after* fixture setup
    runs, so a fixture that sets them to ``None`` is silently undone before the test starts.
    Written as a fixture first, three of the tests below passed without the condition ever
    being applied - green while testing nothing, which is the failure mode the guard rules
    exist for. Verified: fixture-set reads ``False``, body-set reads ``True``.
    """
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)


def test_the_log_config_applies_with_no_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole bug, hermetically. No browser, no bundler, no packaging step needed."""
    _no_console(monkeypatch)

    logging.config.dictConfig(uvicorn_log_config())


def test_uvicorns_own_default_is_what_crashes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cry-wolf half: proves the guard above is aimed at a real defect, not a hypothetical.

    If uvicorn ever stops sniffing the stream, this fails and the custom config can be deleted
    rather than carried forever as unexplained ceremony.
    """
    _no_console(monkeypatch)

    with pytest.raises(ValueError, match="formatter"):
        logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)


def test_startup_reaches_the_server_without_a_console(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end through `main`, stopping where the real process would block on the socket."""
    _no_console(monkeypatch)
    served: dict[str, object] = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: served.update(kw, app=app))

    code = main(["--db", str(tmp_path / "c.sqlite"), "--no-browser"])

    assert code == 0
    assert served, "the server was never reached"
    assert served["log_config"] == uvicorn_log_config(), "uvicorn's tty-sniffing default was used"


def test_a_console_still_gets_its_log_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Surviving no console must not mean silencing logging for everyone who has one.

    Without this, replacing the config with a NullHandler unconditionally would pass every other
    test here while making a terminal run mute - a fix that hides the next bug.
    """
    monkeypatch.setattr(sys, "stderr", sys.__stderr__)

    handler = uvicorn_log_config()["handlers"]["default"]

    assert handler["class"] == "logging.StreamHandler"
    assert handler["stream"] == "ext://sys.stderr"


def test_no_console_uses_a_handler_that_writes_nowhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """The other half of the branch, so neither side can rot unnoticed."""
    _no_console(monkeypatch)

    assert uvicorn_log_config()["handlers"]["default"]["class"] == "logging.NullHandler"
