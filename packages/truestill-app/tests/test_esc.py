"""(F42) ``esc`` must escape single quotes - single-quoted attributes already exist in app.js."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP_JS = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static" / "app.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def test_esc_escapes_single_quotes() -> None:
    """Execute the shipped ``esc`` from app.js; an unescaped apostrophe is the bug."""
    src = APP_JS.read_text(encoding="utf-8")
    match = re.search(r"^const esc = \(s\) => (.+);$", src, re.MULTILINE)
    assert match is not None, "esc definition not found in app.js"
    script = f'const esc = (s) => {match.group(1)};process.stdout.write(esc("O\'Brien <x> &"));'
    out = subprocess.check_output(["node", "-e", script], text=True)
    assert "'" not in out
    assert "&#39;" in out
    assert "&lt;" in out
    assert "&amp;" in out
