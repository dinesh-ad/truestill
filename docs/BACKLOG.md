# truestill - Backlog (approved but unbuilt)

Things that were **decided** but not yet built - captured here so nothing lives only in chat
history. This is not a wishlist of everything possible; only items already agreed, with the
decision context that produced them.

> **How to read this file: status is per ENTRY, never per section. A heading is not a status.**
> Read the entry's own text before acting on it - several are *partial*, and partial is the
> normal state here rather than the exception. This is written at the top because it is the
> defect the 2026-07-31 audit found: 20 of the 36 entries under a heading that said *"not yet
> built"* were built, and separately `(n)` and `(ii)` described shipped work as unstarted. Both
> directions cost real money - one hides finished work, the other invites rebuilding a schema
> that already ships.

> **Items (w) and (x) came from a three-report external research synthesis (2026-07-27) whose
> main result was that it changed nothing.** It reviewed the shipped architecture and validated
> it point-for-point; these two are the entire delta, one of them trivial and one of them
> post-launch. That outcome is worth recording as loudly as a finding would have been - an
> external review that produces two small additive items is evidence the recorded decisions
> have been holding, and it is the kind of result that quietly disappears if only the deltas
> get written down.

## Item letters

Letters are **permanent identifiers, not an ordering** - `IMPLEMENTATION_STANDARDS.md` cites
`(aad)` and `(ii)` by letter and `PROJECT_STATUS.md` cites `(gg)`, so reusing or renumbering one
silently redirects a citation. Since the split those citations reach across **two** files: a
letter is assigned here and the entry may live in `BACKLOG.md` or in
[`SHIPPED.md`](SHIPPED.md). They are assigned across *all* sections, not per-section, and
`SHIPPED.md` never allocates one.

*(The example here used to be "§8 cites `(u)`". That citation no longer exists - the contract
names no `(u)` anywhere - which is exactly the drift this paragraph warns about, found in its
own text. Replaced with citations verified present on 2026-08-01.)*

**Used: (e)-(z), (aa)-(zz), (aaa), (bbb)-(fff), (aab)-(ahy). Next free: (ahz).**
⚠ **`(ahe)` was assigned ahead of `(ahd)` on 2026-08-25**, the way `(aap)` went ahead of
`(aao)`: letters are identifiers rather than an ordering. **The gap was filled the same day** by
`(ahd)`, so the range is contiguous again.
⚠ **`(agf)` was cited by `pyproject.toml`, a test and `age.md` before its entry existed**, so for
one commit three working citations resolved to nothing. Recorded because it is this section's own
warning happening - *"nothing recorded which letters were spoken for"* - and the fix is to claim
the letter in the commit that first cites it, not the one that gets round to it.
⚠ `(adk)` was the gap this line flagged as free, and it was taken on 2026-08-15 by the SSE
heartbeat fix in `SHIPPED.md`, so the range is now contiguous. `(adl)`-`(adq)` were allocated on
2026-08-14 and this line was not updated with them, which is the exact drift the warning
below describes. Six letters, one day, and the *next free* answer stayed right by luck
while the *used* range was wrong. `(aap)` was assigned ahead of `(aao)` and the gap has since been filled by `(aao)`; letters are identifiers, not an ordering, so neither was renumbered. Check here before assigning - `(u)` and `(v)` were proposed
a second time on 2026-07-27, four hours after they were first taken, because nothing recorded
which letters were spoken for.

**AN ENTRY IS CLOSED BY A COMMIT WHOSE MESSAGE SAYS `Closes (xyz)` ON A LINE OF ITS OWN, AND BY
NOTHING ELSE** (standing, 2026-08-10). A ruling in conversation is not a closure until a commit
records it, and that commit moves the entry to [`SHIPPED.md`](SHIPPED.md) - this file carries open
work only.

**The trailing full stop is conventional and is deliberately not required**, corrected 2026-08-10
because this line said *exactly* `Closes (xyz).` while the pattern had always accepted both. Of
the two possible reconciliations only one fails safely: requiring the period means a commit that
omits it stops counting as a closure at all, so a shipped entry sits in the open-work file with
nothing to say so - the silence the rule exists to end. A wider marker costs nothing here, because
the line must still be a trailer of its own, which nobody writes by accident.

**Both directions are enforced, in two places, because only one of them is checkable against
history.**

- *Declared closed, but still open work here* - **`test_closed_entries_leave_the_backlog.py`**,
  over the whole corpus. It also fails when a declared letter is in **neither** document, which is
  what deleting an entry outright would look like.
- *Left this file without ever being declared* - **`scripts/check_entry_closure.py`**, a
  `commit-msg` hook (activate with `uv run pre-commit install --hook-type commit-msg`). It refuses
  a commit that removes an entry title from here unless the message declares the letter closed
  **and** the entry arrives in `SHIPPED.md` in the same commit.

**Why that half is a hook and not a test, stated so nobody "finishes the job" later.** As a check
over the corpus it is not honest: *a letter in `SHIPPED.md` must carry a trailer* fails **31 of its
32 entries** on the day it is written, because the whole history holds exactly one; and *an
allocated letter is in one of the two files* is false as well - `(e)` and `(h)` are retired and
legitimately in neither. ⚠ **This sentence named `(gg)` as a third example and that was wrong:
`(gg)` has a full entry in `SHIPPED.md` (*Adaptive day-folder threshold*, Built 2026-07-30).**
Recorded rather than quietly dropped, because the claim was load-bearing - it is one of the two
counter-examples justifying why this check is a hook and not a corpus guard, and one of the two
was false. `(e)` and `(h)` were verified against both files and do hold. A guard that goes red on the past gets switched off and takes its real
signal with it (`ENGINEERING_STANDARD.md` §4).

**And the boundary is structural, not a date.** The hook reads only the staged diff of the commit
being made, so it has no opinion about anything already committed - there is no "from now on" to
record and nothing to grandfather. An undated "from now on" would be the next drift; this way there
is no list of exceptions to maintain and no date to go stale. What it cannot see is stated in its
own docstring: an amend that only edits the message stages nothing, and hooks do not run in CI.

## A new entry that asserts an ABSENCE names the check it ran (convention, 2026-08-24)

**Only for negative claims** - *nothing does X*, *no caller*, *never reached*, *there is no route*.
An entry making one states, in one line, **the command that would falsify it and what it returned
on the day of filing**. `(acc)`'s *"Checked by grep across core, CLI and app, not assumed"* and the
Biome entry's *"zero `<form>` elements in the app (checked, not assumed: 0 in `index.html`, 0 in
`app.js`)"* are the shape; the latter says the durable part out loud - **"that check is the durable
artifact here, not the finding."**

**Why negative claims and nothing else.** A negative is the one kind of claim a single command can
kill: one hit refutes it. *X does Y* needs a reading, and no line in an entry substitutes for that.
Requiring evidence where it is cheap and decisive costs a line; requiring it everywhere would be a
research standard, which `ENGINEERING_STANDARD.md` §3 already owns.

**It earns a filer two different things**, which is why it beats "be careful":

- **At filing** it kills the entry that was never true. Three of the seven false-when-written
  premises died to a grep somebody could have run first - `(ace)` (the tool existed as
  `mutate_once.py` while the entry asked for `mutate.py`), `(ags)` (the extractor was never the
  cited function) and `(agq)` (the creating function was three below the one read).
- **Afterwards it makes the entry falsifiable by anyone.** A recorded command carries a date, so a
  later reader **re-runs it** instead of re-deriving the premise. That is the half that reaches the
  *fixed-under-another-name* family - `(abi)`, `(aak)`, `(abs)` were all true when filed and went
  false under a commit naming a different letter, which no closure guard can see.

⚠ **Not retroactive, and that is a ruling rather than laziness.** Roughly **42 of the 90** open
entries carry a negative headline today and **6 of 149** bodies record a check; demanding one of
the rest would go red on the past, which is the failure the paragraph above already explains about
the closure guard. ⚠ **And it is a convention, deliberately not a hook.** What counts as a negative
claim is a judgement about English, and a guard that has to make one fires on ordinary prose - the
`_PENDING` list in `test_backlog_references.py` was narrowed twice for exactly that. The full
argument is `ENGINEERING_STANDARD.md` §4's **seventieth member**.

*`(acr)` is the instance that proved the rule.* It was closed by the maintainer in conversation;
neither its entry nor any commit said so, and no repo check could ever have seen it - it sat here
as open work while shipped. Two of the three entries stale that day *were* catchable, because
their commits said so and nothing checked. The trailer is what turns a ruling into something the
repository can observe.

**Retired 2026-08-11, and named here because a retired letter is not a free one:** `(abp)` (the
body sans face is not bundled) and `(abh)` (the nav icons are Unicode glyphs, so their letterform
varies per machine). Both were recorded 2026-08-05, both are cosmetic, and **both were untouched by
the monospace bundling that shipped in between** - a pass that went through the type system and did
not reach for either. Carried a third week they would still be preferences rather than defects, so
they are retired rather than carried. Reopening one needs a reason the font pass did not supply.

> ⚠ **`(abh)`'s STATED REASON WAS FALSE, corrected 2026-08-13 (`4ff3577`). It stays retired.**
> All ten glyphs the rail uses **are present** in the bundled DejaVu Sans Mono - verified against
> the shipped `.ttf`. The letterform varied because `.nav-item .ico` set width, flex and size and
> **never asked for that family**, so it inherited `--font-sans` and resolved from whatever the
> machine had. Two lines of CSS fixed it.
>
> **The paragraph above recorded the right observation and drew the opposite conclusion from it.**
> *"Untouched by the monospace bundling ... a pass that did not reach for either"* was read as
> evidence they were cosmetic; it was evidence the pass had **left a gap**, because nothing pointed
> at the bundled face. `(abh)` was a live rendering defect filed as a preference.
>
> **Correcting it strengthens the retirement rather than undoing it:** a drawn icon set is still
> worth having, and it is now genuinely a want rather than a defect wearing that word. Left in
> place rather than rewritten - a document that states a cause it never verified is the failure
> here, and deleting the sentence would hide it.

