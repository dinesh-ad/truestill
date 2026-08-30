"""A path turned into a string goes through ``as_posix()``, never ``str()``. `(ais)`

**Two red CI runs in two sessions came from prose and test code tripping a platform fact no local
run could reach.** This closes the separator half; P145 closed the encoding half.

**The measured instance.** `c81cb02` shipped a test whose `_on_disk` built
``sorted(str(p.relative_to(drive)) ...)`` and compared it against the catalog's ``relative``
column. The catalog stores that column in **POSIX form** so a drive is readable on either OS
(`destinations/local.LocalDestination.list` produces it with `as_posix`), so on the Windows lane
the left side read ``Saved\\2024\\...`` and three tests failed on the separator rather than on
anything the product did. Fixed in `cdbe7da`; nothing stopped the next one.

🔑 **THE SEAM CAN BE FORCED HERE, so this is a guard and not an `xfail`.** `PureWindowsPath` is
available on every platform and renders exactly as the Windows lane does - it is the same class
`WindowsPath` inherits `__str__` and `relative_to` from. That makes this the encoding half's
situation, not `(aid)`'s: a separator is a **string decision in our own code**, where a colon's
legality is a filesystem driver's and cannot be forced at all. `test_the_windows_rendering_is_what
_took_the_lane_red` below reproduces the defect on Linux, byte for byte.

⚠ **A `skipif(sys.platform != "win32")` WOULD BE WORSE THAN NOTHING, and that is not a stylistic
preference.** It is silent on the lane where it is written, so it cannot fail in front of the
person introducing the bug - which is precisely how this half survived while the encoding half was
being fixed beside it. `test_unreadable_source.py` is the proof: a module-level `pytestmark` for
three tests that `chmod` also exempted three that do not, and one of those three sat comparing
``str(p.relative_to(src))`` against ``"sub/a.jpg"`` where no lane could ever run it.

⚠ **WHAT THIS DOES NOT COVER, stated so nobody reads it as "platform differences are handled".**
It sees **separators only**, and only where the rendering is lexically adjacent to the
`relative_to` call. It does not see:

* a `relative_to` result bound to a variable and stringified later - `p = x.relative_to(y)` then
  `str(p)` is invisible to it, and no AST rule short of type inference would catch that;
* `str()` over any *other* `Path`, which is usually correct and sometimes not;
* **case-insensitivity** (NTFS and APFS fold case; `migrate.py` handles it deliberately and
  nothing guards the rest), **drive letters**, **reserved device names** or **trailing dots** -
  `layout.py` defends those for token values only, which is `(aid)`'s subject;
* **`text=True` on a subprocess**, the encoding half - `check_entry_closure.py` and
  `test_closed_entries_leave_the_backlog.py` own that one.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath

REPO = Path(__file__).resolve().parents[3]


def _tracked_python() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=REPO,
        capture_output=True,
        # UTF-8 rather than `text=True`, which decodes with the machine locale - cp1252 on
        # Windows. The sibling half of this entry, and a guard that trips over it is a joke.
        encoding="utf-8",
        errors="surrogateescape",
        check=True,
    ).stdout
    files = [REPO / line for line in out.splitlines() if line]
    assert files, (
        "`git ls-files '*.py'` matched nothing, so this guard has no subject and would report "
        "zero offences in zero files - ENGINEERING_STANDARD.md 4's silent instrument."
    )
    return files


def _is_relative_to_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "relative_to"
    )


def _offences(tree: ast.AST) -> list[tuple[int, str]]:
    """Every ``str(x.relative_to(y))`` and ``f"{x.relative_to(y)}"`` in one module.

    Parsed with `ast`, not a regex, for `test_subprocess_has_one_home.py`'s stated reason: a
    docstring or a comment mentioning the shape must not fail this, and a call spread over
    several lines must not escape it. This file's own docstring contains both spellings.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "str"
            and len(node.args) == 1
            and _is_relative_to_call(node.args[0])
        ):
            found.append((node.lineno, "str(...relative_to(...))"))
        if isinstance(node, ast.FormattedValue) and _is_relative_to_call(node.value):
            found.append((node.lineno, 'f"{...relative_to(...)}"'))
    return found


