# (aja) A RE-RUN REPAIRS NOTHING AN INTERRUPTION BROKE, BECAUSE THE ROW WRITTEN TOO EARLY SAYS THERE IS NOTHING TO DO.

*Body of entry `(aja)`, **shipped 2026-08-31** - the closure is in [`SHIPPED.md`](../../SHIPPED.md);
the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

Filed 2026-08-31 (P166, soak eleven), **measured on real removable media** under a **physical
mid-write pull**. The run is [`soak-eleven-record.md`](../../soak-eleven-record.md).

## THE PATH A PERSON WALKS, WHICH IS THE FINDING

> `organize --apply` said **2062 organized**. **1,223 were true.**
> The stick was pulled. **836 photographs are now zero bytes.**
> The obvious remedy - plug it back in, run it again - reported
> **"2,068 already on this drive"** and **exit 0**, and **repaired nothing**.
> Only `truestill verify` dissents, and only if the user knows to run it.

**Every automatic path reports success.**

## MEASURED

Re-run, same source, same destination, stick re-inserted:

```
     2069  duplicate, skipped        467  organized
       11  organized (renamed)             2,068 already on this drive
RERUN EXIT=0
```

Re-stat'ed **cold**, against the recorded list of the 839 paths damaged by the pull:

```
STILL ZERO-LENGTH : 836      STILL MISSING : 2      now non-empty : 1
```

**838 of 839 are exactly as the pull left them.** The one "now non-empty" was never zero - it is
the size-correct, content-wrong file, and it is still the wrong bytes.

## 🔑 THE MECHANISM: THE CLAIM DEFENDS ITSELF

`(aiz)` established that the custody claim is written **before** the bytes reach the medium. This
is the second half: **the row then suppresses its own repair.** Dedup asks `file_copies` whether a
copy exists on this drive; `file_copies` is precisely what the interruption falsified; so the
files most in need of re-copying are exactly the ones reported as `already on this drive`.

⚠ **THE RE-RUN'S ARITHMETIC IS INTERNALLY HONEST, WHICH MAKES IT WORSE.** `467 + 11 = 478` is
**exactly** the `478 not attempted` the interrupted run reported. **It converged perfectly on work
it had never started and not at all on work it had recorded wrongly.** Those are two different
properties and only the first holds - so a reader who checks the numbers concludes it worked.

## WHY THIS RANKS ABOVE `(aiz)` RATHER THAN INSIDE IT

`(aiz)` is a **window**: bad for the duration of a write, and nothing is lost unless something
interrupts it. This is **permanent**: once the interruption has happened, the state is
self-stabilising. **The remedy a user would reach for first is the one that confirms the damage
rather than fixing it**, and it does so with a zero exit code.

## ⚠ ON NTFS THE RE-RUN DOES NOT LIE - IT DIES. NEITHER CONFIRMED NOR REFUTED THERE

Same stick, same pull, NTFS instead of exFAT. After `ntfsfix` cleared the dirty flag, the
convergence `backup --apply` **crashed on its first `mkdir`**:

```
OSError: [Errno 22] Invalid argument:
  '.../backup/2014/2014-08/2014-08-14 - Wayanad Monsoon 2014/2014-08-15'
  File ".../backup.py", line 478, in _copy_missing
    dst.parent.mkdir(parents=True, exist_ok=True)
```

**The run never reaches the dedup branch this entry is about.** One directory's MFT record is
unusable - every `stat`, `ls` and `mkdir` under it returns `EINVAL`, while the identical name
creates fine at the volume root, so it is corruption and not `(ajc)`'s character set.

⚠ **So this entry's mechanism is UNTESTED on NTFS**, and the user's position there is different
without being better: on exFAT they are told everything is fine; on NTFS they are shown a stack
trace and given no way forward. **That crash is `(ajd)`, not this entry.** What can be said is that
`_files_missing_on_target` compares catalog rows against `copies_on_drive` - **both sides are the
catalog, the disk is never consulted** - so the mechanism is filesystem-independent by
construction; it simply could not be reached to prove it.

## WHAT IS NOT ESTABLISHED

- **Whether dedup should verify before trusting a row.** Re-hashing every recorded copy on every
  run is the obvious answer and is **plainly too expensive** - it is `verify`'s whole cost, paid
  on every organize. **A size check is nearly free and would have caught 836 of 839** (that is
  `(ajb)`, and the two entries are separable: this one is about who dedup asks, that one is about
  what `rescan` compares).
- **Whether the trigger should be the interruption rather than the run.** A run that ends in
  `RunStoppedError` or a non-zero exit knows the drive misbehaved; nothing records that against
  the drive, so the next run starts innocent. **A "this drive was interrupted, verify before
  trusting it" flag is a candidate and is not ruled here.**
- **Whether `(ain)`'s ruling reaches this.** *"Keep the file and record it, never roll it back"*
  was decided for a copy that had **committed**. These rows describe copies that never landed.
  Whether the ruling extends to them is a real question and this entry does not answer it.
- **Every other destination.** Measured on one exFAT stick under one pull. NTFS journals and may
  differ; rclone, SMB and NFS were not touched.

## RELATED

`(aiz)` (the window this is the far side of), `(ajb)` (the cheap detector that would have seen it),
`(ain)` (false custody from the errno side), `(abn)` (repair, still unbuilt - and this is the
strongest case yet made for it),
[`soak-eleven-record.md`](../../soak-eleven-record.md) §4.
