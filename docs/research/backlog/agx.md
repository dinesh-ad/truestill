# (agx) `undo_migration` RAISES ON A VERIFICATION FAILURE AND THROWS AWAY WHAT IT ALREADY REVERSED.

*Body of entry `(agx)`. **SHIPPED 2026-08-24.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ✅ SHIPPED 2026-08-24 (P56)
>
> `undo_migration` returns a `MigrationStop` instead of raising, reusing the forward path's kinds
> and classification unchanged. Both surfaces report it through **one** reporter.
>
> ⚠ **Two things this entry did not know, found by verifying rather than inheriting it.** The raise
> had **widened** - `(agm)` stopped `_matches` swallowing `DestinationError`, so `checksum` on a
> failing drive was a second, unclassified escape - so the handler covers the whole row's I/O, not
> the write half. And the CLI's undo **returned `0` whatever happened**, including for the refusals
> it was already printing: the exit-code defect `(agm)` fixed forward, still live in reverse.
>
> **The data claim held**, re-checked: `relocate` is a COPY and every catalog write is downstream
> of the verify, so a stop leaves the catalog naming where the file really is.
>
> ## Q314 - what this does to `(agm)`
>
> **`(agm)` is smaller than filed, on its migrate half.** It asks whether migrate should write a
> run record, and one of the two things a record must describe - *how a run ended* - now exists on
> **both** directions as `MigrationStop(kind, reason, never_attempted)`, already worded by both
> surfaces. A record builder needs an adapter over an outcome that carries its own ending, rather
> than a new vocabulary invented for the record. **The bake half is untouched by this and unchanged.**

- **(agx) `undo_migration` RAISES ON A VERIFICATION FAILURE AND THROWS AWAY WHAT IT ALREADY
  REVERSED.** Filed 2026-08-24 while writing `(agm)`'s missing tests - **found by auditing the
  fix, not the feature**, which is where the asymmetry became visible.
  - **The mechanism.** `migrate.py:840` raises `VerificationFailedError` when a file no longer
    hashes to what the migration recorded. The loop keeps `done` and `refused` in locals, so the
    raise unwinds the frame and **both are lost**: a reversal that put 900 files back and then
    met one bad file reports **nothing it did**. The caller sees an exception, not an outcome.
  - 🔑 **THE FORWARD PATH WAS THE OUTLIER AND IS NOW THE MODEL - THE ASYMMETRY HAS FLIPPED.**
    Before `(agm)`, `run_migration` raised the same way and `undo_migration` was the one that
    named its refusals. `(agm)` gave the forward path a `MigrationStop` and a `refused` list;
    the undo still raises. **One direction of one feature now reports partial work and the other
    does not**, which is worse than both being wrong, because a reader who checks one concludes
    the pattern is followed.
  - **This is `(agj)`'s shape**, quoted from its own closure: *"a stopped organize took its own
    paperwork down with it."* Same defect, different surface.
  - ⚠ **WHAT IS NOT AT RISK, so the entry is not overstated.** The docstring's other promise
    holds and is deliberate: *"a failed verify raises and leaves both the file and its journal
    row intact"*. Nothing is moved, nothing is deleted, the row stays, and a re-run resumes -
    `test_migrate.py` covers that. **The loss is the report, not the data.**
  - **The fix's shape, not designed here**: mirror the forward path. Return
    `UndoOutcome(reversed_files=..., refused=[...])` with a stop rather than raising, reusing
    `MigrationStop` and `MigrationStopKind` - which already exist and already carry the
    cancel/ground-moved/could-not-continue split. `undo.UndoOutcome.stopped` is the precedent one
    module over, and its own field comment explains why a field beats an exception here: the
    loop already owns and returns the whole outcome, so there is no frame to lose.
  - ⚠ **ITS RAISE PATH HAS ZERO COVERAGE TODAY**, checked rather than assumed:
    `grep -rn "verification failed after putting" packages/*/tests/` returns nothing, and no test
    constructs a hash mismatch against `undo_migration`. **So whoever builds this writes the
    failing test first** - and it must assert the partial outcome, never today's raise.
  - **Deliberately not pinned by a test in the meantime.** A test asserting the current raise
    would encode the behaviour this entry proposes to change, and the next person would have to
    delete it. `test_migrate_matches_returns_false_when_checksum_is_unreadable` cost exactly that
    in `(agm)`: it pinned a *mechanism* rather than a *promise*, and had to be rewritten.
