# (aeg) CACHE PLAYWRIGHT'S SYSTEM LIBRARIES SO `--with-deps` STOPS INVOKING apt AT ALL.

*Body of backlog entry `(aeg)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aeg) CACHE PLAYWRIGHT'S SYSTEM LIBRARIES SO `--with-deps` STOPS INVOKING apt AT ALL.**
  Recorded 2026-08-20, split out of `(aee)` at the moment `(aee)`'s fix landed. **This is the right
  long answer and it is not what was built**, so it is filed rather than implied.

  ## WHY IT IS THE RIGHT ANSWER

  `(aee)` bounds apt from outside because apt on noble cannot bound itself -
  [LP#2003851](https://bugs.launchpad.net/bugs/2003851), a per-process queue deadlock, unfixed on
  noble as of February 2026. **That contains the hang; it does not remove the dependency.** Every
  run still asks a mirror for packages it asked for last time, and the only reason the answer
  matters is that Playwright's installer shells out to `apt-get`.

  **`--with-deps` is the largest consumer and the one that actually cost the most:** it spent
  **43m33s** on run 32295312064 and was the step that made the `e2e` lane hit its 45-minute bound.
  The two exiftool steps are a single small package; this one pulls a browser dependency set.

  **Removing the call removes the class**, rather than bounding one more instance of it: no
  mirror, no 503, no deadlock, no retry, and a faster lane on every ordinary run as a side effect.

  ## ⚠ WHAT IT DOES NOT COVER, AND THIS IS THE REASON IT IS NOT THE WHOLE FIX

  **The `check` lanes still need exiftool**, which is an ordinary apt package on Linux and has no
  Playwright cache to hide in. So `(aee)`'s `scripts/ci_bounded.sh` stays regardless - this entry
  removes the biggest consumer, not the dependency on apt. Anyone reading this as "then we can
  delete the bound" has read it wrong.

  ## WHAT IS UNKNOWN, STATED RATHER THAN DESIGNED

  - **Which libraries `--with-deps` actually installs** has not been enumerated on the runner; the
    set is Playwright's business and changes with its version. The existing `Resolve playwright
    version` / `Cache browsers` steps already key on the version, so there is a shape to follow.
  - **Whether a cached apt archive or a prebuilt library set is the better carrier** is
    unmeasured. So is whether the runner image already carries most of them, in which case the
    honest fix may be smaller than a cache - possibly just dropping `--with-deps`.
  - ⚠ **No measurement exists for the ordinary-run cost of `--with-deps`**, only for the outage
    case. Building a cache to save time nobody has timed would be the wrong reason to do this; the
    reason is removing an apt call from the critical path.
