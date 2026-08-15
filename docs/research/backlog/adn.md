# (adn) NOTHING STOPS TWO APPS RUNNING AGAINST ONE CATALOG.

*Body of backlog entry `(adn)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adn) NOTHING STOPS TWO APPS RUNNING AGAINST ONE CATALOG.** Recorded 2026-08-14, and it is
  the reason the schema fix had to be cross-process rather than an in-process lock. `(adh)`
  test (d) measured it: **launching twice gives two sidecars, two ports, two catalogs**, and
  `session-url.txt` names only one. Single-instance detection is listed there under *"the fixes,
  named as fixes and NOT as work done"* and does not exist; nor does the Rust shell, so there is
  nowhere to put it yet.

  Both sidecars resolve the same `default_catalog_path()`, so **two processes hold one catalog**,
  and a user reaches that by double-clicking twice. A third route needs no shell at all:
  `truestill organize` beside an open window.

  **Correctness now rests on `BEGIN IMMEDIATE` alone**, which is genuinely cross-process and
  covers the schema race. What it does not do is stop two apps running - two job managers, two
  sets of in-flight writes, two things believing they own the library. See also `(abd)`.
