# (agx) `undo_migration` RAISES ON A VERIFICATION FAILURE AND THROWS AWAY WHAT IT ALREADY REVERSED.

*Body of entry `(agx)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

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
