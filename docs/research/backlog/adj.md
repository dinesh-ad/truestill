# (adj) THE FREEZE IS NOT A REPRODUCIBLE TARGET: `truestill.spec` IS GITIGNORED.

*Body of backlog entry `(adj)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adj) THE FREEZE IS NOT A REPRODUCIBLE TARGET: `truestill.spec` IS GITIGNORED.** Recorded
  2026-08-14, found while deciding where the React bundle lands. The PyInstaller spec that decides
  what the shipped artifact contains is not in the repository - it is generated ad hoc and
  ignored - so **what ships is whatever the last person's spec said**, and nothing records it.

  Harmless while `static/` is a fixed set of files the spec happens to sweep. **It stops being
  harmless the moment `static/dist/` exists**: a built frontend that the spec does not collect
  produces a `.deb` that installs, launches, serves a page, and renders nothing - and no test in
  this repo would see it, because the e2e lane runs against the source tree rather than the
  package. Fix before the first `.deb` carrying React, not after.

  Found in the same look, and it took **three attempts to state correctly**, which is the part
  worth keeping. `packaging/truestill_freeze/` was called "a tracked empty directory" (git cannot
  track an empty directory), then "an untracked local leftover" (also wrong - two commits touch
  the path). What it actually is: `__init__.py` and `rthook_imagehash.py` lived there and were
  deleted in `e314de1`, and git leaves the emptied directory on disk because it only removes
  files. Harmless, and now gone.

  *Each wrong version was asserted from something real - `ls` output, then a clean `git status` -
  and neither was the question being asked.* Same proxy-answer failure as the token rename, in a
  one-line aside, twice.
