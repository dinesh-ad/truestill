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
    ⚠ *Corrected 2026-08-23, `(aea)`: the description above died with `(adw)` on 2026-08-19 -
    the legacy path and the launched-from-a-terminal gate are both retired, and today's
    resolution (`app_paths.py:245`) is override-else-data-dir, identical for a double-click and
    a terminal run. Consequences 1 and 2 below are untouched by that and stay this entry's
    weight.*
  - **The disclosure pipe already exists - do not rebuild it** (recorded 2026-08-23, `(aea)`).
    `CatalogChoice.note` is rendered by `format_startup_lines` (`catalog_startup.py:369`) on
    every non-`--db` boot, pinned by
    `test_a_choice_note_is_its_own_line_and_an_empty_one_is_silent`; nothing sets it since
    `(adw)`. Whatever this entry rules, the surface half of "say which library and why" is
    built and waiting.
  - **THREE CONSEQUENCES, recorded separately because they need different fixes.**
    1. **Wrong totals.** Every reporting surface sums across both libraries - the custody strip,
       Stats, `truestill status`, `where`/Find.
    2. **PRIVACY, and this is the sharpest one for a product whose pitch is custody.** Working in
       A reveals B through: the custody strip; Stats totals, the per-drive table naming B's drive
       **label**, and `undated_samples` / `zero_drive_samples`, which are real filenames; the
       Backups cards (label, path hint, counts); **Find and `truestill where`, whose query joins
       `drives` and selects `d.label` with no drive filter at all**; `truestill status`; and the
       startup banner. There is no active-library concept and no scoping control anywhere.
    3. ✅ **CLOSED IN FACT BY `(aei)` ON 2026-08-20 (`e20dbf5`), recorded here 2026-08-22 by a
       whole-backlog re-read. Neither entry cited the other.** The text below is kept as written
       because it was true when written and is the reason the consequence was ranked where it was.
       `organizer._scope_to_destination` now scopes dedup per **destination** rather than per
       catalog, so two libraries on two registered destinations each receive their copy; pinned by
       `test_a_fresh_second_destination_receives_the_files`. ⚠ **This closes the CONSEQUENCE, not
       the entry** - `(aei)` was a fix for organizing onto a second *drive* and knew nothing about
       two libraries; that it also repaired this is a property of the remedy being right rather
       than of anyone connecting them. **Items 1 and 2 are untouched and are now the whole of this
       entry's weight.**
       > **DEDUP REFUSES THE SECOND COPY - behavioural, not cosmetic, and neither the maintainer
       > nor this agent anticipated it.** `DedupIndex` seeds from catalog content, so the same
       > photo organized into library B after library A is an exact duplicate of itself and is
       > **skipped**. Deliberately keeping one photo in two separate libraries does not work at
       > all. A user would read this as Truestill silently refusing to copy their file.
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

## Prior art - how four products handle two catalogs for one install (researched 2026-08-23, moved here from `(aea)`'s close)

- **Lightroom Classic - silent pick, evergreen lost-work genre.** Default preference is
  *"Load most recent catalog"*, announced nowhere but the title bar; every version upgrade
  leaves a second `.lrcat` behind. The Lightroom Queen keeps a standing article whose thesis
  is the prior verbatim: *"If you open Lightroom and your catalog is empty, Lightroom has
  likely just opened the wrong catalog"* (lightroomqueen.com/lightroom-catalog-empty). Adobe
  forum threads with that diagnosis recur; the data is almost never gone - users report it as
  loss anyway.
- **Zotero - the counter-example, and it EARNED its prompt.** The 5.0 migration picked
  silently (most-recently-modified `zotero.sqlite`; its own KB admits it sometimes migrated
  the wrong profile), and the resulting loss reports forced explicit UI: a launch dialog -
  *"data directory could not be found at X, but a data directory was found at Y. Use this
  directory instead? / Locate / Quit"* - plus a pre-sync guard, *"You are about to sync your
  account to an empty Zotero database"*.
- **digiKam - silent config read, nulls reported as findings.** The database-settings manual
  documents no startup selection and no missing-path behaviour at all; a missing configured
  path historically hangs with no window or loops an error (KDE bug 235928). A clean
  "opened the wrong `digikam4.db`" thread was searched for and not found; its loss genre is
  the adjacent path/UUID drift.
- **Immich - silent and worst-in-class.** A one-line `DB_DATABASE_NAME` mismatch silently
  materialises a fresh empty schema and greets the user with the **first-run admin
  registration page** over hundreds of GB of intact data (github discussions 19977 - ">200 GB
  gone", fixed by reverting one env line). The "UI" for the wrong-database state is the
  onboarding screen, which is exactly what makes users read it as total loss.

**The refined prior**: silent pick is the industry default; users reliably report it as lost
work even when the data is intact in the other catalog; and the one product that prompts
today grew the prompt from damage. That is the argument for this entry disclosing **before**
users arrive rather than after.
