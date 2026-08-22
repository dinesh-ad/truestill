# (aeh) THE RUNNER IMAGE IS UNPINNED, SO THE apt THAT DEADLOCKS IS NOT A VERSION WE CHOSE.

*Body of backlog entry `(aeh)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aeh) THE RUNNER IMAGE IS UNPINNED, SO THE apt THAT DEADLOCKS IS NOT A VERSION WE CHOSE.**
  Recorded 2026-08-20 alongside `(aee)`'s fix. **A route with a cost, not a recommendation.**

    - ⚠ **BLAST RADIUS CHANGED 2026-08-22, AND NEITHER ENTRY COULD HAVE KNOWN.** Both were filed
    2026-08-20, inside the two-day window when the `e2e` job was `if: false` - so apt was not
    being invoked **at all**, and the cost being reasoned about was a lane that did not run. The
    job now runs **nightly and on `workflow_dispatch`** (`ci.yml`, re-decided 2026-08-22), so the
    hang costs a **scheduled** run rather than a push. Same defect, same remedy, different price:
    a nightly that dies at 03:17 is discovered the next morning by whoever looks, which is
    `ENGINEERING_STANDARD.md` §4's nineteenth member - *a guard that is silently cancelled is
    worse than one never scheduled, because the calendar says it ran.* **The urgency fell and the
    detection risk rose**, which are opposite movements and should be weighed as a pair.

  ## THE CONNECTION TO `(aee)`

  The hang is [LP#2003851](https://bugs.launchpad.net/bugs/2003851), a per-process queue deadlock
  in apt's retry machinery. **It is fixed upstream in apt 3.1.3 (June 2025), and it is
  noble-specific in practice** - noble/24.04 had not received the backport as of February 2026.
  `ci.yml` runs on `ubuntu-latest`, which is noble today.

  So the version of apt that deadlocks our lanes is **not a version anybody here selected**. It
  arrived with the image, and the fixed one will arrive the same way, whenever GitHub decides.
  Pinning is how that becomes a decision instead of an event.

  ## THE COST, WHICH IS THE REASON THIS IS FILED RATHER THAN DONE

  ⚠ **Pinning does not fix anything by itself.** `ubuntu-24.04` pinned is the same apt we have
  now. The value is only realised at the moment a fixed image exists and we move to it
  deliberately - which is a future action this entry does not perform.

  **And the migration is not free.** `ubuntu-latest` flipped from 22.04 to 24.04 in **January
  2025**, and the recorded experience is that teams *"are still discovering breakage months
  later"*: trimmed preinstalled tools, PEP 668 marking the system Python externally managed, and
  package versions changing between jammy and noble. Pinning trades an unscheduled break for a
  scheduled one - **which is the point, and it is still work.**

  ## THE HAZARD IT CLOSES, SEPARATELY FROM apt

  Even with no apt bug, `ubuntu-latest` moving to the next LTS without warning is its own risk,
  and it is the shape `(aee)` is already about: **a default nobody chose.** The three-OS matrix
  names `ubuntu-latest`, `macos-latest`, `windows-latest`, so the same argument applies to all
  three and the same cost does too.

  ## WHAT IS NOT DECIDED

  - **Whether to pin at all**, given the maintenance it creates: a pinned image must be moved by
    hand, and an image nobody moves is a different kind of stale.
  - **Whether to pin all three lanes or only Linux.** Only Linux has the apt argument; the other
    two would be pinned for the unscheduled-break argument alone.
  - ⚠ **Nothing here is measured.** No breakage has been attributed to an image flip in this
    repo - the argument is entirely from the recorded experience of others, and it should be read
    as that rather than as a local finding.
