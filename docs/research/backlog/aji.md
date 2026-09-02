# (aji) A VANISHED DRIVE FAILS 1,130 FILES ONE AT A TIME, AND THE RULE THAT ALLOWS IT IS JUSTIFIED BY ANOTHER COMMAND'S WIRING

*Body of backlog entry `(aji)`, under **Real, but conditional**. The index is
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

## ⚠ CORRECTION 2026-09-01 (P171): THE MECHANISM BELOW IS WRONG ON ITS LOAD-BEARING CLAIM

**This entry said `DestinationDevice.check` is never reached on organize's per-file path, because
`exists()` raises first. THE PRESERVED EVIDENCE SAYS OTHERWISE, and it was in the transcript this
entry was written from.** `cli_van2.err`, line 4 - **the very first failure of the run**:

```
FAILED: Canon EOS 100D.jpg: /run/media/<user>/S12V2 is no longer the drive this run started
on -- it looks like the drive was disconnected or unmounted. ...
```

🔑 **That is `check`'s own sentence. The guard IS reached, and it fires first.** The tail confirms
two arms, not one: *"and 1,116 more FAILED (**2 distinct reasons in total**)"* - the device guard,
then `cannot probe` for the files after it.

**So the real mechanism is sharper than the one below, and worse.** The guard fires **correctly**,
per file, and `_record_failure_or_stop` then hands its exception to `persists_for_the_run`, which
returns `False` because a `DestinationError` carries **no `__cause__`**. **A correctly-firing
stop-the-run guard is downgraded to a per-file failure and re-fired 1,130 times.** The
classifier's blindness is not a latent gap next to the mechanism - it **is** the mechanism.

⚠ **AND ONE THING IS NOW UNKNOWN THAT THIS ENTRY ASSERTED.** It claimed `exists()`'s `cannot
probe` arm fires on a vanished root. **Measured twice on 2026-09-01 and it does not**: a path
under a removed mountpoint answers `ENOENT`, which is in `_ABSENT_ERRNOS`, so `reach()` returns
`Reach.MISSING` and `exists()` returns `False` **without raising** - with and without an active
writer. So some *other* errno produced `REFUSED` in the soak and **I have not reproduced it**.
Named as unknown rather than guessed.

**What survives unchanged**: `persists_for_the_run` returns `False` for these exceptions, the run
does not stop, and `(aji)`'s ruling that `GONE` must not persist stands on its own measurement.
**What is retracted**: *"`check` is never reached"*, and the table below that contrasts `backup`
with `organize` on that basis. The original is kept beneath rather than deleted, because the
correction is only legible next to what it corrects.

## 🔑 THE RULING: A THIRD THING. THE GUARD IS CORRECT AND ITS JUSTIFICATION IS NOT (AS FILED - SEE THE CORRECTION ABOVE)

**Two independent reasons the run does not stop, and only the second is about `GONE` at all.**

### 1. The `GONE` branch is never evaluated, because the exception carries no cause

`organizer` reaches the destination through `destination.exists(...)` **before** any write
(`organizer.py:_free_relative`, `:1074`, `:1472`). On a vanished root that raises:

```python
message = f"cannot probe {relative_path!r}: the filesystem refused to describe it"
raise DestinationError(message)          # local.py:LocalDestination.exists - note: no `from`
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
| `organize` | inside `LocalDestination._make_parent`, reached only from `upload`/`adopt`/`relocate` | ✅ **yes, and it fires first** - then `persists_for_the_run` downgrades it to one failure per file; see the correction above |

**The guard is not broken. The reasoning that made `GONE` non-persistent for every caller was
derived from one caller's wiring** and filed in a module both use. That is the defect, and it is a
documentation-and-scope defect rather than a logic one - which is why the fix is not obvious.

## 🔑 RULED 2026-09-01 (P171): `GONE` SHOULD **NOT** PERSIST, AND THE MEASUREMENT IS WHY

**The question named as the one that would settle it was taken.** *Is a definite `GONE` reading
ever transient?*

**Instrument**: `aji-probe/probe.py`, preserved at
`/data/TruestillLibrary/aji-gone-probe-2026-09-01/`. An exFAT loop volume, `read_device` sampled
every 2 ms on its own thread, while the volume was unmounted and remounted underneath - which is
what a user replugging a stick produces.

```
samples=1203  alive=713  gone(definite)=490  gone(INDEFINITE)=0
unmount at t+0.065s, remount at t+1.126s
definite-gone window: 1.057s
DID A DEFINITE-GONE READING LATER RECOVER? YES
distinct device ids seen while alive: [29, 1816]
```

🔑 **YES. A definite reading recovered after 1.057 s.** `definite` does not mean *permanent*; it
means *the path is genuinely not there right now*. **So making `GONE` persist on a single reading
would abort a healthy run on a one-second blip** - the cry-wolf `run_health`'s docstring calls
*"the failure mode to fear"*, now with a number against it rather than a worry.

⚠ **Two further readings, neither of which was predicted:**

* **`gone(INDEFINITE)` was ZERO.** The `definite` split - the vocabulary this entry hoped to reuse
  - produced no uncertain reading at all in the scenario it exists for. It distinguishes nothing
  here, which is worth knowing before anyone builds on it.
* **Two device ids appeared while the path was readable: `1816` and `29`.** The volume, and the
  filesystem *underneath* its mountpoint. So a stat can succeed and describe **the wrong
  filesystem** - which is precisely the "ordinary empty directory" hazard `DestinationDevice`
  exists for, observed directly. `check` handles it correctly by comparing against a latched
  baseline; nothing else on the per-file path does.

### What follows, and what does not

* ❌ **Do not add `GONE` to `persists_for_the_run`.** Measured cry-wolf.
* ❌ **Do not fix the causeless raise at `local.py:LocalDestination.exists` for this purpose.** `(aji)` established that
  both would have to change or neither does anything; the ruling is **neither**. The causeless
  raise remains a real blind spot in the classifier and is now the only live half - it should be
  filed on its own merits, not as a step toward a persistence change that is not happening.
* ✅ **The mechanism that fits the measurement is STRIKING, and it already exists.** `RunHealth`
  requires 3 strikes spanning 15 s, which would ignore a 1.06 s blip and catch a real removal.
  Routing `exists()`'s refusal into that counter is the shape to build.
* ⚠ **And that mechanism is inert where it is most needed.** Measured in soak twelve 12b: the
  1,324-file run took **~6 s** against a 15 s span. **On a small library there is no backstop at
  all**, so "the watcher will catch it" cannot be the whole answer. Any build must lower the floor
  or count strikes per FILE rather than per tick.

## ⚠ WHAT WAS NOT RULED BEFORE P171, KEPT AS THE READING IT WAS

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
