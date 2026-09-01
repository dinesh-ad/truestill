# (ajk) A CLASSIFIER GRADES A DECISION IT CANNOT READ, AND THE ONE DISCARDED ERRNO IS IN A DIFFERENT ARM

*Body of backlog entry `(ajk)`, under **Approved - still to build**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

Filed 2026-09-01 (P172) from `(aji)`'s corrected mechanism. **Read-only session: nothing here was
built.** Evidence at `/data/TruestillLibrary/aji-gone-probe-2026-09-01/`.

## ⚠ FIRST BLOCKER: THE `REFUSED` ARM DOES NOT REPRODUCE, AND NOTHING SHOULD BE BUILT UNTIL IT DOES

`(aji)` rests partly on `LocalDestination.exists` raising *"cannot probe ...: the filesystem
refused to describe it"* on a vanished drive. **Three attempts, 2026-09-01, none reproduced it:**

| attempt | method | result |
|---|---|---|
| 1 | `reach()` on a path under an unmounted exFAT loop volume | `missing`, `raw stat errno=2 (ENOENT)`, **no raise** |
| 2 | the same, with an active writer holding the volume busy | **identical** - `missing`, ENOENT |
| 3 | **a real `truestill organize --apply`**, 300 files, `unmount --force` at 41 landed - the soak's exact shape | **257 failures, every one `"is no longer the drive this run started on"`. Zero `cannot probe`.** |

`ENOENT` is in `path_reach._ABSENT_ERRNOS`, so `reach()` answers `Reach.MISSING` and `exists()`
returns `False` **without raising**. Some other errno produced `REFUSED` in soak twelve and
**it is unknown.**

**What was eliminated**: the loop device (the soak used one too), a busy volume (attempt 2), and
the catalog living on the same volume (`--db` was on `/data/tmp` in both). **What was not**:
whether the *device* went versus the *mountpoint*, and the mount options.

🔑 **So no change to what the classifier does with a live guard is warranted yet.** The last
mechanism filed here without reproducing it - `(aji)`'s - was wrong.

## WHAT *IS* ESTABLISHED, FRESHLY MEASURED

Attempt 3 reproduces `(aji)`'s **corrected** mechanism end to end: **257 failures, one condition,
the guard firing correctly on every file, and the run not stopping.** That is precisely the
*"N failures describing one condition"* that `persists_for_the_run`'s own `NO_SPACE` branch calls
the reason to stop.

## THE CENSUS

### Six call sites, and three of them can be handed something unreadable

`persists_for_the_run` is called at `backup.py:301`, `backup.py:339`, `organizer.py:2118`,
`migrate.py:1340`, `migrate.py:1569` and `undo.py:467`. **Null: none in `truestill-cli` or
`truestill-app`** - it is core-only, and `underlying_oserror` has no caller outside
`drive_unwritable.py`.

Three are structurally safe: both `backup` sites are handed a bare `OSError` captured by
`safe_copy`, and `undo.py:467` sits under `except OSError`. **The exposed three are
`organizer.py:2118`, `migrate.py:1340` and `migrate.py:1569`.**

🔑 **AND `migrate` ALREADY BUILT THE ESCAPE HATCH, NARROWLY.** Both its call sites read
`if persists_for_the_run(exc) or isinstance(exc, VerificationFailedError):` - an explicit
exemption for the one causeless raise its author hit. **`organizer.py:2118` has no disjunct at
all.** The precedent for *"some refusals are not the classifier's to grade"* is already in the
tree, applied to one class by someone who met this wall and did not generalise it.

### The raise sites, and why the pairing's premise is false

Of **22** raises of `DestinationError` or a subclass in core, **exactly one discards an available
`OSError`**:

