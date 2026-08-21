#!/usr/bin/env python3
"""Apply ONE mutation, run a command against it, restore, and refuse to do any of that silently.

`mutation_matrix.py` is for a whole suite; this is for the one-off proof you write while fixing
something - "does this guard actually fail if I put the defect back". Those were done inline with
`sed -i` and hand-rolled `str.replace`, and **that cost three false proofs in a single day**:

* `ruff format` reflowed a call across lines, so the anchor no longer matched. `sed` reported
  success, changed nothing, and the suite that ran next measured **unmutated code** and passed.
  A green from an unapplied mutation reads exactly like a guard that works.
* The same reflow defeated a `str.replace` patch, whose result was never checked.
* A third anchor missed after an unrelated edit moved the text.

Each time the evidence for "this guard bites" was a run against the original file.

**So every step here is verified rather than attempted**: the target must appear exactly once, the
file must actually differ afterwards, and the restore must return it byte for byte. A miss is
`exit 2` with the reason, never a shrug. The same reasoning as `mutation_matrix.py`'s stale and
ambiguous checks - "at least one match" and "exactly the one I meant" are different questions, and
only the second is being asked.

    uv run python scripts/mutate_once.py \\
        --file packages/truestill-app/src/truestill_app/server.py \\
        --old-file /tmp/old.txt --new-file /tmp/new.txt \\
        -- uv run pytest packages/truestill-app/tests/test_x.py -q

Exit codes: 0 the command failed (the mutation was CAUGHT - what you want), 1 the command passed
(the mutation SURVIVED - the guard does not bite), 2 the mutation could not be applied or restored.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True, help="the file to mutate")
    parser.add_argument(
        "--old-file", type=Path, required=True, help="file holding the exact text to replace"
    )
    parser.add_argument("--new-file", type=Path, required=True, help="file holding the replacement")
    parser.add_argument("--label", default="", help="what this mutation represents")
    parser.add_argument(
        "command", nargs=argparse.REMAINDER, help="-- command to run against the mutant"
    )
    args = parser.parse_args()

    command = [c for c in args.command if c != "--"]
    if not command:
        return _fail("no command given; pass it after `--`")

    # ⚠ THE CONTROL RUNS FIRST, ALWAYS, AND THERE IS NO FLAG TO SKIP IT. A mutation proof is a
    # claim that THIS test failed for THIS reason, and an exit code alone cannot support it: a
    # usage error, a suite that collected nothing and a genuine failure are all "non-zero". Three
    # proofs were void in a single session on 2026-08-21 because `pytest $TARGETS` with two paths
    # in an unquoted variable is not word-split by zsh, so pytest received one path that does not
    # exist, exited 4, and this script reported `mutation caught`. The tell was `no tests ran`, in
    # output nobody read. It is now the script's job rather than the reader's.
    refusal = _control_refusal(command)
    if refusal:
        return _fail(refusal)

    original = args.file.read_bytes()
    problem = _apply(args.file, original, args.old_file.read_text(), args.new_file.read_text())
    if problem:
        return _fail(problem)

    restored = False
    try:
        print(f"--- mutant applied{': ' + args.label if args.label else ''} ---", flush=True)
        result = _run(command, "mutant")
    finally:
        # No `return` in here: one would swallow whatever exception brought us to `finally`,
        # and a mutation run that dies deserves to say why before it reports anything.
        args.file.write_bytes(original)
        restored = args.file.read_bytes() == original
        print("--- restored ---" if restored else "--- RESTORE FAILED ---", flush=True)

    if not restored:  # pragma: no cover - filesystem failure
        return _fail(f"RESTORE FAILED for {args.file}; the mutant may still be on disk")

    if result.returncode == 0:
        print(f"\nMUTATION SURVIVED{': ' + args.label if args.label else ''} - nothing failed.")
        return 1

    return _kill_or_refusal(result, args.label)


#: pytest exits 4 for a usage error, 3 for an internal error, 2 for an interrupt and **5 when it
#: collected nothing**. None of those is a test failing, and every one of them is non-zero - which
#: is why an exit code alone cannot be the verdict.
_PYTEST_NO_TESTS_EXIT = 5
_PYTEST_NOT_A_RESULT_EXITS = frozenset({2, 3, 4, _PYTEST_NO_TESTS_EXIT})

#: The summary line pytest prints. Matched loosely on purpose: the point is to find a COUNT, not
#: to parse the whole line, and a command that is not pytest simply yields nothing here.
_OUTCOME = re.compile(r"(\d+) (passed|failed|error|errors)\b")


@dataclass(frozen=True, slots=True)
class _Verdict:
    """What a run actually did, as opposed to what its exit code implies."""

    #: ``True`` when tests demonstrably ran, ``False`` when they demonstrably did not, and
    #: ``None`` when the command is not pytest-shaped and there is nothing to read. Three states,
    #: because "cannot tell" must not be folded into either - the same reasoning `DriveReach`
    #: records for a drive that may simply never have been placed.
    tests_ran: bool | None
    summary: str
    diagnosis: str


def _run(command: list[str], what: str) -> subprocess.CompletedProcess[str]:
    """Run ``command``, showing its output and keeping it for inspection.

    Captured rather than streamed because the verdict below has to READ it. The output is printed
    afterwards so a person still sees everything they would have seen.
    """
    # ⚠ NO BYTECODE CACHE, AND THIS IS NOT A PERFORMANCE SETTING. CPython revalidates a `.pyc`
    # on the source's **size and whole-second mtime**, and a mutation cycle defeats both: the
    # control compiles the original, the mutant replaces it with a same-length line inside the
    # same second, and the interpreter runs the CACHED original. `ENGINEERING_STANDARD.md` §4's
    # forty-ninth member records that costing four minutes of reading correct code - and the
    # remedy it names, "run mutation cycles with PYTHONDONTWRITEBYTECODE=1", was a sentence
    # somebody had to remember. It is now the harness's job. Found by this script's own guard
    # test, which mutated `VALUE = 1` to `VALUE = 2` and watched the mutation survive.
    #
    # It stops the cache being WRITTEN, so the control cannot poison the mutant. A `.pyc` that
    # predates the whole run can still be read, which is the residual; purging `__pycache__`
    # under an arbitrary command's tree is not this tool's business.
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(command, check=False, capture_output=True, text=True, env=environment)
    print(f"--- {what}: {' '.join(command)}", flush=True)
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    return result


def _verdict(result: subprocess.CompletedProcess[str]) -> _Verdict:
    """Whether tests ran, read from the OUTPUT rather than inferred from the exit code."""
    text = f"{result.stdout}\n{result.stderr}"
    counts = {kind: int(n) for n, kind in _OUTCOME.findall(text)}
    executed = counts.get("passed", 0) + counts.get("failed", 0)
    summary = ", ".join(f"{n} {kind}" for kind, n in counts.items()) or "no pytest summary found"

    hint = (
        "If the command was built from a shell variable, quote it or pass the paths literally: "
        "zsh does NOT word-split an unquoted parameter, so `pytest $TARGETS` sends ONE argument "
        "that does not exist and pytest exits on a usage error. That is what made three proofs "
        "void on 2026-08-21."
    )
    if "no tests ran" in text or result.returncode == _PYTEST_NO_TESTS_EXIT:
        return _Verdict(False, summary, f"pytest collected nothing. {hint}")
    if executed:
        return _Verdict(True, summary, "")
    if result.returncode in _PYTEST_NOT_A_RESULT_EXITS:
        return _Verdict(
            False,
            summary,
            f"exit {result.returncode} is pytest refusing to run, not a result. {hint}",
        )
    # Not pytest-shaped. The control exiting 0 is then the whole of the evidence, and saying so is
    # better than inventing a stronger claim - `mutation_matrix.py` is the tool for a whole suite.
    return _Verdict(None, summary, "")


def _control_refusal(command: list[str]) -> str:
    """Run the command unmutated and return why the proof cannot proceed, or ``""``.

    Extracted so `main` stays under its return ceiling, and because the control is a claim in its
    own right: *this invocation runs these tests and they pass.* Everything after it is
    conditional on that, so it deserves a name rather than four inline branches.
    """
    control = _run(command, "control (unmutated)")
    verdict = _verdict(control)
    if control.returncode != 0:
        return (
            f"THE CONTROL FAILED (exit {control.returncode}) before anything was mutated, so the "
            f"invocation is broken and the mutant would prove nothing.\n{verdict.diagnosis}"
        )
    if verdict.tests_ran is False:
        return f"THE CONTROL RAN NO TESTS, so a red mutant would mean nothing.\n{verdict.diagnosis}"
    print(f"--- control OK: {verdict.summary} ---", flush=True)
    return ""


def _kill_or_refusal(result: subprocess.CompletedProcess[str], label: str) -> int:
    """Report a kill, or refuse to call a broken run one.

    ⚠ **A NON-ZERO EXIT IS NOT A KILL BY ITSELF.** The control already proved the invocation
    works, so a mutant that now reports "no tests ran" or a usage error means the **mutation**
    broke the run - a replacement that does not parse, say - rather than the guard catching it.
    Reporting that as a kill is the same false pass one step further along.
    """
    mutant = _verdict(result)
    if mutant.tests_ran is False:
        return _fail(
            "THE MUTANT RAN NO TESTS, so its non-zero exit is not a kill - the mutation most "
            f"likely broke the run itself.\n{mutant.diagnosis}"
        )
    print(
        f"\nmutation caught{': ' + label if label else ''} "
        f"(command exited {result.returncode}; {mutant.summary})"
    )
    return 0


def _apply(path: Path, original: bytes, old: str, new: str) -> str:
    """Replace ``old`` with ``new`` in ``path``, or return why it refused to.

    Every failure here is one that a plain `sed -i` reports as success.
    """
    hits = original.decode().count(old)
    if hits == 0:
        return (
            f"TARGET NOT FOUND in {path}.\n"
            "The text has moved or been reformatted - `ruff format` reflowing a call across lines "
            "is what defeated this three times. Re-read the file and copy the current text."
        )
    if hits > 1:
        return (
            f"TARGET AMBIGUOUS: {hits} matches in {path}.\n"
            "Add surrounding context. Editing an arbitrary one of several matches measures nothing."
        )
    path.write_text(original.decode().replace(old, new, 1))
    # VERIFIED, not assumed: a replacement producing identical bytes is not a mutation, and the
    # run that follows would be measuring the original.
    if path.read_bytes() == original:
        return "the file is unchanged after replacing; `old` and `new` are equivalent"
    return ""


def _fail(message: str) -> int:
    print(f"REFUSING: {message}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