**Retired 2026-08-24, and it is the first letter retired because it was NEVER WORK:** `(ags)`
(ingest extracting a whole archive into the user's temp). **The premise was false when it was
filed** - `extract_archive_set` has staged under `destination/.truestill-staging` since the
feature's first commit (`346135c`, 2026-08-01), three weeks earlier, and that staging *is* the
entry's own recorded fix-shape. The line it cited, `organizer.py:1251`, is `_MetadataBaker`:
a hundred files at a time, previous chunk removed before the next is staged.

⚠ **`Retires`, not `Closes`, and the distinction is the whole point.** A `SHIPPED.md` row would
credit a fix nobody made, and the next reader would find a closure with no commit behind it. The
reason is kept in full at [`research/backlog/ags.md`](research/backlog/ags.md), which is now a
**record** rather than a body - it is the primary evidence behind §4's seventieth member, so it is
linked rather than folded in here. That diverges from `(abp)`, `(abh)` and `(adb)`, whose bodies
were deleted because their reasons were a sentence each; this one is a measured proof with eight
citations, and the *Item letters* section is a registry, not a home for one.

**Retired 2026-08-24, and named here because a retired letter is not a free one:** `(aco)` (a
still whose camera wrote UTC into `DateTimeOriginal`). **The premise held and the population could
not be produced**: two censuses of both format corpora - 1,434 stills, by tag text and by GPS
comparison - found no camera with a Make and Model that does it, and the three apparent hits are
**London and Cardiff photographs taken in winter**, genuinely GMT. Every fix it proposed cost more
than the defect: 14 of the 37 GPS-comparable stills have a delta that is not a real UTC offset at
all, nine of them off by twenty-two hours. ⚠ **Its most valuable finding outlives it** - a fix
aimed at `dates.py:370`'s `is_video` would have done nothing, because `UTC_CONTAINER_TAGS` omits
`DateTimeOriginal` too. The body is kept as a **record** at
[`research/backlog/aco.md`](research/backlog/aco.md) with its reopen condition, and the live
evidence found on the way is `(agz)`.

Several early letters no longer appear anywhere in this file: their items shipped and the
Shipped entries describe the work rather than repeating the letter. `(e)` and `(h)` are still
cited by name in `drive-identity-research.md` and `org-structure-research.md`. **A letter that
is invisible here is retired, not free.**

## Approved - still to build

- **(ahv) RESTORE CANNOT CREATE AN EVENT, ONLY RENAME ONE - AND IT BLAMES THE PHOTOS.** Filed
  2026-08-26 (P103). After a catalog rebuild the `events` table is empty, so `apply_decisions`
  finds nothing by signature (`decisions.py:526`-`:531`) and **every event name is lost**.
  Measured: 353 files, 1 trip + 3 events named through the app's HTTP routes - the trip came back,
  all three events did not. ⚠ **The stated reason is false**: the product says *"its photos have
  changed"* while the content was byte-identical and the re-derived signatures matched the
  document's exactly, so **clustering is idempotent and the signature is stable**. Trips survive
  because `_apply_trips` (`decisions.py:442`) creates them from days. Body:
  [`research/backlog/ahv.md`](research/backlog/ahv.md).

- **(ahw) THE APP'S EVENT QUERY TESTS A LABEL WHERE A RULE WAS MEANT, AND THE TRIPS SCREEN GOES DEAD.** Filed 2026-08-26 (P103).
  `catalog.py:1289` filters `f.category = 'Camera'`; `layout.py:530`-`:532` forbids exactly that
  test in as many words, and the CLI asks correctly by rule (`event_review.py:68`). **Under
  `--by-device` the Trips screen proposes nothing** - not an error, not an empty state with a
  reason. ⚠ **A rule with a named violator, so the subject is the census**: three unlinked
  definitions of one concept, nothing guarding them, and a grep for the constant cannot see inside
  a query. The entry carries the guard design, its two blind spots, and the safety condition -
  **the rule is not persisted** (`catalog.py:92`) and the two selections **provably diverge**, so
  the fix is not a strict repair. **P104.** Body:
  [`research/backlog/ahw.md`](research/backlog/ahw.md).

- **(ahx) `not_applied` REACHES NO CONSUMER, SO A RESTORE NEVER SAYS THE ALBUMS WERE DROPPED.** Filed 2026-08-26 (P103). `apply_decisions` returns
  `not_applied=("albums",)` (`decisions.py:590`) and `_print_restore_plan` (`cli.py:1440`) prints
  five other fields and not this one - against its own docstring at `cli.py:1440`-`:1443`
  promising *"the half that is easy to leave out - what would not [come back]"*. **A user
  restoring is never told the albums section was discarded**, on either surface. No test asserts
  it. Checked: four hits repo-wide, one of them a name collision. Body:
  [`research/backlog/ahx.md`](research/backlog/ahx.md).

- **(ahy) AN IN-PLACE ORGANIZE AGAINST AN EMPTY CATALOG REBUILDS NOTHING, AND REPORTS SUCCESS.** Filed 2026-08-26
  (P103). An organized 353-file drive, fresh catalog, `organize <drive> <drive> --in-place
  --apply`: **`353 already in place`, exit 0, and 0 files / 0 copies recorded** - plus no
  `path_hint`, so the decisions document can never reach that drive either. Copy mode rebuilt all
  353. **`(aei)`'s shape on the in-place path**, and it is the arm a user with an
  already-correct library would naturally reach for when `(ahs)` says re-organize is the recovery.
  Body: [`research/backlog/ahy.md`](research/backlog/ahy.md).

- **(ahs) NO READ-ONLY PATH REBUILDS THE INVENTORY AFTER A LOST CATALOG.** Filed 2026-08-25 (P98).
  A **product ruling, filed not ruled**. Catalog deleted, library rebuilt from files: `restore`
  returns **drive identity only** (0 files, 0 copies); `rescan` reports all **10,710 as "ON THE
  DRIVE, NOT IN THE CATALOG"**; `attach_drive` returns **`linked=0`, `unmatched=10710`** because it
  links by content against zero rows. **Only a full re-organize rebuilds them.**
  ⚠ `rescan`'s own sentence - *"No command repairs any of the above yet. This one only tells
  you."* - is honest, and is also the whole gap.
  The claim holds **in substance and not in reach**: the facts are in the files and only the
  longest operation recovers them. ⚠ `(ahr)` made that recovery CLEAN on 2026-08-25 - a rebuild
  now returns identical date, source and category for 1,127 of 1,127 - so what is left against it
  is only that it is the longest operation in the product.
  [Full entry](research/backlog/ahs.md)

- **(aht) THE ARCHIVE STAGING TREE IS NEVER REMOVED.** Filed 2026-08-25 (P98), found in `(ahp)`'s
  artifact. A 1.61 GB archive leaves **535 files, 1.6 GB** under `.truestill-staging/` beside the
  organized copy, and **nothing removes it** (`grep -iE "rmtree|unlink|clean"` against
  `archive_ingest.py` returns nothing).
  ⚠ **Measured, and it changes the rank**: a second ingest of the same archive **does not stage
  again** - still 535 files, one directory - so N ingests cost **1x, not Nx**. Untidiness, not a
  disk a user runs out of. **But the work repeats**: 534 files unpacked again. Cost is per
  distinct archive.
  Defensible as it stands - copy mode never deletes a source, and the staging tree *is* that run's
  source.
  [Full entry](research/backlog/aht.md)

- **(ahq) FLAT PHOTOGRAPHS ARE ALL NEAR-DUPLICATES OF EACH OTHER.** Filed 2026-08-25 (P95).
  **89 files** sit within the default threshold (5) of the all-zero perceptual hash, across 16
  distinct hashes, and are mutually near-duplicate **by construction**. **Ten are real
  photographs** - `DSC05501.JPG` (Sony) and `DSCN0407.JPG` (Nikon) among them, unrelated frames
  from different cameras.
  ⚠ **NOT a bug in the hashing, and that was checked by LOOKING**: the 1.36 MB
  `IMG_20190719_153609.jpg` was opened and is a near-black frame, so its all-zero dHash is honest.
  Every flat image lands on that value whatever it depicts.
  ⚠ **The null**: nothing in the product or the documents addresses low-variance images -
  `grep` over `hashing.py` returns one hit and it is about *flatbed scans*; `docs/*.md` returns
  nothing. `PERFORMANCE.md` documents this comparison's cost and not what it returns.
  **The harm**: a user shown two unrelated photographs as duplicates stops trusting every pair the
  product reports, including the true ones - and 827 files went into that review queue.
  [Full entry](research/backlog/ahq.md)

- **(aho) THE JOB ENVELOPE IS THE ONLY SUCCESS PAYLOAD WITH NOTHING TO NARROW ON.** Filed
  2026-08-25 (P93/P94), split out of `(ahn)` stage 4b because the fix is a **wire change**.
  Every arm of every response union in this app carries a `Literal`-tagged key - `ok`, `armed`,
  `valid`, `code` - **except `JobStarted`**, which is one key, `job_id`, and no literal.
  ⚠ **Checked, not assumed**: an AST pass over every union arm reachable from a route, reported in
  the body. `_start_drive_job` returns **three** shapes, so all **15** job-start sites return a
  union, and `app.js:244` tells the arms apart with `started.ok === false` - false for `JobStarted`
  **only because `ok` is undefined**. The one place in the app where narrowing rests on a key not
  being there.
  **The fix** is `ok: Literal[True]`, additive and almost certainly safe - but it puts a new key on
  the body every job start returns, which is a ruling and not a detail.
  [Full entry](research/backlog/aho.md)

- **(ahl) CONDITION 3 IS AT 34 FIELDS, NOT 2, AND ITS OWN CENSUS DISAGREES WITH ITSELF.** Filed
  2026-08-25 (P81). `PROJECT_STATUS.md`'s condition 3 is kept by hand and names **two** live
  instances. Derived from the AST: **117 TypedDicts, 579 key slots, 289 distinct key names, 34**
  with no hit in `app.js` code and none in React (**11.8%**); **21** reach `cli.py` either.
  ⚠ **Checked, not assumed**: an AST walk of both `TypedDict` forms against the three consumer
  surfaces with `//` and `/* */` stripped, derived twice independently. **The naive grep certifies
  five dead fields as live** on the strength of a comment naming them (29 -> 34, surfaces held
  fixed). ⚠ **This entry said *"20 to 34 ... fourteen"* until 2026-08-25**; those two figures
  measured different surface sets, so the delta measured neither. Corrected when the guard had to
  assert on it.
  ⚠ **34 is a FLOOR, not a count.** A key-name census cannot see a collided field:
  `BakePreview.absent` is rendered at `app.js:4131` while `BakeSummary.absent` is not read by
  `bakeCompletion` at all, so the name never enters the list. `apollo-kotlin#991`, open since 2018,
  is the same limit in another language.
  ⚠ **The document disagrees with itself**: `PROJECT_STATUS.md` said **3 sites** in one place and
  **2** in another for the one instance it names, and the file has **4**, across two TypedDicts,
  one of which is read.
  **Its value expires when `app.js` is deleted** - see `(ahn)`.
  [Full entry](research/backlog/ahl.md)

- **(ahm) SIX OF NINE RUNS WRITE A HISTORY NOTHING READS.** Filed 2026-08-25 (P81), split out of
  `(agm)`'s closing report. ⚠ **Checked, not assumed**: `grep -rn` for `record_path_for`,
  `run_index_for`, `runs_dir_for`, `superseded_record_path`, `last-run` and `index.jsonl` across
  `packages/*/src`, minus the two modules that own them, returns **three** hits - one docstring and
  two **write** paths - and **zero** in `app.js` or `frontend/src/`.
  The only human affordance is `truestill organize --report PATH` (`cli.py:433`), which moves the
  file rather than reading one, and exists for `organize` alone.
  ⚠ **Ruled OUT of `(ahl)`/condition 3 deliberately**: a record has a designed consumer and a dead
  payload key has none; condition 3's subject is the route-to-surface contract; and condition 1
  already owns records. **So the 34 stands.** But in absolute terms this is larger than every
  instance in `(ahl)` together. `truestill where` is the candidate that satisfies `(afl)`'s
  **purpose** rather than its letter, and is also the only one whose cost is not trivial.
  [Full entry](research/backlog/ahm.md)

- **(ahn) THE PAYLOAD CONTRACT STOPS AT THE PYTHON BOUNDARY, AND REACT IS BEING BUILT AGAINST
  NOTHING.** Filed 2026-08-25 (P81). 117 TypedDicts describe every route's return **in Python**,
  and nothing carries any of it across the wire; the React source consumes **zero** payload keys.
  ⚠ **The live instance is already in the tree, before a screen exists**: `main.tsx:37` declares
  `type OrganizeSummary = Record<string, unknown>` - the cast that lets generated types change
  without complaint and the pull request go green.
  **The mechanism is a field standard**: the backend emits an OpenAPI spec, `openapi-typescript`
  generates the types, the frontend imports them - mechanical at **both** ends, which is the end
  `(ahl)` cannot reach. ⚠ **This project does not get it free, by a standing decision**:
  `pyproject.toml:17` records *"not FastAPI ... Pydantic is disallowed for our models"*, and
  **`pydantic` appears in no `pyproject.toml` in this workspace** (checked).
  ⚠ **And the join does not exist**: `server.py` declares **50** routes and **all 50** handlers are
  annotated `-> JSONResponse`, never the payload they return. This entry records the gap and the
  mechanism; it does **not** choose between hand-writing the spec, generating it from the
  TypedDicts, or emitting it from the routes.
  [Full entry](research/backlog/ahn.md)

- **(ahk) THE NAMING ROUTE DOES A CHECK-THEN-INSERT WITH NO LOCK, AND `truestill restore` CAN
  RACE IT.** Filed 2026-08-25 (P74). **Ranked above `(ahh)`**: that entry is how the collision is
  *reported*, this is the collision.
  `commit_trips` reads `catalog.trip_for_day` for every day (`trip_review.py:373`) and then
  inserts (`:378`) - **two transactions**, so `BEGIN IMMEDIATE` does not close the window. The
  route around it holds **nothing**: `events_apply` (`server.py:823-842`) has no
  `_start_drive_job`, no `jobs.claim` and no `lock_for`. Meanwhile `truestill restore` reaches
  `create_trip` through `decisions.py:477` in another process.
  ⚠ **The window is reproduced, and the reproduction's limit is stated**: with a second real
  `Catalog` connection opened inside the window, `commit_trips` raises
  `IntegrityError: UNIQUE constraint failed: trip_days.day`, the user's typed name is **gone**,
  and the day belongs to the other writer. **That forces the interleaving deterministically; it
  does not race two OS processes.** A true collision has a known *shape* and a reproduced
  *window*, not an occurrence observed in the wild.
  🔑 **THE TWIN PATH WAS HARDENED AGAINST THE NEIGHBOURING SHAPE, WHICH IS THE EVIDENCE THIS IS
  REAL.** `decisions.py:457-458`, verbatim:
  > `# Day -> the name of the trip holding it. Read once and kept in step as trips are created, so`
  > `# a document that names one day twice cannot make `create_trip` fail on the day primary key.`
  ⚠ **That defends the WITHIN-RUN duplicate and not the cross-process one** - and because it reads
  the claim map **once** up front, `apply_decisions` is if anything **more** exposed to this
  window than `commit_trips`, which at least re-reads per day.
  ⚠ **`(agu)`'s guard SEES this route and ALLOWS it**, which is the part worth knowing.
  `test_every_job_declares_whether_it_mutates.py` enumerates every handler and classifies every
  bare service call; `apply_event_review_names` is entry **:256**, *"catalog rows; its own
  docstring: 'No files move'"*. The classifier's own comment calls the class a recorded gap -
  *"catalog-ROW writers ... deliberately outside drive locks - the gap `(aaw)` recorded and
  `(adt)`'s close split into residue letters"*. So the guard is not blind; it reds a **deleting**
  call outside the exclusion, and this one inserts.
  **Census (P74): 9 unlocked catalog-writing routes; 8 are safe by construction.** Seven are
  single-key settings upserts (`set_organize_mode`, `set_sidebar_collapsed`, `set_text_size`,
  `set_library_root`, `set_layout`, `set_event_settings`, `set_everyday_day_settings`) and
  `confirm_file_date` is one `_tx` with `ON CONFLICT DO UPDATE`. **`events_apply` is the only one
  whose correctness depends on a read in one transaction and a write in another.**
  ⚠ **WHAT THE FIX IS NOT**: fixing `(ahh)`'s reporting does not fix this. A route that reports a
  collision cleanly is still a route that permits one - and the harm here is the user's typed name
  being lost, which no amount of good reporting returns.
  **Related but not this**: `(ads)` records that the catalog's concurrency *model* was inherited
  rather than chosen, and `(adn)` that nothing stops two processes holding one catalog. Neither
  covers an application-level check-then-insert, which no journal mode fixes.
  [Full entry](research/backlog/ahk.md)

- **(ahh) A FAILED "SAVE NAMES" REPORTS TOTAL FAILURE OVER A PARTIAL SUCCESS.** Filed 2026-08-25
  (P72), **re-scoped and re-ranked 2026-08-25 (P74) after reproducing it** - the entry as filed
  described a defect one class more serious than the one that exists.
  ✅ **The behaviour is real and reproduced.** Ten decisions with a forced failure on #7: trips
  1-6 committed, 7-10 never attempted, and `migration_journal`, `migration_runs`, `organize_runs`
  and `inplace_runs` all **empty** with no record file written. `commit_trips`
  (`trip_review.py:363-392`) catches nothing; each `create_trip` is its own transaction.
  ⚠ **THE TRIGGER IN THE FILING WAS NOT REACHABLE, and the entry said otherwise.** The
  reproduction poisoned a decision with a duplicate day - `confirmed_days` is typed
  `Sequence[date]` and `trip_days.day` is `PRIMARY KEY`. **No caller can do that**: checked,
  `confirmed_days` has **zero** references outside `trip_review.py`, and `service/trips.py:498`
  builds `TripDecision(card.trip, name)` positionally, so it stays `None` and the days come from
  `proposal.days`, a **`Mapping`** - unique by construction. What is reachable is `(ahk)`'s race.
  🔑 **It is a REPORTING defect, not lost work**, and each half was checked rather than reasoned:
  the catalog stays consistent (one transaction per trip); the half-state **is discoverable**,
  because re-proposing reads `ExistingNames` (`service/trips.py:135`, `:219`) so the six show as
  named and the four return as proposals; **a re-run converges** - proved, a second apply named
  the remaining four and the first six took `update_trip_days` rather than re-create; and the
  **session survives**, because `discard_session` is called from exactly one place
  (`server.py:887`, the apply-to-**disk** `on_started`), so the typed names are still there.
  ⚠ **The user is told the save FAILED while six succeeded** - `events_apply` is a plain route, a
  non-busy `sqlite3.Error` keeps its 500 by design (`server.py:105-108`), and `guarded` renders a
  fatal banner. That is **failure hiding a partial success**: the inverse of `(afa)`, and the
  **safe** direction - the user under-trusts and a re-run fixes it. **So this ranks BELOW
  `(abm)`-shaped computed-and-unread defects**, not above `(ahi)`/`(ahj)` as originally filed.
  **The fix shape is `(afw)` Stage 4's skip-count-name** - a verdict per decision, counted and
  named, batch finished - which is `ENGINEERING_STANDARD.md` §4 Errors' own rule. **Not a
  journal** (a re-run converges, so there is nothing to resume) and **not a run record** (whether
  a catalog-only naming is *"a run that changes the library"* is `(ahi)`/`(agm)`'s question and
  answering it here would smuggle in a decision this entry has no evidence for).
  It is `(agj)`'s shape on a fourth surface, with one difference: `(agj)` carried partial results
  to a **record writer that already existed**, and here there is none.
  [Full entry](research/backlog/ahh.md)

- **(ahi) THE RECORD-STATE CENSUS COVERS 5 OF 9 MUTATING OPERATIONS.** Filed 2026-08-25 (P72).
  `test_the_app_records_what_a_run_did.py`'s `MUTATING_RUNS` has rows for organize, backup,
  migrate, bake and organize_undo. Enumerated from `server.py` by AST, there are **nine**
  `mutating=True` operations: those five plus **`trip apply`, `archive unpack`, `clean empty` and
  migrate-`undo`** - and none of `service/trips.py`, `service/clean_empty.py` or
  `service/migrate.py` writes a run record.
  ⚠ **P69's own docstring predicted this exactly**: *"a new mutating service that writes no record
  cannot be detected, because nothing in this codebase declares the set of mutating services."*
  It was written as a stated limit and is now a measured gap - four operations outside the census
  that exists to make absence visible. Same hand-list blind spot `cli-app-parity.md` has, in the
  guard written against that class.
  [Full entry](research/backlog/ahi.md)

- **(ahg) `cli-app-parity.md` IS KEYED BY CLI SUBCOMMAND, SO AN APP-ONLY CAPABILITY HAS NO ROW.**
  Filed 2026-08-25 (P68). The document that answers *"what is actually missing"* **cannot see the
  class of gap that matters most**, structurally rather than by omission: rows are one per
  subcommand, so a capability with no subcommand gets no row. `bake` had **zero** mentions there
  until `(ahd)` gave it one, and `backup` and `trip apply` still have none.
  **The proposed shape: one row per CAPABILITY, one column per SURFACE**, each cell
  supported/partial/absent with the implementing `file:line`. An app-only feature then **must**
  appear with an empty CLI cell - the gap becomes visible by construction - and the reverse gap
  (`reclaim`, CLI-only) is caught by the same table instead of by a second one.
  **Prior art, and each answers a different half.** Nextcloud's `occ` manual claims parity in
  prose in **both** directions and there are open requests for the reverse - the failure mode of
  writing it down without keying it. **Git** separates plumbing from porcelain and documents which
  contract each command honours, so the capability is defined once and each surface is a stated
  contract. **Kubernetes Gateway API** defines behaviour in a spec with feature tiers and
  validates implementations against it rather than trusting them. **Docker CLI and kubectl** are
  thin clients over a documented API, so the API *is* the registry and parity is auditable.
  [Full entry](research/backlog/ahg.md)

- **(ahb) THE UNDATED REPORT NAMES THE PROBLEM AND LINKS TO NOTHING.** Filed 2026-08-24 (P53).
  **Ranked ABOVE `(aha)`** - a route is worth more than a defect note, because it is what keeps a
  user out of the defect. The Organize result says *"No reliable date could be found, so these are
  kept together, not guessed"* and links **nowhere**; the Dates screen that fixes exactly this is
  reachable only by another door. 🔑 **The `(afu)` shape with a measured population: 1,262 undated
  of 7,790, 16%** (golden snapshot, 2026-08-23) - and it is the moment a user reaches for the
  external tool `(ii)` says will revert their work. ⚠ **The list SELF-DRAINS** (a confirmed file
  leaves the tier), so *"Set dates for these"* is honest and *"review 1,262 files"* is not.
  ⚠ **`DATE_TIER_PAGE = 50` was checked and is NOT the defect** - the truncation is disclosed and
  the list drains, so it is a pacing limit; do not spend a turn on it. **The browser lane can stay
  off**: `test_the_rearrange_card_name.py` is the precedent, and its docstring is this entry's own
  defect solved once already. ⚠ **The CLI half is NOT cheap** - `add_parser("dates")` returns 0,
  the rescue is app-only by recorded deferral, so a CLI sentence must point at the app, which is a
  ruling rather than wording. [Full entry](research/backlog/ahb.md)

- **(aha) AN EXTERNAL EXIF EDIT PRODUCES A DUPLICATE, OR ADVICE THAT DESTROYS IT.** Filed
  2026-08-24 (P53) from a traced read. ⚠ **Records behaviour, proposes nothing.** Editing the EXIF
  and re-running **is the field's model** (`porte`, `exif-assistant`), so users arrive expecting
  it. Edit the **source** → new `files.sha256`, the dedup identity → **copied again**, leaving a
  **duplicate** beside the undated original. Edit the **library copy** → `copy_sha256` is stale →
  `verify` reports MISMATCH and advises *"re-copy the source to restore a bad file"*, which
  **discards the edit**. 🔑 **`(agv)`'s COUSIN, not its sibling**: there the photo was intact and
  `verify` lied; here the content genuinely differs so **`verify` is right** - what is wrong is the
  **remedy**, which assumes corruption is the only way a file changes. `(ii)`'s catalog-event
  ruling extends from hand-moves to hand-edits unchanged, and the field's tools can afford that
  hatch only because they keep no catalog. The hash cache is **not** the mechanism (it invalidates
  correctly) and `rescan` cannot see it (`PLACED` is never read).
  [Full entry](research/backlog/aha.md)

- **(agz) A STILL CAN DECLARE ITS OWN UTC OFFSET AND WE THROW IT AWAY.** Filed 2026-08-24 (P50)
  out of `(aco)`'s retirement census - the live evidence found while withdrawing a false entry.
  ⚠ **CHANGES NO FOLDER TODAY**, and the entry leads with that: `OffsetTimeOriginal` is the offset
  *of* a local `DateTimeOriginal`, so reading it moves no wall clock. **What it buys is the true
  instant** - what cross-device ordering needs, and what an April 2026 Lightroom thread is
  complaining about when two cameras seconds apart sort five hours apart. `parse_exif_datetime`
  strips the offset and `OffsetTimeOriginal` is not in `exif.REQUESTED_TAGS` at all (grepped).
  Two real cameras write it inside the tag (`FLIR Vue Pro 640`, `FLIR iPhone device`), so placement
  is correct **by luck of convention, not by reading what the file says**. ⚠ **Does NOT contradict
  `(uu)`'s trap** - that is `OffsetTime` (0x9010, modification); this is `OffsetTimeOriginal`
  (0x9011, capture). 🔑 **Prevalence: 38% of post-2016 stills, 11 makers, 14 models** - the 2.37%
  I first measured used the wrong denominator, since the tag did not exist before 2016.
  **Permission: an offset present and read is evidence; an offset absent must never be inferred.**
  [Full entry](research/backlog/agz.md)

- **(agy) FIVE THINGS THE CATALOG WRITES AND NOTHING READS - a census, not a verdict.** Filed
  2026-08-24 (P47), generalised from one instance found by a surviving mutation in P46.
  `migration_runs.completed_at`, `file_copies.copied_at`, `reclaim_journal.reclaimed_at`,
  `skipped_clusters.skipped_at`, and **`file_albums` - an entire table** with no reader in shipped
  code. 🔑 **The census is a proof rather than a guess because this repo forbids `SELECT *`**
  and pins that with `test_queries_name_their_columns.py`, so "named in no query" really does mean
  "never read". The `verified: Literal[True]` family at the schema layer. ⚠ **`file_albums` is NOT
  orphaned** - `(acg)` owns it and `decisions-on-drive-research.md:110` designs for it, so for that
  row the answer is *deliberate, and waiting*. ⚠ **`migration_runs.completed_at` is the one with a
  consequence**: `run_migration`'s close condition has no observable effect, so no test can guard
  it. **Rules nothing** - the four timestamps may all be legitimate provenance; what is recorded is
  that nobody has said so. [Full entry](research/backlog/agy.md)

- **(agw) `last-run.json` IS WRITTEN OUTSIDE THE LOCK THAT GUARDS THE REST OF THE RECORD.**
  Filed 2026-08-24. **`(afw)`'s third NOT DECIDED item coming due**: it said to design the
  one-rolling-file question *"before any second writer is added"*, and **three writers exist
  now** (organize, backup, undo - grepped). `record_run` locks the index append, supersede and
  prune; `write_run_record` is the line **after** that block. Bounded by design - detail can be
  lost, the fact cannot, because §1 already rules that a line never asserts its detail exists.
  A design question, not a defect. [Full entry](research/backlog/agw.md)

- **(agt) REFUSED READS AS ABSENT IN MESSAGES AND REPORTS - `(aey)`'s wording residue.** Filed
  2026-08-24 after two censuses in two days, so the list stops being re-derived: nine sites
  where a bare probe's refused-as-`False` changes a sentence or a count - never a recorded fact,
  never an action (those seven are fixed under `(aey)`). Fix opportunistically with
  `path_reach.reach`, one voice across the messages. [Full entry](research/backlog/agt.md)

- **(agp) THE BUSY MESSAGE NAMES A SECOND WINDOW THAT DOES NOT EXIST, AT THE USER'S FIRST CLICK.**
  Recorded 2026-08-23, split out of `(adt)` when it closed, **ranked above `(agq)` by the
  maintainer - a wording-and-detection defect, not a lock defect.** `CATALOG_BUSY_MESSAGE`
  (`catalog_busy.py:70-76`) says *"close the other Truestill window, or stop the other command in
  your terminal"* - and the likeliest way to meet it is a **first-run schema build**: one window,
  one user, their first ever click, **both clauses naming things that do not exist**. That is the
  product telling a user something false at the exact moment it is failing them.
  🔑 **Prior art recorded so it is not re-derived**: Zotero says plainly another instance has the
  database open and **earns** it - `locking_mode=EXCLUSIVE` makes it true. This product cannot
  claim it: `(adn)` says two apps really can run, and the common cause has no second window at
  all. **The ruled shape**: say what is actually known - the catalog is busy, this is usually the
  first run preparing the library, it should clear on retry - and name a second window **only if
  one was actually detected**. The commonest instance was already disarmed by `b0a5d7e`
  (boot-time build, 2026-08-14 - see `(agq)`'s closure); this is what the message says whenever
  it still fires.
  ✅ **Part 1 (S4) shipped 2026-08-23**: the census found seven unhandled direct-write routes -
  a class - so busy is now recognised once, app-level, exactly as the CLI does at its top; 503 +
  the no-window sentence, faults keep their 500, settings writes retry twice. **The ladder is
  two tiers since 2026-08-23 - flock probe + wording**: tier 1's in-process registry is ruled
  DEAD, because the app has built at boot since `b0a5d7e` (2026-08-14) and the only reachable
  "preparing" case is cross-process, which an in-process registry can never see. What remains:
  the probe and S1/S2/S3 wording. [Full entry](research/backlog/agp.md)

- **(agh) `LocalGuard` MAKES FORGETTING THE TOKEN IMPOSSIBLE AND UN-EXEMPTING INVISIBLE.**
  Recorded 2026-08-23. **The token is enforced well** - ASGI middleware wrapping the whole app
  (`server.py:1041`), so no route can forget it, with Host/Origin checks and
  `secrets.compare_digest` (`security.py:84-94`), and the single `/static/` exemption verified
  inert. **The gap is that nothing pins the exemption LIST.** Coverage is per-route
  (`test_server.py:20,33,39,44`, `test_thumb_route.py:115`); a second `startswith` added to
  `_reject` would be caught by nothing, and it is a two-line change that looks harmless.
  🔑 **The asymmetry is the point**: the middleware makes the common mistake structurally
  impossible and leaves the rare one unguarded - the shape that survives longest, because everyone
  knows the token is enforced so nobody re-reads what enforces it. **The pattern exists**:
  `test_every_job_declares_whether_it_mutates.py` walks the routes, and its `assert len(declared)
  >= 12, "the scan is broken"` floor is the load-bearing half to copy with it. 50 routes today.
  [Full entry](research/backlog/agh.md)
- **(agd) A DEGRADED WATCHER SAYS NOTHING, AND THERE IS NO CHANNEL FOR IT TO SAY ANYTHING IN.**
  Recorded 2026-08-23, split out of `(aft)` **while building it**. `(aft)` made an unmeasurable
  probe fail **open** - correct, and the module's recorded posture - but it fails open
  **silently**: a run completes with the disk-space guard switched off and nothing counts or names
  it. ⚠ **Both sides are filed because either may win.** For: §9's never-silent clause
  (`IMPLEMENTATION_STANDARDS.md:1354`) makes a *degraded* outcome something that must be counted
  and named, and it is binding contract. Against: `_stop_if_ground_moved`'s own docstring
  (`backup.py:247-253`) argues that *"a second mechanism for the same class of event would be a
  second thing to keep in step"* - made about the stop path, and it applies to a notice path.
  🔑 **It is one entry, not organize's third of one**: `HealthVerdict` is binary and the three
  watchers consume it three ways - an `ActionResult`, a `MigrationOutcome` field, and a `raise`
  with **no non-fatal path at all** - so building the channel for one leaves two, which is §4's
  fifty-sixth member **scheduled rather than inherited**. **The wording is already ruled** and
  carries three constraints that each cost a draft: no free-space figure, no reason word, and
  neither *"Truestill's catalog folder"* nor *"nothing was left half-written"*.
  [Full entry](research/backlog/agd.md)
- **(age) `(aek)`'s SILENT DIRECTION SURVIVES INSIDE `(aek)`'s OWN FIX.** Recorded 2026-08-23,
  found while investigating `(aft)`. `preflight_destination` correctly records `free: int | None`
  (`filesystem.py:259-263`) and then **throws it away one line later**: `free_bytes=need if free
  is None else free` (`:271`), with `DestinationPreflight` carrying **no field** for *"this was not
  measured"*. So unmeasurable becomes *exactly enough*, `may_proceed` is `True`, and
  `cli._print_preflight` prints nothing. 🔑 **The conflation was removed where it was MEASURED and
  reappeared where it is REPORTED** - a fix that stops one line short of the surface, which is why
  it is its own letter rather than a note on `(aek)`. ⚠ **The backstop argument does not cover
  it**: *"it fails later, and louder, with the real reason"* is about a **run**, and a **preview**
  exists to say what will happen before it happens - so the later failure is not its backstop, it
  is what the preview was meant to prevent. Mirror of `(aft)`: loud-and-wrong there,
  quiet-and-wrong here. [Full entry](research/backlog/age.md)
- **(afz) `mutation_matrix.py` LEAKS A TEMPORARY DIRECTORY PER MUTANT, IN A SCRIPT NO GATE
  RUNS.** Recorded 2026-08-23, found while measuring `(afy)`. `scripts/mutation_matrix.py:539` is
  a bare `tempfile.mkdtemp()` with **no cleanup on any path**, called once per mutant - **67
  mutants across three suites**, so ~73 `/tmp/tmp*` directories per sweep. ⚠ **It accumulated
  invisibly for a structural reason**: the script is in no `Makefile` target, no hook and no
  workflow - correctly, it costs minutes - so **no gate can see it**, and the directories are
  near-empty so nothing runs out of anything. 🔑 **`:617` is leftover BY DESIGN and must not be
  "fixed" with it**: it holds the originals of every mutated file so a `SIGKILL` leaves a
  one-command recovery, and a `TemporaryDirectory` there would delete the recovery exactly when
  it is needed. ⚠ **The commissioning premise was false and is corrected in the entry**: pytest
  does **not** clean `tmp_path` - retention defaults to **3** by design - so "there are
  leftovers" implies nothing, and following it excluded the script while pointing at the suite,
  which calls `tempfile` **zero** times. Also named, not fixed: `shoot_screens.py:170` leaks on
  abnormal exit. [Full entry](research/backlog/afz.md)
- **(afx) THE CEILING IS ASYMMETRIC - LOCAL 2000, CI 3600. THE 3.79 s WAS A CONTENDED READING.**
  ⚠ **RETITLED AND NARROWED 2026-08-23**; it read *"THE BROWSER LANE HAS GROWN INTO ITS OWN
  CEILING: 1996.21 s AGAINST 2000"*. That run was taken while `(afu)` was being written and
  `make check` ran against the same cores; **five other readings of the same lane sit at
  1169-1506 s** and both local readings report an identical `973 passed, 3 skipped`, so the lane
  had not grown. **Real headroom is ~493 s, not 3.79 s.** 🔑 **Do NOT raise the ceiling** - now
  because there is nothing to accommodate.
  ⚠ **The defect is the ASYMMETRY, not the number.** CI overrides to **3600** (`ci.yml:554`), so
  CI stays green while `make e2e` fails locally - and local is what a person runs before
  committing, so **the red lands on whoever is doing the right thing** and the person who skips
  the lane sees nothing. ⚠ **It is `(aec)`'s bill**: 62 waits across 20 files, re-counted 2026-08-22
  and unchanged, whose total nobody was watching once the lane went nightly. ⚠ And the ceiling
  times **pytest only** - `make frontend` runs outside it, and `(aee)` measured 43% of a CI lane
  outside what it can see. `pytest-xdist` is the obvious lever and is deliberately **not**
  proposed: this suite protects a UI `(adi)` is replacing. [Full entry](research/backlog/afx.md)
- **(afs) A DESTRUCTIVE MIGRATION MAY NOT RUN WITHOUT A PRE-UPGRADE COPY, AND NOTHING SAYS WHICH
  ONE IS DESTRUCTIVE.** Recorded 2026-08-22, split out of `(ady)` while building it - **a policy
  change about what a migration may do, which would have been invisible arriving inside a
  copy-before-upgrade fix.** `(ady)` degrades when the copy fails, which is right while every
  migration is additive and wrong the day one is not. The declaration must **not** gate the copy
  itself: that would trust the same judgement that wrote the destructive migration. The guard is
  demonstrated rather than proposed - an AST scan over `catalog.py` cleared all 19 forward steps
  and flagged `downgrade_v12_to_v11`, the one function that really does `DROP TABLE`.
  [Full entry](research/backlog/afs.md)
- **(afr) THE LOCK DIRECTORY GROWS ONE EMPTY FILE PER DRIVE, FOREVER.** `DriveLock.release`
  truncates and never unlinks (`drive_lock.py:208,219`), so `~/.local/share/Truestill/locks/`
  gains a 0-byte file per distinct drive key and keeps it - and `path:` keys mean **every
  destination ever organized** leaves one. ⚠ **Nothing breaks and deletion is safe, because the
  flock is the truth and not the file** - which is exactly why it needs a letter rather than a
  comment: it was **neither designed nor recorded**, and `(aaw)`'s *"no stale lock to detect or
  clear"* is true of the lock and was read as true of the file. ⚠ *"Unlink on release"* is the
  obvious fix and probably the wrong one - it makes routine the one hole here, two processes on
  two inodes at one path. **Measure first**: nobody has counted a real user's key set. Found
  2026-08-22. [Full entry](research/backlog/afr.md)
- **(afq) A PREVIEW OCCUPIES THE DRIVE IN THE APP, AND NOTHING SAYS WHY.** `_start_drive_job`
  passes `operation="organize preview"` to `jobs.start`, which occupies the drive exactly as an
  apply does, so a second tab previewing during an organize is refused - while the CLI has never
  done this. ⚠ **Split out of `(aaw)` rather than folded in**: the lock rests on measured data
  loss, a preview writes nothing, and letting a UX decision inherit a safety argument it has not
  earned is what the 2026-08-03 design did without noticing. May well be right; needs its own
  reason. Filed 2026-08-22. [Full entry](research/backlog/afq.md)
- **(afg) THE DOWNLOAD PAGE HAS NO HOME IN THIS REPOSITORY, AND `truestill.app` EXISTS ONLY IN
  CONVERSATION.** The
  domain is bought; **nothing about it is in this repository** - `grep -ri truestill.app` matches
  only the package identifiers. D9 binds a requirement to a page that does not exist: *"Windows
  users must be told what SmartScreen will show… on the download page, above the button."*
  ⚠ **Whether it blocks a first tag is NOT DECIDED and this entry does not assume**; the arguments
  either way are recorded for the ruling. §4's fifty-eighth member exactly - a live planning
  assumption invisible to every grep and every audit. Filed 2026-08-22.
  [Full entry](research/backlog/afg.md)
- **(aff) ONE EXTRA NEAR-DUPLICATE ON 3.14, FROM THE INTERPRETER AND NOT FROM A DEPENDENCY.**
  262 look-alikes on 3.13, **263** on 3.14, stable over two runs each - and ⚠ **both pools agree
  exactly on both interpreters**, which is the property the step was run for. Ruled out by
  measurement: the relock moved **no** package version, and the walk order is byte-identical. The
  mechanism is **not isolated**. It did not block the upgrade because a near-duplicate is kept and
  flagged, never removed - the effect is one extra row in a review list, and exact dedup was
  identical in all four runs. Found 2026-08-22. [Full entry](research/backlog/aff.md)
- **(afa) `unreachable` MEANS FOUR THINGS, AND THE TOOLTIP ASSERTS ONE OF THEM.** ⚠ **Narrowed
  and retitled 2026-08-22 after a read-only pass falsified its own thesis.** It claimed
  `date_rescue` told the user nothing; measured, it renders *"could not check"*. What is wrong is
  that `unreachable` is produced by four distinct causes - no catalog row, no `source_path`, the
  sidecar refused, the parent is not a directory - and the tooltip asserts one of them for all
  four. ⚠ **Its central guess is recorded as FALSIFIED**: the three sites shared a cause, not a
  remedy, and one vocabulary would have fixed neither `(afn)` nor `(afo)`. That finding is worth
  more than the fix. Found 2026-08-21, narrowed 2026-08-22.
  [Full entry](research/backlog/afa.md)
- **(ael) NO CLI ROUTE COPIES A LIBRARY TO A SECOND DRIVE WITHOUT A SOURCE FOLDER.** `(aei)`
  closed most of this - `organize <source> <second-drive>` is now the CLI's second-copy route.
  What remains is drive-to-drive when the source folder is gone or no longer matches the drive.
  ⚠ `backup_run` is app-side and the CLI cannot import it, so this is a **move to core**, never a
  second implementation. Recorded 2026-08-20. [Full entry](research/backlog/ael.md)
- **(aeh) THE RUNNER IMAGE IS UNPINNED, SO THE apt THAT DEADLOCKS IS NOT A VERSION WE CHOSE.**
  `(aee)`'s hang is fixed in apt 3.1.3 and unbackported on noble; `ubuntu-latest` is noble today.
  ⚠ **A route with a cost, not a recommendation** - pinning fixes nothing by itself, and
  `ubuntu-latest` flipping to 24.04 in January 2025 left breakage found months later. Recorded
  2026-08-20. [Full entry](research/backlog/aeh.md)
- **(aeg) CACHE PLAYWRIGHT'S SYSTEM LIBRARIES SO `--with-deps` STOPS INVOKING apt AT ALL.** The
  right long answer to `(aee)`'s hang - it removes the class rather than bounding an instance -
  and the largest consumer, at 43m33s on run 32295312064. ⚠ **Does NOT cover the `check` lanes**,
  which still need exiftool, so `ci_bounded.sh` stays either way. Recorded 2026-08-20. [Full
  entry](research/backlog/aeg.md)
- **(aec) 62 FIXED WAITS IN THE BROWSER LANE, EACH ONE A COIN TOSS AGAINST A MEASURED LATENCY.**
  Recorded 2026-08-19. One was fixed; the class was not. [Full entry](research/backlog/aec.md)
- **(adz) A COMPATIBILITY PATH STATES ITS REMOVAL CONDITION WHEN IT IS WRITTEN.** Recorded
  2026-08-19. ⚠ **The window for free removal closes at the first `v*` tag.** [Full
  entry](research/backlog/adz.md)
- **(adx) A LIBRARY THAT MOVES IS HANDLED. WHAT IS MISSING IS THE DISCLOSURE.** Recorded
  2026-08-18. Three gaps, one user journey. [Full entry](research/backlog/adx.md)
- **(ads) THE CATALOG'S CONCURRENCY MODEL IS SQLITE'S DEFAULT, NOT A DECISION.** Recorded
  2026-08-15. [Full entry](research/backlog/ads.md)
- **(adm) `inspect_catalog` SKIPPED THE FIRST-RUN CASE - FIXED FOR THE APP, UNCHANGED FOR THE
  CLI.** Recorded 2026-08-14. [Full entry](research/backlog/adm.md)
- **(adn) NOTHING STOPS TWO APPS RUNNING, AND QUITTING THE SECOND DELETES THE WAY BACK INTO
  THE FIRST.** Recorded 2026-08-14, retitled 2026-08-22.
  ⚠ **Narrowed 2026-08-22 by `(aaw)`, and the title is now too broad**: two mutating operations on
  one drive can no longer overlap across processes, so *"two sets of in-flight writes"* is gone.
  **What remains is single-instance detection** - two apps, two ports, two sidecars, and
  `session-url.txt` naming one. ⚠ **`(vv)`'s residue was merged in the same day and `(vv)` closed**,
  so this is now the whole of the problem in one place, including the worst of it: quitting the
  second instance **deletes the link to the first, which is still running**.
  [Full entry](research/backlog/adn.md)
- **(adj) THE FREEZE IS NOT A REPRODUCIBLE TARGET: `truestill.spec` IS GITIGNORED.** [Full
  entry](research/backlog/adj.md)
- **(adi) REACT + SHADCN MIGRATION - PLANNED, GROUNDWORK LANDED, NOTHING MIGRATED.** [Full
  entry](research/backlog/adi.md)
- **(adh) TAURI SHELL + PYTHON SIDECAR - STAGE 1 MEASURED, THREE GAPS NAMED AND UNFIXED.** Recorded
  2026-08-13. [Full entry](research/backlog/adh.md)
- **(aed) THE METADATA BAKER STAGES EVERY BAKED FILE THROUGH THE SYSTEM TEMP DIRECTORY.** Recorded
  2026-08-19, split from `(adb)`. **Measure before changing anything.** [Full
  entry](research/backlog/aed.md)
- **(adg) THE VERIFY RESULT BLOCK MOVES `#bk-preview` BY +92.4px - a bigger mover than `(acw)`, and
  it cannot be reserved.** [Full entry](research/backlog/adg.md)
- **(ada) THE BACKUPS SCREEN NOW PUTS STATE BELOW THE FORMS, AND A ONE-COPY WARNING CAN FALL BELOW
  THE FOLD.** [Full entry](research/backlog/ada.md)
- **(act) AN UNNAMED ROOT IS LABELLED WITH THE LITERAL STRING `Library`, WHICH COLLIDES WITH
  ITSELF.** Recorded 2026-08-10. [Full entry](research/backlog/act.md)
- **(acy) THE NAMING LAYER - characterised across four rounds, measured against what already ships,
  and deliberately NOT built.** Recorded 2026-08-11. [Full entry](research/backlog/acy.md)
- **(acv) THE PRIVATE PATHS IN GIT HISTORY ARE ACCEPTED, NOT OVERLOOKED - and the repository goes
  private at launch.** [Full entry](research/backlog/acv.md)
- **(acu) POI LOOKUP FROM GPS - the strongest form of location naming, measured and NOT built.**
  Recorded 2026-08-11. [Full entry](research/backlog/acu.md)
- **(acp) GPS-DERIVED TIMEZONE - understood, costed, and deliberately NOT built.** [Full
  entry](research/backlog/acp.md)
- **(acn) DOES A GPS FIX TIME COUNT AS CAPTURE EVIDENCE? A RULING, NOT A BUG.** [Full
  entry](research/backlog/acn.md)
- **(adf) A CLI-ORGANIZED LIBRARY LEAVES `path_hint.library` UNSET, so the app has no observed
  destination to prefill.** [Full entry](research/backlog/adf.md)
- **(acg) ALBUM MEMBERSHIP CANNOT LEAVE THIS MACHINE - the same class as `(ack)`, waiting.**
  Recorded 2026-08-09. [Full entry](research/backlog/acg.md)
- **(acc) NOTHING PASSIVELY NOTICES A DECISIONS DOCUMENT ON A DRIVE.** ⚠ **Retitled again
  2026-08-23 by the open-entry sweep, because this index carried a headline its own body calls
  FALSE.** It read *"`write_decisions` exists with ZERO CALLERS, so no decisions document has ever
  been written"* and added *"the write trigger is not [built]"* - and `acc.md` has recorded since
  2026-08-22 that `write_decisions` has **two callers** (`decisions.py:981`, `cli.py:1515`) and
  that **`catalog_session.open_catalog` is the standing trigger**, writing on the first open after
  upgrade and on every clean exit that dirtied the catalog. **Documents are written to drives.**
  🔑 **An index that contradicts its own body is worse than either being wrong**, because the index
  is what a cold start reads and the body is what it reads second, if at all.
  **What survives is the title's claim and nothing more**: `read_decisions` is reachable only from
  an explicit CLI command, and `drive.reach_of` reads the marker and never the contents - so
  plugging in a drive that carries decisions tells nobody. Recorded 2026-08-09.
  [Full entry](research/backlog/acc.md)
- **(aca) The app and the CLI disagree about when an organize run needs confirming.** [Full
  entry](research/backlog/aca.md)
- **(aby) Organize screen: copy that repeats itself or explains its own button.** [Full
  entry](research/backlog/aby.md)
- **(abz) Organize shows one population three ways and connects none of them.** [Full
  entry](research/backlog/abz.md)
- **(abw) An already-named trip is re-asked, and until this commit the answer was discarded.**
  ⚠ **Findings (1), (2) and (4) are closed; (3) is open and, since 2026-08-15, a FEATURE question
  rather than a defect** - an attempt at it is preserved unmerged under the tag
  `preserved/abw-finding-3` (peels to `66f6c22`; was a branch until 2026-08-15). [Full entry](research/backlog/abw.md)
- **(abt) The unhinted-residue prompt is CLI-only, because the app cannot ask mid-job.** Recorded
  2026-08-07. [Full entry](research/backlog/abt.md)
- **(abr) `rcRunArchives` passes no `onRefuse`, so a refused start would throw.** [Full
  entry](research/backlog/abr.md)
- **(abn) rescan, beyond the report. `truestill rescan` REPORTS; nothing acts on it yet.** Recorded
  2026-08-07. [Full entry](research/backlog/abn.md)
- **(abd) ONE CATALOG OR MANY - the question is unanswered, and it may be the wrong default.**
  Recorded 2026-08-05. [Full entry](research/backlog/abd.md)
- **(abe) CLI custody was fixed forward the same day; REPAIRING PRE-EXISTING ROWS IS THE OPEN
  HALF.** ⚠ **Retitled 2026-08-22** so the built half is not read as pending:
  `cli._register_destination` landed 2026-08-05 in `a0091cf`, gated on `--apply`. Rows written
  **before** that still carry no copy row, so they stay outside custody and invisible to
  `verify`, `status` and `where`. Recorded 2026-08-05. [Full entry](research/backlog/abe.md)
- **(abf) A fix does not retroactively clean what it prevented.** Recorded 2026-08-05.
  🔑 **User evidence, added 2026-08-23**: a Photoshop Elements user imported from an SD card
  for **four years** believing files were being moved to their hard drive, because their
  preferences said so; the import had silently begun leaving them on the card. They wiped it
  and lost photographs of a newborn grandchild. **Thumbnails displayed correctly throughout.**
  That is reassured-state-with-no-staleness costing someone their photographs, and it moves
  this entry from a theoretical worry to an observed failure mode.
  [`user-evidence-log.md`](user-evidence-log.md) §2. [Full
  entry](research/backlog/abf.md)
- **(abg) The reassured state has no notion of staleness - "Schrodinger's backup".** 📌 **read the
  entry first - a premise inside it was corrected.** **Stages 1-3 have shipped**; what remains open
  is the `GONE` state, which is unbuilt and unruled. Recorded 2026-08-05. [Full
  entry](research/backlog/abg.md)
- **(abk) The library has no per-folder view - "where is all this actually sitting".** [Full
  entry](research/backlog/abk.md)
- **(abj) Find matches one substring; a two-word query silently finds nothing.** [Full
  entry](research/backlog/abj.md)
- **(abc) `check_product_name.SUBCOMMANDS` should be derived, not transcribed.** [Full
  entry](research/backlog/abc.md)
- **(abb) The other capture-filename conventions.** `rule_camera_filename` shipped with ONE
  pattern, Android's `IMG_`/`VID_`; the other vendors' conventions are unbuilt. Recorded
  2026-08-03. [Full entry](research/backlog/abb.md)
- **(aba) Nothing reconciles the catalog's recorded location with where a file actually is.**
  Carries `(agr)` part 3 since 2026-08-23 - the two-identities-at-one-path drive sibling, ruled
  no-build with its specimen preserved. [Full entry](research/backlog/aba.md)
- **(aaz) `ModifyDate < DateTimeOriginal` as a back-dating signal. RECORD ONLY - do not build.**
  [Full entry](research/backlog/aaz.md)
- **(aay) JPEG XL (`.jxl`) is classified as unrecognized. RECORD ONLY - do not build.** [Full
  entry](research/backlog/aay.md)
- **(aax) `time_known` is derived from provenance, not from the value. POST-LAUNCH.** [Full
  entry](research/backlog/aax.md)
- **(aan) A "verified against code" clause must still resolve.** Recorded 2026-08-01.
  🔑 **`(ago)` built the OTHER half on 2026-08-23 and did not close this** - recorded here because
  neither entry named the other. `(ago)` checks that a **line number** in a living document points
  at code that exists; this entry argues, with a measurement, that the line number is the wrong
  discriminator and asks for **symbols**: *"every backticked symbol inside a verified-against-code
  clause must exist under `packages/*/src`. Symbols, never line numbers."* `(ago)`'s own docstring
  says the same from the other side - it cannot see a line that moved onto other real code, and
  *"catching the rest honestly would mean citing symbols"*. **One seam, two halves, one built.**
  [Full entry](research/backlog/aan.md)
- **(aas) An undated file cannot be assigned to an event the user knows it belongs to.** Recorded
  2026-08-02. [Full entry](research/backlog/aas.md)
- **(aau) A zero-warning test lane, and why it is not one today.** Recorded 2026-08-02. [Full
  entry](research/backlog/aau.md)
- **(aai) The plain copy path does not verify at write time. DEFERRED with the cost stated - not
  an open item awaiting work.** Recorded 2026-07-31. The entry's original framing was **wrong and
  its fix would have been a regression**; what remains is detection latency, not correctness.
  ⚠ **The status was in the body and not on this line until 2026-08-24**, which is how a handoff
  came to rank it third among live engine work - the reader who only reads the index is the reader
  this file is *for*. Left in *Approved - still to build* deliberately: this file's own top rule is
  that **status is per entry, never per section**, and moving an entry so a heading agrees with it
  is that rule broken in the act of tidying. [Full entry](research/backlog/aai.md)
- **(aaf) Persisted skip record - "show me what was skipped last week".** [Full
  entry](research/backlog/aaf.md)
- **(aag) Near-duplicate grouping and burst review.** A review surface over behaviour that is
  already correct - record only, do not build. Overlaps `(m)`. [Full entry](research/backlog/aag.md)
- **(aad) Desktop installers - LAUNCH-BLOCKING for the paid product.** [Full
  entry](research/backlog/aad.md)
- **(aac) Organize names unreadable source files; ONE RESIDUE REMAINS, and it is app-side.**
  ⚠ **Retitled 2026-08-22 - the bare title read as a whole unbuilt feature and two thirds is
  built.** Scan tier and residue 1: built 2026-08-02. **Residue 3 closed by `(aev)` on 2026-08-21**
  and nobody connected them - `FileHashes.perceptual_computed` plus `uncompared_photos` are exactly
  the *"readable but undecodable is indistinguishable from a video"* distinction it asked for.
  **What is left is residue 2 alone**: `unreadable_files` is built in `organize_preview` only, so
  the app's **run** completion cannot name a file the CLI names. [Full
  entry](research/backlog/aac.md)
- **(ss) Organize preview hashes every file before showing anything - slow on a network mount.**
  [Full entry](research/backlog/ss.md)
- **(xx) Absolute-path columns and hash-cache keys are not machine-portable.** [Full
  entry](research/backlog/xx.md)
- **(aap) Registering a folder does not mint a second identity - BUILT 2026-08-02, ONE SURFACE
  LEFT.** ⚠ **Retitled 2026-08-22.** The row sat under *"still to build"* while the entry's own
  first line said **BUILT 2026-08-02**; the guard that prevents the loss is shipped on the CLI.
  What remains is deliberate and named in the entry: **the app has no register screen**, so the
  protection has no app-side surface. [Full entry](research/backlog/aap.md)
- **(bbb) exiftool `_original` backups.** Mostly BUILT - safety 2026-07-30, recovery 2026-07-31;
  recovery item 4 is the PARTIAL remainder. [Full entry](research/backlog/bbb.md)
- **(nn) Prove destination timestamp parity against a live rclone remote.** [Full
  entry](research/backlog/nn.md)
- **(r) Analyze mode - the hash cache half is SHIPPED.** [Full entry](research/backlog/r.md)
- **(kk) Persist GPS at ingest - it is read and then thrown away.** 📌 **read the entry first - a
  premise inside it was corrected.** [Full entry](research/backlog/kk.md)
- **(ll) Sub-day event identity that survives a changing file set.** [Full
  entry](research/backlog/ll.md)
- **(aam) Sidebar reference: profile header, section labels, submenus.** [Full
  entry](research/backlog/aam.md)
## Settled technical stances (recorded so they are not re-litigated)

- **(aat) `(aar)` is forward-only, and `migrate-layout` will not carry it backwards.** [Full
  entry](research/backlog/aat.md)
## Product / strategy (parked decisions)

> **Settled stance these sit under:** a user's **photo data never leaves their machine** and
> there is no telemetry. Pro is gated by a **signed local token** obtained at a one-time account
> activation - `docs/DECISIONS.md` **D5**, which supersedes D1's no-accounts stance on the maintainer's
> ruling. Any Pro-tier item below inherits that constraint, and none of the licensing
> infrastructure is built yet.

- **Web dedup teaser.** A Pro-tier positioning idea (a lightweight web-facing "find your
  duplicates" hook); not started. Reference stack proven in PixSort's browser mode, all
  **client-side - nothing is uploaded**: `exifr` (image EXIF), `mediainfo.js` (WASM, video
  dates), `hash-wasm` (BLAKE3 hashing in the browser). PixSort's `lib/metadata.ts` and
  `lib/hash.ts` (present under both `frontend/` and `apps-platform/`) are the reference
  implementations to study when we build this.
- **Desktop UI: Tauri vs local-web.** Parked architecture decision. The Rust-backed Tauri path
  informed the SHA-256/no-BLAKE3 hashing choice; the event-review interaction is the feature
  that will ultimately force the decision.
  - **(o) Lessons from the PixSort audit** (`PixSort/AUDIT_REPORT.md`): whatever wraps the UI,
    **one process serves the real UI**, bound to **loopback only**, and there is **never a second
    framework runtime beside the Python core**. PixSort's Electron+Next.js shell ran a whole JS
    runtime alongside the backend - the coupling and bundle weight it caused is exactly what
    truestill's single-process, server-rendered, no-build local-web UI avoids. A native shell (if ever
    built) wraps that one process; it does not add a second app runtime.

## Converged programs (do not pick in isolation)

These are not duplicates to delete - they are **one job split across lettered items**. Anyone
picking one up must map the combined order before building.

- **Date provenance → honesty → rescue → optional `_original`.** Items: **`(n)`**, **`(ii)`**,
  **`(bbb)` recovery**, and **`(kk)`'s `GPSDateStamp`** (lat/lon on `(kk)` also serves
  places/map, but the stamp is this program's cross-check). **One program, now partly built -
  check each step before starting it:**
  **PROGRAM COMPLETE 2026-07-31**, with one clause carried out as `(aaj)` - see `(bbb)` item 4.
  **`(n)` and `(ii)` are built and now live in [`SHIPPED.md`](SHIPPED.md)**; `(bbb)` is still
  here because its recovery half is partial, and `(kk)` is still here because none of it landed.
  This block stays in `BACKLOG.md` because it is an instruction to whoever is about to build,
  and it is the one place the program is numbered end to end.

  1. ✅ **Done.** Persist a durable date-provenance column: `files.date_source` (**v13**) and
     `date_tag` (**v14**), written by `record_uploaded`, worded once in `date_explain.py`.
  2. ✅ **Done.** Honesty view (`(n)`): the provenance **mix** ships in `service/stats.py`, and
     since step 5 each tier drills down to the files in it, each carrying the sha256 the rescue
     is keyed on.
  3. ✅ **Done.** Rescue (`(ii)`): stored durably, survives every whole-disk operation
     (`date_confirmations`, **v15**; O4 tested by name), and **reachable** since step 5 -
     `POST /api/dates/confirm`, app-only by recorded deferral.
  4. ✅ **Done.** `_original` offer (`(bbb)` recovery): same surface, same `human-confirmed`
     tier, never a parallel tool and never a silent substitution. Item 4's "optionally note the
     embedded conflict" clause was **decided against** - see `(aaj)`, now out of scope.

  Also not started: **`(kk)`'s `GPSDateStamp`** - verified 2026-07-31, the catalog has no
  latitude/longitude columns and no `GPSDateStamp`, so no part of `(kk)` has landed.

  Building an unbuilt slice alone still builds half a screen; **starting a built one rebuilds a
  shipped schema.** Steps 1 and 2 read as unstarted in this file until 2026-07-31.

- **Empty-folder leftovers.** Already shipped as one capability - see **Empty-folder cleanup**
  (provenance `(rr)` / `(zz)` / `(eee)` Commit 4).

- **Walk-and-classify on a drive.** `(hh)` (`adopt`) shares machinery with shipped `clean-empty`;
  map that reuse when `(hh)` is chosen - do not invent a second walker.

- **Preview cost / progressive disclosure.** `(tt)` + `(u)` Built; remaining is measured
  `(ss)` work and `(r)` Analyze (richer dry-run report, not a cheaper pass).

- **Loud failure vs portability for absolute paths.** `(ww)` Built; `(xx)` / `(yy)` remain the
  portability + reconnect half of the same family.

- **LayoutScheme axes.** `(gg)` Built (adaptive day folders); `(y)` / `(z)` are further axes on
  the same seam - do not rebuild routing.

## Ideas / deferred

> **Sequencing note - several of these share machinery, and picking them one at a time is the
> expensive order.** See **Converged programs** first. `(n)` and `(ii)` (and `(bbb)` recovery /
> `(kk)` GPSDateStamp) are one date-provenance program; `(hh)` (`adopt`) shares the
> **walk-and-classify** machinery with shipped `clean-empty`. When the first of a cluster is
> chosen, map a combined order before building - the schema step and the UI surface are each
> worth paying for once.

- **(aal) How often is the machine wrong about dates, and about what?** Recorded 2026-07-31. [Full
  entry](research/backlog/aal.md)
- **(m) Duplicate-cleanup staging UX.** The visual side-by-side compare it describes IS `(aag)`'s
  subject - scope the two together or the same review surface gets designed twice. [Full
  entry](research/backlog/m.md)
- **(p) "Share safely" - metadata-stripping export. PRO TIER (behind the capability seam).** [Full
  entry](research/backlog/p.md)
- **(x) XMP sidecar export for user-generated context.** Trip and event names are the only
  user-created thing in a library, and the only thing lost on leaving truestill. Post-launch. [Full
  entry](research/backlog/x.md)
- **(hh) `truestill adopt` - bring stray media in an organized drive into the catalog.** [Full
  entry](research/backlog/hh.md)
- **(aao) Asset pairing: several files that are one photo.** Names the concept `(y)`, `(p)` and
  `(aag)` were each circling: several files that are one photo. Needs a design pass before any
  build. Recorded 2026-08-02. [Full entry](research/backlog/aao.md)
- **(aaq) `rule_software` reads a tag that is never requested, so it cannot fire.** [Full
  entry](research/backlog/aaq.md)
- **(y) Optional photo / video split - default TOGETHER, and pair-aware or not at all.** [Full
  entry](research/backlog/y.md)
- **(z) Optional source / device manifest - catalog-first, hash-keyed.** [Full
  entry](research/backlog/z.md)
- **(s) Source-folder names as event evidence.** A meaningful source folder name (`Olympics/`)
  becomes a pre-named event proposal instead of scattering by capture date. [Full
  entry](research/backlog/s.md)
- **(t) Reflink / copy-on-write fast path.** `FICLONE`/`clonefile` on APFS, btrfs, XFS, ReFS.
  Optimization, not correctness - `copy2` already takes `sendfile` fast paths today. [Full
  entry](research/backlog/t.md)
## App-surface deferrals

Copy / Move / Reorganize-in-place and `undo-organize` are **in the app** - see **`(eee)`**.
What remains CLI-only shares one reason: each is a **space-safe or irreversible** operation
whose failure mode is permanent, and GUI demand is still judged from soak / launch feedback
rather than assumed.

- **The date rescue (`confirm_file_date`) is APP-ONLY**, recorded 2026-07-31 when step 5 made it
  reachable. A rescue is review-shaped - look at a photo, judge it, correct it, with the evidence
  in front of you - which is what the honesty view already is. A CLI equivalent would need file
  addressing by hash or path and would be used for bulk correction: a different, more dangerous
  feature that wants its own design. **Written down explicitly rather than left implicit**,
  because `test_surface_parity.py`'s second blind spot is a surface that omits a key entirely,
  so an undocumented single-surface contract is indistinguishable from drift.

- **Naming a trip or event is APP-ONLY**, recorded 2026-08-25. ⚠ **The PLACEMENT half is not
  missing, and that is the part everyone got wrong** - including `(ahf)`'s own text for four
  prompts. `truestill migrate-layout --apply` already moves files into trip and event folders,
  because placement derives from `files.event_id` and `trip_days`, and it is journalled and
  reversible with `--undo`. What has no CLI is the **naming**: turning *"these 40 photos are the
  Goa trip"* into a `trips` row.
  It is **review-shaped**, and unlike the date rescue there is **no durable intermediate at all**.
  The proposed names live in a browser array (`app.js:3380`, no `localStorage`) and a
  process-local dict capped at 32 that calls itself *"Mutable UI-only review state"*
  (`server.py:49`), and both die on reload. The request body sends the names as a **positional
  array** zipped against the server's session cards, so the identities never leave the process. A
  CLI could not consume a review - it would have to **own** one, which is the different and more
  dangerous feature the date-rescue row above already refuses.
  ⚠ **`server.py:675` held this decision in a comment** - *"session-based; merge/split are UI-only,
  no CLI path"* - and this register did not. This row is that decision arriving where it can be
  audited.
  **What would reopen it**: a durable pre-apply record, a `trip_confirmations` analogue of
  `date_confirmations`. The moment proposed names are written down before they are applied, a CLI
  can consume them - which is exactly what let `truestill bake` exist.

- **`truestill reclaim`** stays **CLI-only** until an app surface is explicitly approved. When
  one does get a surface, the pre-approved shape is advisory same-device detection plus a typed
  confirmation identical to the CLI's.
- **`{camera_model}` layout token** -- demand **re-confirmed by the user** during the soak
  era. Stays **deferred / Pro-tier candidate** as originally recorded in
  `org-structure-research.md` (§C1 "explicitly NOT v1 tokens"): it needs device metadata
  plumbed into the template render context. Recorded here so the re-confirmation is not lost
  the next time the token list is reviewed.

## Consciously out of scope (recorded with reasons)

- **A JavaScript FORMATTER, permanently. Ruled 2026-08-10 after measuring Biome 2.5.7.**
  Running it once would rewrite `app.js` wholesale - **3,733 source lines, 5,665 differing** - and
  `app.css` and `tokens.css` with it.
  - ⚠ **The cost lands on documentation that no test protects.** `docs/` carries **314**
    `file:line` references, of which **65 point into files the formatter would rewrite** (45 into
    `app.js` alone). Among them are `(abg)`'s, `(acd)`'s, `(acq)`'s, and several `ENGINEERING_STANDARD.md`
    §4 members written that week.
  - **Nothing would tell us.** Checked: **no test or guard asserts a line number.** Every
    `node.lineno` in the suite builds an error *message* (`test_absolute_imports`,
    `test_patch_targets_stay_aimed`, `test_subprocess_has_one_home`, `test_preview_gate_holds`);
    one docstring mentions `index.html:102`. So a reformat is green on every lane and silently
    invalidates 65 pointers.
  - **The benefit is consistency in a file one person edits**, and the cost includes routing every
    future `git blame` on `app.js` through one formatting commit. Not a close call.

- **Biome as a DEPENDENCY. Ruled 2026-08-10; the findings were taken, the tool was not.**
  A one-off `biome lint` run over `static/` and `templates/` found **90 diagnostics in 179 ms**:
  36 `useButtonType`, 16 `useOptionalChain`, 10 `noUnusedVariables`, 8 `noDescendingSpecificity`,
  6 `useTemplate`, and singles elsewhere. **Roughly 84 were opinions and 4 were real** - the four
  were fixed by hand in the commit that records this, with no Biome in the tree.
  - **Against adoption:** **63-80 MB per platform** (linux-x64 63.3, darwin-arm64 55.6, win32-x64
    79.6) across four CI lanes and three operating systems, as the **second** non-Python tool in a
    Makefile that has one; and our template **does not parse at all** without a committed
    `biome.json` enabling `html.parser.interpolation`, because Biome rejects `{{STALE_WARNING}}`.
    Adoption therefore starts with config, not with a binary.
  - **The 36 `useButtonType` findings stay unfixed, deliberately.** A `<button>` defaults to
    `type="submit"`, which only misbehaves inside a form - and there are **zero `<form>` elements
    in the app** (checked, not assumed: 0 in `index.html`, 0 in `app.js`). Inert today, real the
    day someone adds a form. **That check is the durable artifact here**, not the finding.
  - **Not a refusal of static analysis for the browser.** If it is revisited, the honest shape is
    a *small enabled rule set* - the a11y group, plus `suspicious/noDuplicateCustomProperties` -
    with `--formatter-enabled=false`, never the default 517 rules, which would mean fixing ~84
    non-defects or maintaining a suppression list as its own surface.

Not "not yet" -- decided **against**, so the question does not get re-litigated every time a
neighbouring product ships one. Each would be a reasonable feature in a different product.

- **A `warnings` field on `MigrationApplySummary`.** Found and **decided against 2026-07-31**,
  while closing the §9 gap where a missing exiftool degraded a migration silently. Recorded so
  it reads as a boundary someone chose, not a corner someone missed.
  - **What is still silent, precisely.** `migration_preview` surfaces the "folder names could
    not be checked against the files" warning through `warnings`, which the UI already renders,
    and the CLI prints it before the plan. `migration_apply` re-derives the same rules and has
    nowhere to put the reason, so a **direct apply without a preview** would degrade silently.
  - **No shipped flow performs that call.** The UI previews and shows the warning *before* the
    user confirms; `truestill migrate-layout` prints it in the same invocation that then
    applies. The silent path is reachable only by calling the service function directly, which
    is not a user flow.
  - **The cost is out of proportion to the case.** Closing it reaches the `TypedDict`, the
    payload construction, and the JS render - a public surface change, for a state nothing
    currently produces.
  - **What would make it worth doing:** *a caller that applies without previewing.* An API
    client, a scheduled or unattended migration, or a UI change that lets a user re-apply from
    a stored plan. Any of those turns this from unreachable into a real silent degradation, and
    the fix should land with that caller rather than in advance of it.

- **Cloud storage reached over a web API rather than a mounted filesystem `(aav)`.** Recorded
  2026-08-02. **A scope decision, not a limitation** - it follows directly from the product's
  promise that files stay readable without Truestill, in ordinary folders on the user's own disks.
  - **What works: anything the OS presents as a path.** Internal and external drives, NAS over SMB
    or NFS, and pCloud / Dropbox / OneDrive **mounted as a drive**. Truestill opens paths and does
    not care what is behind them, which is why the supported list needs no maintenance.
  - **What does not, and why it is a different product.** Google Drive API, S3, iCloud web. These
    are not filesystems: each needs a provider adapter, an OAuth flow, token refresh, rate
    limiting and its own failure taxonomy - and none of that makes anyone's photos more durable.
  - **Mounted is not local, in performance.** A FUSE or NAS path pays a round trip per file across
    tens of thousands of them. Projected from a measured 5 GB sample: for a 33,457-file library,
    network I/O dominates CPU by **3.6x to 36x** at every plausible transfer rate, so the mount
    decides the runtime and the pipeline does not. See `(ss)` and `PERFORMANCE.md` §3.0.
  - **Mounted is not always present, either.** A drive can vanish mid-run, which is what the
    `.truestill-drive.json` marker and `DriveReach.OFFLINE` exist for, and why identity is the
    marker uuid rather than a path.

- **Migrate verifying against the live copy hash instead of its journal snapshot `(aah)`.**
  Found 2026-07-31 while closing condition 3 of the date-provenance program. **Decided against
  2026-07-31**, after the analysis rather than before.
  - **Live catches no failure the snapshot misses.** On-disk corruption, a partial file from a
    crash, a half-finished relocate - the snapshot catches every one, and so does live, because
    corruption never updates the catalog. Every row where live "wins" is a **false alarm
    avoided, not a detection gained**.
  - **The snapshot is an independent second record; live collapses to self-consistency.** Two
    records that must agree catches a class one record checked against itself cannot - a catalog
    value that drifted from the bytes, or a row that now describes a *different* file after a
    re-organize. That is the same defect as `(aai)`: **a hash read from the thing it validates
    is not a check.** It is also what "a resume knows what it expected" buys - a resume finishes
    a plan made earlier, and must not silently re-derive one.
  - **Its entire benefit was already bought.** The only realistic source of the false alarm is a
    bake landing mid-migration, and condition 3 removes it at zero cost to the snapshot: the
    bake refuses while a migration is journalled and unfinished, re-checked before every file.
    `(aah)` would trade a real property away for something already secured.
  - **The hybrid is rejected too.** Accepting the on-disk hash if it matches *either* the
    journalled or the current value tolerates the bake and still catches corruption - but it
    reintroduces the self-consistency hole for exactly the case the snapshot exists to cover.
    *Two records must agree* beats a rule with an escape clause.
  - ⚠ **Reopening condition, deliberately specific:** evidence that the cross-process race
    actually bites - a soak run showing a real stall caused by a legitimate bake. Even then the
    fix is **the on-disk lock, not weakening the comparison**.
    ⚠ **Updated 2026-08-22: that lock now EXISTS.** This clause pointed at `(vv)`, which asked
    for it and has since closed; `(aaw)` shipped it - `flock`/`msvcrt`, per drive, mutating
    operations only. So the reopening condition is unchanged and its remedy is no longer
    hypothetical. The residual and its cost are recorded on `(aaw)`.

- **Noting an embedded-metadata conflict against a human-confirmed date `(aaj)`.** The
  "optionally note the embedded conflict" clause of `(bbb)` item 4. **Decided against
  2026-07-31**, after the design was worked out rather than before.
  - **The disagreement is already surfaced where it matters most**: the three-state card shown
    the moment someone confirms a date says exactly what the file still claims inside
    (*"The file itself still says 2014 inside"*), computed from the row being overwritten. What
    `(aaj)` would add is seeing that **later**, on the honesty view.
  - **Seeing it later needs the prior claim, and `confirm_date` destroys it.** It overwrites
    `captured_at` / `date_source` and sets `date_tag = NULL`; nothing else holds the old values.
    So the feature requires **storing a value the system has already decided is wrong** -
    forever, on every row, with every migration and every `record_uploaded` obliged to reason
    about it - whose only consumer is a line of explanatory text. *A column that exists only to
    be disagreed with* is the reason not to add one.
  - **The alternative was ruled out too.** Re-reading the file is live metadata, which the
    stated constraint forbids, and it inherits `(xx)`: with the drive disconnected it would read
    "cannot check" for most rows most of the time.
  - **The clause said "optionally".** That word was written by someone who already knew this was
    nice-to-have. The human-wins half of item 4 is built, tested by name against all five
    whole-disk operations, and is the half that carries the promise.
  - ⚠ **Do not reopen this to enable a *statistics* feature** - see `(aal)`. That is a different
    question with different requirements, and it is the use that would justify the column.

- **Face recognition / people albums.**
- **Semantic AI search** ("photos of a beach at sunset").
- **Auto-generated Memories / highlight reels.**

- **Per-camera or per-person subfolders inside an event.** It fragments **one memory by
  source** - the same error as an unconditional photo/video split. Four phones at one trip is
  precisely the case where everything should stay together, and splitting by device turns a
  shared afternoon into four partial accounts of it. Device identity is real and worth keeping;
  it belongs in the **catalog**, queryable, not carved into the folder tree - see `(z)`.

- **Conditional `Photos/` + `Videos/` subfolders ("create them only when both are present").**
  A structure must never rewrite itself because one file arrived: adding a single video to a
  618-photo day would force **619 files to move**. That is the same instability that rules out
  date-range folder names, and it is worse here because it triggers on an ordinary import. The
  optional, always-on, pair-aware split remains available as `(y)`.

**Why all three, together:** they are one class -- **ML infrastructure** -- and adopting any of
them changes what truestill *is*. Each needs models shipped or downloaded, a vector store or
embedding index beside the catalog, GPU-or-slow inference, and a retraining/refresh story; that
is a permanent tax on every install, and it lands squarely against the lean, local, no-network,
minimal-dependency identity recorded in `ENGINEERING_STANDARD.md` §1 and
`IMPLEMENTATION_STANDARDS.md` §7. It is also **Immich's and Ente's territory**, where they are
strong and mature: competing there means being a worse version of a server product, while the
thing truestill does that they do not -- custody of files you can still read without it -- goes
unfinished.

The honest framing for a user who wants these: run truestill for organizing and custody, and a
gallery server for browsing and search. They compose. That answer is better than a shallow
imitation of both.
