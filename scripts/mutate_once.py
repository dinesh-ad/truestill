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
import subprocess
import sys
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

    original = args.file.read_bytes()
    problem = _apply(args.file, original, args.old_file.read_text(), args.new_file.read_text())
    if problem:
        return _fail(problem)

    restored = False
    try:
        print(f"--- mutant applied{': ' + args.label if args.label else ''} ---", flush=True)
        result = subprocess.run(command, check=False)
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
    print(
        f"\nmutation caught{': ' + args.label if args.label else ''} (command exited {result.returncode})"
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