| site | what it refuses | an `OSError` to chain? |
|---|---|---|
| **`destinations/local.py:154`** `exists()` | `Reach.REFUSED` | ⚠ **YES, and it is discarded** - `reach()` returns a verdict only, and `probe()` returns `tuple[Reach, os.stat_result \| None]`: **the stat, not the error** |
| `destinations/base.py:88` `DestinationDevice.check` | device id != latched baseline | **NO** - `device_of` swallows the error and returns `None`; this is a comparison |
| `destinations/base.py:118,121` `check_contained` | path shape (absolute, anchored, `..`) | **NO** - pure string analysis, no syscall |
| `destinations/base.py:233,241,246,251` `Destination` ABC | backend does not support adopt / relocate / remove / checksum | **NO** - capability refusal |
| `destinations/local.py:231` `relocate` | `source.is_file()` is False | **NO** - a boolean test |
| `organizer.py:1965` preflight | `preflight.may_proceed` is False | **NO** - a computed verdict, and raised *before* the loop |
| `migrate.py:1098,1489` `VerificationFailedError` | hash mismatch after relocate | **NO** - deliberate, and compensated by the `isinstance` disjunct |
| ten sites in `local.py` | write-path failures | already `from exc` / `from outcome.error` |

⚠ **THE FRAMING THIS ENTRY WAS COMMISSIONED UNDER IS FALSE, AND THAT IS THE FINDING.** The brief
read *"give `DestinationError` a cause and `persists_for_the_run` starts seeing `GONE`."* **You
cannot give `check`'s raise a cause - there is no exception object at that point.** So the two
halves are not *the raise and the classifier*. They are:

1. **a classifier asked to grade a DECISION** it can only read by errno (`check`), and
2. **a genuinely discarded errno in a different arm** (`exists`), whose reachability is unproven.

⚠ **A cheap fix that does not exist, checked rather than assumed.** It was suggested that `check`'s
raise carries a `__context__` (being inside `local.py`'s `try:`/`except OSError`), so the walker
could read that instead. **Measured: raising inside a `try` block sets neither `__cause__` nor
`__context__` - both are `None`.** There is nothing to walk.

### Two more blind spots, named and not chased

* **`MetadataBakeError`** (`organizer.py:1123`, raised `:1296`) **is** an `OSError`, so the walk
  stops on it - but it is built with one string argument, so `errno is None` and
  `classify_unwritable` answers `OTHER`. It classifies as non-persistent by construction.
* **`undo.py:402-403`** (`_why_not`) catches `OSError` from `sha256_file` and returns `UNREADABLE`
  **without consulting the classifier at all**, so an `EIO` on the pre-flight read is silently
  per-file.

## THE CANDIDATE RULING - RECORDED, DELIBERATELY NOT RULED

**Blocked on the reproduction above.** Written down so the next session does not re-derive it:

> A `DestinationError` raised by `DestinationDevice.check` should **bypass**
> `persists_for_the_run` rather than be classified by it.

`persists_for_the_run` is an errno classifier - its own docstring says *"Keyed on `errno`, never
on `winerror`"* - and `check` has no errno. It has a decision already taken by a guard whose whole
purpose is to take it. Three supports, **none of which depends on the unreproduced arm**:

* **The same guard already stops the run in `backup`** (`_copy_missing` calls
  `run.device.check(run.target)` at the top of each iteration, outside any `try`) and does not in
  `organize`. One guard, two behaviours, neither documented as deliberate.
* **`migrate`'s existing `isinstance` disjunct** is this idea, applied to one class.
* **The 257-failure measurement** above.

⚠ **Why the tempting alternative is refused.** Synthesising an `OSError` at `check` so the
classifier can read it: `backup._stop_the_run` does construct one -
`raise OSError(verdict.error.errno, verdict.detail) from verdict.error` - **but only because it
has a real errno to copy**, and its docstring says exactly that. At `check` there is none, so any
construction **invents evidence** - the same refusal `(ajg)` made when it declined to print a
count the type could not supply. And routing it through `GONE` collides with `(aji)`'s probe,
which says `GONE` must not persist.

## ⚠ A SECOND INSTRUMENT DOUBT, FOUND HERE AND NOT CHASED

Both the soak and attempt 3 printed *"2 distinct reasons in total"*, but attempt 3's
`last-run.json` holds **one** distinct failure detail across all 257.
`cli._print_capped` computes it as `len({_reason_key(r.detail or "") for r in results})`. **Why it
said two is not determined.** It does not weaken the soak evidence - that printed both messages
*literally* rather than deriving a count - but the number should not be used as evidence until
someone looks.

## RELATED

`(aji)` (the corrected mechanism, and the `GONE` ruling this must not collide with),
`(ajg)` (the refusal-to-invent precedent), `(agi)` (the classifier itself),
`(ajj)` (the other half of the same reading).
