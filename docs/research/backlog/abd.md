# (abd) ONE CATALOG OR MANY - the question is unanswered, and it may be the wrong default.

*Body of backlog entry `(abd)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(abd) ONE CATALOG OR MANY - the question is unanswered, and it may be the wrong default.**
  Recorded 2026-08-05. **Ranked above the three entries below it.** The question, not a ruling:
  a user who keeps library A and library B deliberately apart gets one catalog, and every
  library-wide number sums across both.
  - **What the code does.** `app_paths.default_catalog_path` resolves, per call: `--db` if
    given; else `./reports/catalog.sqlite` **if a working directory was "chosen"**; else
    `TRUESTILL_DATA_DIR` or `platformdirs.user_data_dir`. "Chosen" is
    `sys.stdout is not None or sys.stderr is not None` - *was this launched from a terminal* -
    because a double-clicked app inherits a meaningless directory. **The destination is never
    consulted.** The catalog is a property of how you launched, not of what you organized into.
  - **THREE CONSEQUENCES, recorded separately because they need different fixes.**
    1. **Wrong totals.** Every reporting surface sums across both libraries - the custody strip,
       Stats, `truestill status`, `where`/Find.
    2. **PRIVACY, and this is the sharpest one for a product whose pitch is custody.** Working in
       A reveals B through: the custody strip; Stats totals, the per-drive table naming B's drive
       **label**, and `undated_samples` / `zero_drive_samples`, which are real filenames; the
       Backups cards (label, path hint, counts); **Find and `truestill where`, whose query joins
       `drives` and selects `d.label` with no drive filter at all**; `truestill status`; and the
       startup banner. There is no active-library concept and no scoping control anywhere.
    3. **DEDUP REFUSES THE SECOND COPY - behavioural, not cosmetic, and neither the maintainer
       nor this agent anticipated it.** `DedupIndex` seeds from catalog content, so the same
       photo organized into library B after library A is an exact duplicate of itself and is
       **skipped**. Deliberately keeping one photo in two separate libraries does not work at
       all. A user would read this as Truestill silently refusing to copy their file.
  - **`--db` separation is genuinely clean.** Two catalogs share nothing: no totals, no leak, no
    cross-library dedup. The whole problem is the default, not the architecture.
  - **Separation is possible and undocumented.** `--db` on both surfaces, or
    `TRUESTILL_DATA_DIR`. Neither is presented as a multi-library feature - `--db`'s help says
    "SQLite catalog", and the env var is documented as a *test-isolation* override. Forgetting
    the flag once merges the two permanently.
  - **PRIOR ART - WEB RESEARCH SUPPLIED BY THE MAINTAINER, not repo evidence and not verified
    by this agent, which has no web access. Treat it as his findings, recorded verbatim:**
    - **Adobe's own docs** tell users to work with the same catalog every time, and Lightroom
      experts call deliberate splitting unnecessary and "a recipe for total confusion".
    - **But the reported pain is almost entirely ACCIDENTAL multiplication** - users with
      fourteen catalogs they never meant to create, or jumping between catalogs after a machine
      change and losing work already done. The deliberate case is a defended minority: one
      catalog per drive so a single drive can travel.
    - **Immich and PhotoPrism answer it differently** - per-user private libraries - and
      PhotoPrism has an open, unresolved discussion asking for exactly that.
  - ⚠ **Truestill's per-directory behaviour is closer to Lightroom's accident than to anyone's
    intent.** `reports/catalog.sqlite` was picked up because the app ran from the repo. The
    same install, double-clicked, would have used the OS data directory. Nothing warns that the
    answer changed.
  - **Is one catalog a recorded decision? NO - checked, and this is the finding.** `DECISIONS.md`
    holds D1-D9 and **none is about catalog scope**. The nearest, D8, argues "one catalog column,
    one verification identity, no setting that splits a library's custody record" - that is about
    *hash algorithms*, not libraries. `IMPLEMENTATION_STANDARDS.md` §3's "Single SQLite file" is
    the *no-server, stdlib-sqlite3* choice in context. No research doc examines it; no backlog
    item raised it before this one. **The architecture assumes one library per machine and the
    code serves that assumption well, but nobody weighed it.**
  - **THE SHAPE A RULING WOULD TAKE - noted, deliberately NOT made.** On the evidence above, one
    catalog is likely the right default; **accidental multiplication is the disease**, not
    deliberate separation; and today's launch-mechanism resolution is closer to Lightroom's
    accident than to anyone's intent. What still has to be answered: is one-catalog-per-machine
    the intended product with `--db` as the escape hatch, is a named-library concept wanted, or
    is the per-directory pickup itself the bug? All three are consistent with today's code.
    **Post-launch.**
