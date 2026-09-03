"""A `run:` step that pipes reads the status it means to, and a pwsh step checks what it calls.

Two facts about the runner decide this, both verified against its own documentation and issues
(actions/runner#353, github/docs#18933): a step with no `shell:` key runs `bash -e {0}` -
**pipefail off** - so `x="$(cmd | other)"` takes `other`'s status; and a `shell: pwsh` step exits
on the LAST native command's `$LASTEXITCODE` only, so a `uv run ...` line that is not the last
line and is not followed by a check cannot fail the step.

Found 2026-09-02 (P188): `release.yml` piped `ls | head` under the default shell, `ci.yml` piped
`playwright --version | awk` under it, and the Windows installer step ran `compare_selfcheck.py`
in pwsh with nothing reading its exit. Each was one word or one line from correct. This pins the
words. Widened 2026-09-02 (P189) to `& $native ...` calls, which the first version missed while
naming the class - and to a native call inside a pipeline, because a native command piped to a
cmdlet can leave `$LASTEXITCODE` unset (PowerShell/PowerShell#19848), so `| Out-Null` after an
installer discards the only status it has. Redirect to `$null` instead.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_WORKFLOWS = sorted((Path(__file__).resolve().parents[3] / ".github" / "workflows").glob("*.yml"))

#: A real pipe: `|` that is not half of `||`.
_PIPE = re.compile(r"(?<!\|)\|(?!\|)")
#: A pwsh line that invokes a native program - through uv, or with the call operator `&` on an
#: executable path; its exit code is what the step exists for. (`&` on a cmdlet is not native,
#: and none of the workflows does that.)
_NATIVE = re.compile(r"^\s*(uv run |& )")
#: A GUI-subsystem program started the one way pwsh promises to wait for it. Added 2026-09-03
#: (`(ajv)`'s dry run): `& Setup.exe ... > $null` followed by `$LASTEXITCODE` threw with an EMPTY
#: code, because pwsh neither waits for a GUI program nor sets `$LASTEXITCODE` for it. The
#: status a `Start-Process` line means to read is `.ExitCode`, and only with `-Wait -PassThru`.
_START = re.compile(r"^\s*\$\w+ = Start-Process ")


def _run_steps() -> list[tuple[str, str, dict[str, Any]]]:
    found = []
    for workflow in _WORKFLOWS:
        doc = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for job_name, job in doc["jobs"].items():
            default = ((job.get("defaults") or {}).get("run") or {}).get("shell")
            for raw in job.get("steps", []):
                if "run" in raw:
                    step = {**raw, "shell": raw.get("shell") or default or "(default)"}
                    found.append((workflow.name, f"{job_name}/{step.get('name', '?')}", step))
    return found


def _lines(step: dict[str, Any]) -> list[str]:
    """Logical lines: comments dropped, and a continuation (a trailing backtick in pwsh, a
    trailing backslash in bash) joined to the line it continues, so a six-line `pyinstaller`
    call is one command and its exit is the step's own."""
    logical: list[str] = []
    pending = ""
    for line in str(step["run"]).split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        pending = f"{pending} {line.strip()}" if pending else line
        if pending.rstrip().endswith(("`", "\\")):
            pending = pending.rstrip()[:-1]
            continue
        logical.append(pending)
        pending = ""
    if pending:
        logical.append(pending)
    return logical


def _bash_family(step: dict[str, Any]) -> bool:
    """Steps that run under bash on at least one lane: an explicit bash, or the default shell on
    a step that is not Windows-only (the default is pwsh only on Windows runners)."""
    if step["shell"] == "bash":
        return True
    return step["shell"] == "(default)" and "Windows" not in str(step.get("if", ""))


def test_a_step_that_pipes_under_bash_has_pipefail() -> None:
    offenders = []
    for workflow, name, step in _run_steps():
        if not _bash_family(step):
            continue
        piped = [line.strip() for line in _lines(step) if _PIPE.search(line)]
        if piped and step["shell"] != "bash" and "pipefail" not in str(step["run"]):
            offenders.append(f"{workflow} {name}: {piped[0]}")
    assert not offenders, (
        "a `run:` step pipes under the default shell, where pipefail is OFF and the pipeline's "
        "status is its last command's - add `shell: bash`, or `set -o pipefail`:\n"
        + "\n".join(offenders)
    )


def test_a_pwsh_step_reads_the_exit_of_every_native_call_it_makes() -> None:
    offenders = []
    for workflow, name, step in _run_steps():
        if step["shell"] != "pwsh":
            continue
        lines = _lines(step)
        for index, line in enumerate(lines):
            if _START.match(line):
                if "-Wait" not in line or "-PassThru" not in line:
                    offenders.append(
                        f"{workflow} {name}: {line.strip()}  (Start-Process without -Wait -PassThru)"
                    )
                elif index < len(lines) - 1 and ".ExitCode" not in lines[index + 1]:
                    offenders.append(
                        f"{workflow} {name}: {line.strip()}  (next line does not read .ExitCode)"
                    )
                continue
            if not _NATIVE.match(line):
                continue
            if _PIPE.search(line):
                offenders.append(
                    f"{workflow} {name}: {line.strip()}  (piped: $LASTEXITCODE may be unset)"
                )
            elif index < len(lines) - 1 and "$LASTEXITCODE" not in lines[index + 1]:
                offenders.append(f"{workflow} {name}: {line.strip()}")
    assert not offenders, (
        "a pwsh step invokes a native program and the next line does not read $LASTEXITCODE; "
        "pwsh does not stop on a native failure and the runner exits on the LAST code only:\n"
        + "\n".join(offenders)
    )


def test_the_scan_is_reading_real_steps() -> None:
    """Both workflows parsed, dozens of run steps, and pipes exist to judge - or every assertion
    above is over an empty set."""
    steps = _run_steps()
    assert len({w for w, _, _ in steps}) == 2, "both workflow files must contribute"
    assert len(steps) > 30, f"only {len(steps)} run steps parsed; the shape changed"
    piped = sum(1 for _, _, s in steps if any(_PIPE.search(line) for line in _lines(s)))
    assert piped >= 3, f"only {piped} piped steps found; the pipe regex has stopped matching"
    assert sum(1 for _, _, s in steps if s["shell"] == "pwsh") >= 3, "the pwsh steps were not seen"
