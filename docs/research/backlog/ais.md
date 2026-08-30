# (ais) A GUARD THAT ONLY THE WINDOWS LANE CAN FAIL IS A GUARD NOBODY CAN ITERATE ON.

*Body of backlog entry `(ais)`, open in [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is
shared with [`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-08-30 (P146). **Not a product defect** - it is a defect in the instrument, and it has
now cost two red CI runs in two sessions from the same cause: *content written locally, tripping a
platform fact no local run can reach.*

## THE TWO INSTANCES, AND THEY ARE THE SAME SHAPE

| session | what tripped | seen by |
|---|---|---|
| P143 (`c81cb02`) | a test compared `str(Path.relative_to(drive))` - `Saved\2024\...` on Windows - against the POSIX form the catalog stores. Three tests failed **on the separator**, not on the product | Windows lane only |
| P145 (`ae506dc`) | a backlog entry added the first `❌` to `BACKLOG.md`; `❌` is `E2 9D 8C` and `0x9D` is unmapped in cp1252, which is what `text=True` decodes with on Windows | Windows lane only |

Both were **green under `make check`** on the machine they were written on, because a POSIX locale
is UTF-8 and a POSIX separator is `/`. Neither was a product bug. Both were found by CI minutes
after a push that had been reported as finished.

## 🔑 THE ASYMMETRY IS THE FINDING

P145 closed its half **on every lane**: `test_the_hook_reads_git_as_utf8_whatever_the_machine_locale_says`
swaps `text=True` for `encoding="cp1252"` and reproduces the Windows seam exactly - same byte,
same position - so it bites under Linux. That is the technique `(aic)` established
(`test_the_reply_survives_the_machine_locale.py`) and `(aif)` reached for from the other side.

**The separator half has no such instrument.** Nothing forces `os.sep` to `\` for a test, so the
class *"a test that compares a rendered path against a stored one"* is still detectable only by
pushing and waiting. One half of a single class is now guarded locally and the other is not, and
that asymmetry - rather than either instance - is what this entry is for.

## THE FIX SHAPE IS KNOWN, WHICH IS WHY THIS IS FILED RATHER THAN RESEARCHED

**Assert against the POSIX form the catalog stores, never `str(Path)`.** The catalog stores a
`relative` in POSIX form so a drive is readable on either OS (`LocalDestination.list` says so and
returns `path.relative_to(self._root).as_posix()`), so a test comparing against a catalog value
has exactly one correct spelling and `str(Path)` is never it.

Two candidate instruments, neither ruled here:

1. **A guard over the test corpus** - refuse `str(` applied to a `Path` in an assertion that also
   mentions a catalog column. Cheap, lexical, and would have caught P143 the day it was written.
   ⚠ It is a **new artifact that has to earn itself** (`(ago)`), and one instance is not the
   evidence for that; two instances of the *class* with only one half guarded is closer.
2. **A hostile-environment child**, the shape `(aic)` used - but `os.sep` is a C-level constant
   and cannot be moved by an environment variable, so this may not be reachable at all. If it is
   not, say so in the entry that closes this: *"the seam cannot be forced"* is a finding, and it
   is what makes instrument (1) the answer rather than a shortcut.

## WHY IT IS NOT URGENT, STATED SO NOBODY RANKS IT ABOVE A DATA DEFECT

Neither instance could reach a user: both were **test and document** defects caught by the gate
that exists for them. The cost is a red `main` and a fix-forward commit, not a lost photograph.
⚠ **But the cost is paid by the next person, not by the one who caused it** - a red tip refuses
the next push until someone runs `TRUESTILL_PUSH_ANYWAY=1`, and that override is exactly the habit
this repo should not be building.

## RELATED

`(aic)` (the locale door and the technique), `(aif)` (the xfail that got a Windows fact no local
run could reach), `(aim)` (P145, whose commit carried the second instance),
[`ENGINEERING_STANDARD.md`](../../ENGINEERING_STANDARD.md) §4 - an instrument silent in the case
it exists for.