def test_no_rendered_relative_path_carries_the_platform_separator() -> None:
    """THE GUARD, and it bites on every lane rather than waiting for a push.

    The fix at every site is `.as_posix()`. There is **no allowlist**, deliberately: a
    diagnostic message is also better rendered the same way on every platform, and an exemption
    list is how the next instance gets in - which is the whole subject of this entry.
    """
    offences = [
        f"{path.relative_to(REPO).as_posix()}:{line}: {what}"
        for path in _tracked_python()
        for line, what in _offences(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    ]

    assert not offences, (
        "a path rendered with the platform's separator:\n  "
        + "\n  ".join(sorted(offences))
        + "\n\nUse `.as_posix()`. `str()` on a Path gives `a\\b` on Windows and `a/b` "
        "everywhere else, and the catalog stores every `relative` in POSIX form so a drive is "
        "readable on either OS. Comparing the two is what took the lane red on `c81cb02`."
    )


def test_the_windows_rendering_is_what_took_the_lane_red() -> None:
    """🔑 **THE SEAM, FORCED ON THIS LANE** - the answer to "can we do what P145 did here?"

    `PureWindowsPath` renders exactly as the Windows lane does, on Linux and macOS. So the
    divergence this guard exists for is reproducible in-process, and the guard's premise is
    demonstrated rather than asserted. This is the direct analogue of swapping `text=True` for
    `encoding="cp1252"`, and it is available for the same reason: **both are decisions our own
    code makes about a string**, unlike `(aid)`'s colon, which a filesystem driver decides and
    which therefore stayed an `xfail`.
    """
    drive = PureWindowsPath(r"C:\Drive")
    landed = drive / "Saved" / "2024" / "2024-01" / "p.jpg"
    stored = "Saved/2024/2024-01/p.jpg"  # what the catalog holds, on every platform

    # ⚠ **BOUND TO A NAME FIRST, AND THAT IS THIS GUARD'S OWN BLIND SPOT USED ON PURPOSE.**
    # Written inline as `str(landed.relative_to(drive))` the guard above would flag it - correctly,
    # since it cannot tell the one place where rendering a relative with the platform separator is
    # the *subject* from the many where it is a mistake. Exempting this file was the alternative
    # and is worse: an allowlist entry covers every future line in it too. The limit is stated in
    # the module docstring and pinned by `test_the_variable_form_is_a_stated_blind_spot`.
    rendered = landed.relative_to(drive)

    assert str(rendered) == r"Saved\2024\2024-01\p.jpg"
    assert str(rendered) != stored, "the defect is not reproducible here"
    assert rendered.as_posix() == stored, "the fix does not hold"

    # And the fix is a no-op where it was already right, which is why it can be applied blanket.
    posix = PurePosixPath("/Drive") / "Saved/2024/2024-01/p.jpg"
    assert posix.relative_to("/Drive").as_posix() == stored


def test_the_guard_is_actually_reading_code() -> None:
    """Cry-wolf, inverted: it must find the shape when the shape is there.

    Without this, a guard that silently parsed nothing - a bad glob, an exception swallowed -
    would report a clean repo forever. `ENGINEERING_STANDARD.md` 4's silent instrument again.
    """
    caught = _offences(
        ast.parse(
            "import pathlib\n"
            "def f(p, root):\n"
            "    a = str(p.relative_to(root))\n"
            "    b = f'{p.relative_to(root)}:1'\n"
            "    ok = p.relative_to(root).as_posix()\n"
            "    fine = str(p)\n"
            "    return a, b, ok, fine\n"
        )
    )

    assert [line for line, _ in caught] == [3, 4], f"the guard read the wrong lines: {caught}"
    assert len(caught) == 2, "as_posix() or a bare str(Path) was reported as an offence"


def test_the_variable_form_is_a_stated_blind_spot() -> None:
    """⚠ **THE LIMIT, PINNED RATHER THAN DESCRIBED.** A docstring cannot go stale into a test.

    `p = x.relative_to(y)` then `str(p)` is the same defect and this guard cannot see it: the
    rendering is no longer lexically adjacent to the call, and telling a `Path` from a `str` at
    that distance needs type inference, not an AST walk. **Asserted here so the module docstring's
    claim is checkable** - and so anyone who later teaches the guard to see it has a failing test
    telling them to delete this one.
    """
    blind = _offences(
        ast.parse("def f(p, root):\n    tail = p.relative_to(root)\n    return str(tail)\n")
    )

    assert blind == [], (
        "the guard now sees the variable form - good; update the module docstring's limits and "
        "remove this test, which exists only to keep that claim honest"
    )
