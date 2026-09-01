# (aji) A VANISHED DRIVE FAILS 1,130 FILES ONE AT A TIME, AND THE RULE THAT ALLOWS IT IS JUSTIFIED BY ANOTHER COMMAND'S WIRING

*Body of backlog entry `(aji)`, under **Approved - still to build**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-09-01 (P170) from [`soak-twelve-record.md`](../../soak-twelve-record.md) 12b, **and
ruled from the code rather than from the soak** - the soak raised the question, four reads and one
measurement answered it.

## THE OBSERVATION

`organize` onto a drive unmounted mid-run failed **1,130 of 1,324 files individually**, each
recorded and named, exit 1. Two lines above the rule that permits this, the `NO_SPACE` branch of
`persists_for_the_run` calls exactly that shape the reason to stop: *"At that point every
remaining file fails, so continuing buys N failures describing one condition."*

## 🔑 THE RULING: A THIRD THING. THE GUARD IS CORRECT AND ITS JUSTIFICATION IS NOT

**Two independent reasons the run does not stop, and only the second is about `GONE` at all.**

### 1. The `GONE` branch is never evaluated, because the exception carries no cause

`organizer` reaches the destination through `destination.exists(...)` **before** any write
(`organizer.py:1068`, `:1074`, `:1472`). On a vanished root that raises:

```python
message = f"cannot probe {relative_path!r}: the filesystem refused to describe it"
raise DestinationError(message)          # local.py:153 - note: no `from`
```

**Measured 2026-09-01**, not reasoned about:

```
underlying_oserror(DestinationError("cannot probe ...")) -> None
persists_for_the_run(...)                                -> False
```

`persists_for_the_run` walks `__cause__` for an `OSError`, finds none, and returns `False` **at
its first guard**. Every branch below - `NO_SPACE`, `QUOTA`, `FAILING`, `REFUSED`, `GONE` - is
dead for this exception.

⚠ **The cause is lost further down than it looks.** `exists()` cannot chain what it never had:
it calls `reach()`, which returns a verdict alone, and `reach` calls `probe`, whose signature is
`tuple[Reach, os.stat_result | None]` - **the stat, not the error**. The `OSError` is discarded
inside `probe`. Giving this exception a cause is therefore a change to `path_reach`, not a `from`
on one line.

### 2. And with a cause it would still not stop - which is where the justification fails

Measured: `persists_for_the_run` on a `DestinationError` chained to `ENOENT` also returns
**`False`**, because `GONE` deliberately does. The comment stating why:

> ⚠ **`GONE` is deliberately here rather than above.** A vanished *source* is one file somebody
> moved. A vanished *destination* does persist - and `DestinationDevice.check` already fails
> closed on exactly that, **at the top of every loop**, so a second guard here would be two checks
> for one condition.

🔑 **That sentence is TRUE of `backup` and FALSE of `organize`, and it is applied to both.**

| command | where `DestinationDevice.check` sits | is it "at the top of every loop"? |
|---|---|---|
| `backup` | `_copy_missing` calls `run.device.check(run.target)` explicitly, per iteration, before the copy | ✅ **yes** - and `backup` does stop |
| `organize` | inside `LocalDestination._make_parent`, reached only from `upload`/`adopt`/`relocate` | ❌ **no** - `exists()` raises first, so `check` is never reached |

**The guard is not broken. The reasoning that made `GONE` non-persistent for every caller was
derived from one caller's wiring** and filed in a module both use. That is the defect, and it is a
documentation-and-scope defect rather than a logic one - which is why the fix is not obvious.

## ⚠ WHAT IS **NOT** RULED, AND WHAT WOULD SETTLE IT

**Whether `GONE` should persist.** Not decided here, and deliberately not fixed on the strength of
one soak.

The argument against is real and is this module's own posture: `run_health`'s docstring calls
crying wolf *"the failure mode to fear"*, and `persists_for_the_run` says an errno nobody has
reasoned about returns `False` because *"continuing is the recoverable mistake and aborting a good
run is not."* A `GONE` that persists ends a run on one bad reading.

**What would settle it, in order of cost:**

1. **Whether a `GONE` reading is ever transient in the field.** `run_health._GONE_ERRNOS` already
   splits definite-gone (`ENOENT`, `ENOTCONN`, `ENODEV`, `ESTALE`) from momentarily-unhappy, and
   `DeviceReading.definite` exists for exactly this distinction - **so the vocabulary is already
   there and unused on this path.** If a definite reading is never transient, `GONE` can persist
   with no cry-wolf risk. Nobody has measured a mount that returns `ENOENT` and recovers.
2. **Whether striking would do instead of persisting.** `RunHealth` already requires **3 strikes
   spanning 15 s** before declaring a drive gone. Routing `exists()`'s refusal into that counter
   rather than into the persistence table gets the stop without the single-reading risk, and reuses
   a mechanism that has already been tuned.
3. ⚠ **Whether `RunHealth` can even fire on a short run.** Measured in 12b: the whole 1,324-file
   run took **~6 s**, and the watcher's floor is 15 s. **On a run this size the backstop cannot
   engage at all** - so "the watcher will catch it" is not an answer for small libraries, and that
   is worth knowing before anyone leans on option 2.

## WHAT IS ESTABLISHED, SO IT IS NOT RE-DERIVED

- `DestinationDevice.check` **is** wired on organize's write path (`_make_parent`), and it is
  correct there. It is simply behind a read that fails first.
- `exists()`'s `DestinationError` is **causeless**, and the cause is discarded in `probe`.
- `persists_for_the_run` returns `False` for this exception **twice over** - once for want of a
  cause, once by the `GONE` ruling. **Fixing either alone changes nothing.**
- The 1,130 failures were each recorded and named, so **nothing was lost and nothing was
  misreported** by the CLI. The cost is noise and a long wait, not damage - which is why this is
  filed and not fixed in the same session.

## RELATED

`(agi)` (the persistence classifier), `(aiq)` (the same run, on the app side - and its
*"nothing at all on a stop"* mechanism is the one this shows is not reached),
`(ajg)` (the surface half of the same soak), `(abn)` (repair),
[`soak-twelve-record.md`](../../soak-twelve-record.md) 12b.
