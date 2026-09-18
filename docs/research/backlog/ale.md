# (ale) `ROOT_CODE` IS A HAND-WRITTEN LIST, SO A NEW ROOT MODULE IS UNTYPED UNTIL SOMEBODY REMEMBERS.

*Body of backlog entry `(ale)`, under **Internal / tooling**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

**Filed 2026-09-18 (P252).** The instance is fixed in `0d57696`; **the class is not**, which is
why this is an entry rather than a line in a commit message.

## THE INSTANCE

`Makefile:17` reads, before that commit:

```make
ROOT_CODE := conftest.py suite_scratch.py
```

`source_region.py` was added at the repo root and **`make check` did not type-check it**. It
passed review only because mypy was run against it by hand. The fix was to append the filename -
which is the fix that will be needed again, by somebody who does not know the list exists.

**Checked, not assumed** (2026-09-18): `uv run mypy source_region.py` said *"Success: no issues
found in 1 source file"* while `make typecheck` at the same commit reported **76 / 172 / 78**
files across three platforms and none of them was it.

## WHY THIS IS A CLASS, AND THE CENSUS THAT ANSWERS IT

⚠ **The defect is not the missing entry, it is the DEFAULT.** A hand-written allowlist fails
**open**: a file nobody adds is silently exempt, and the gate is greenest exactly when coverage is
worst.

**Censused on the day of filing** rather than left for the next person -
`grep -nE '^(CORE|CLI|APP|SCRIPTS|PACKAGING|TEST_TREES|MYPY_PLATFORMS|ROOT_CODE) ' Makefile`:

| variable | enumerates | a new file is covered? |
|---|---|---|
| `CORE`, `CLI`, `APP` | one package source directory each | **yes** |
| `SCRIPTS`, `PACKAGING` | one directory each | **yes** |
| `TEST_TREES` | four test directories | **yes** |
| `MYPY_PLATFORMS` | three platform names, not paths | n/a |
| **`ROOT_CODE`** | **three FILENAMES** | **no** |

**So the class has exactly one member, and it is the one that bit.** Every other variable names a
directory, so a file added inside it is type-checked the day it lands. `ROOT_CODE` is the only
allowlist of files in the gate, and it exists because the repo root also holds files that are not
ours to check.

That result narrows the entry rather than widening it: this is a **one-site** fail-open, not a
pattern running through the Makefile - which is the difference between "fix it" and "build a
guard", and is why the shapes below are costed rather than chosen.

## THE SHAPES, COSTED, WITHOUT CHOOSING

- **Glob the root instead of listing it.** `ROOT_CODE := $(wildcard *.py)` covers every future
  sibling and costs nothing. ⚠ But it silently widens what the gate reads, and a root `.py` that
  is deliberately excluded would start failing with no record of why - so anything excluded needs
  to say so out loud.
- **A guard that asserts the list is complete.** A test comparing `*.py` at the root against
  `ROOT_CODE` and failing on a file in neither. Fails **closed**, keeps deliberate exclusions
  visible, and is one more artifact to maintain - `(ago)`'s bar applies, and one real miss is thin
  evidence for a new guard.
- **Leave it and record it.** What this entry does today.

## WHAT IS NOT PROPOSED

- **Which shape wins.** One real miss is thin evidence for a new guard, and `(ago)`'s bar asks a
  guard to earn itself. Recorded so the second miss is recognised as the second.
- **Touching the other six variables.** The census above says they do not have this defect.
