# (adn) NOTHING STOPS TWO APPS RUNNING, AND QUITTING THE SECOND DELETES THE WAY BACK INTO THE FIRST.

*Body of backlog entry `(adn)`, under **Real, but conditional**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adn)** NOTHING STOPS TWO APPS RUNNING AGAINST ONE CATALOG. Recorded 2026-08-14, and it is
  the reason the schema fix had to be cross-process rather than an in-process lock. `(adh)`
  test (d) measured it: **launching twice gives two sidecars, two ports, two catalogs**, and
  `session-url.txt` names only one. Single-instance detection is listed there under *"the fixes,
  named as fixes and NOT as work done"* and does not exist; nor does the Rust shell, so there is
  nowhere to put it yet.

  Both sidecars resolve the same `default_catalog_path()`, so **two processes hold one catalog**,
  and a user reaches that by double-clicking twice. A third route needs no shell at all:
  `truestill organize` beside an open window.

  ⚠ **NARROWED 2026-08-22 BY `(aaw)`, AND RETITLED TO MATCH.** The old headline was *"nothing
  stops two apps running against one catalog"*, which stopped being the subject the day the
  cross-process lock shipped. A cross-process drive
  lock ships: two **mutating** operations on one drive cannot overlap, whichever process they are
  in, so *"two sets of in-flight writes"* to a drive is no longer reachable. **What this entry is
  still about is single-instance detection**, not write safety - two apps still launch, on two
  ports, with two sidecars, and `session-url.txt` still names only one. Non-job writes (the
  settings routes) remain outside the lock by design; that residue is `(adt)`'s.

  ## ⚠ ABSORBED FROM `(vv)` ON 2026-08-22, WHICH CLOSED ON THE MERGER

  `(vv)` was *"app per-drive job lock is process-local; CLI↔app overlap is not serialized"*. Its
  lock half shipped as `(aaw)`; **its residue is this entry's subject and is now recorded here**,
  because two entries describing one remaining problem is how one of them gets solved and the
  other stays open.

  **The session link makes a second instance worse than merely redundant** - `(vv)`'s own
  measurement, kept verbatim in shape:

  - `bind_listening_socket` tries `for candidate in (preferred, 0)` (`__main__.py:_attempt_browser`), so a
    second `truestill-app` whose preferred port is taken binds an **ephemeral** one and starts
    **successfully**, with its own `JobManager`. Double-clicking the icon twice is enough.
  - `session_link.write` is **replaced, never appended**, so the second instance overwrites the
    first's URL file - and the file is **removed when the process exits**, so quitting the second
    **deletes the link to the first, which is still running**. The ephemeral port is by then the
    only way in, and nothing records it.

  ⚠ **That is the part `(aaw)`'s lock cannot touch and was never meant to.** A drive lock stops
  two processes writing one library; it does not stop two processes existing, and it is the
  *existing* that loses the way back in. **This entry is now single-instance detection, whole.**

  **Correctness now rests on `BEGIN IMMEDIATE` alone**, which is genuinely cross-process and
  covers the schema race. What it does not do is stop two apps running - two job managers, two
  sets of in-flight writes, two things believing they own the library. See also `(abd)`.
