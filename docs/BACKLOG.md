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

**Used: (e)-(z), (aa)-(zz), (aaa), (bbb)-(fff), (aab)-(adg). Next free: (adh).** `(aap)` was assigned ahead of `(aao)` and the gap has since been filled by `(aao)`; letters are identifiers, not an ordering, so neither was renumbered. Check here before assigning - `(u)` and `(v)` were proposed
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
allocated letter is in one of the two files* is false as well - `(e)`, `(h)` and `(gg)` are retired
and legitimately in neither. A guard that goes red on the past gets switched off and takes its real
signal with it (`ENGINEERING_STANDARD.md` §4).

**And the boundary is structural, not a date.** The hook reads only the staged diff of the commit
being made, so it has no opinion about anything already committed - there is no "from now on" to
record and nothing to grandfather. An undated "from now on" would be the next drift; this way there
is no list of exceptions to maintain and no date to go stale. What it cannot see is stated in its
own docstring: an amend that only edits the message stages nothing, and hooks do not run in CI.

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

Several early letters no longer appear anywhere in this file: their items shipped and the
Shipped entries describe the work rather than repeating the letter. `(e)` and `(h)` are still
cited by name in `drive-identity-research.md` and `org-structure-research.md`. **A letter that
is invisible here is retired, not free.**

## Approved - still to build

- **(adb) TWO COPY PATHS STILL WRITE THE REAL NAME FIRST, AND ONE OF THEM IS THE CATALOG.** Named
  in `(acj)`'s closure 2026-08-11 as out of its scope, and filed here because a line in
  `SHIPPED.md` records what was *not* done without tracking it. `(acj)` staged every copy that goes
  through `safe_copy`; these two never did.
  - **`catalog_move.py:131` is the one that matters, and it is `(abu)`'s exact shape on a database.**
    A bare `shutil.copy2(source, destination)`. A failure part-way leaves a **truncated SQLite file
    at the destination path**, wearing the name the user was told to point at. The function's own
    contract makes it worse: it never removes the source and tells the user to *"check the copy,
    then delete the old one"* - so the failure mode is a person deleting a good catalog after
    glancing at a partial one. `copy_leaving_nothing` is a two-argument drop-in; the reason this is
    not a one-line fix is the surrounding `CatalogMove` result, which reports outcomes rather than
    raising, so the leftover-naming half of `CopyOutcome` has to be threaded into the message.
  - **`organizer._MetadataBaker` (`organizer.py:924`) is a different, smaller problem wearing the
    same clothes.** It stages into the **system** temp directory - not beside the target - so
    `safe_copy` would not help even if applied: the write to the real destination is the *upload*,
    a filesystem away. Its own partial is inside a temp tree that is torn down, and a copy that
    dies never enters `self._ready`, so nothing incomplete is uploaded. **The cost here is not
    safety, it is a full second write of every file that needs metadata baked**, on whatever
    filesystem `TMPDIR` names - which on a small root partition is a place a photo library does not
    fit. Measure before changing anything: `PERFORMANCE.md` has no figure for the bake path.
  - **Do not "fix" these together.** They share a `shutil.copy2` and nothing else - one is a
    correctness hole with a known remedy, the other is a placement question with no measurement
    behind it.

- **(adg) THE VERIFY RESULT BLOCK MOVES `#bk-preview` BY +92.4px - a bigger mover than `(acw)`,
  and it cannot be reserved.** Measured 2026-08-12 while closing `(acw)`, which had listed it as
  *"Not covered here and worth the same look... Unmeasured."* Now measured.
  - **The number:** writing a realistic finished-verify card into `#verify-result` moves
    `#bk-preview` **+92.4px**, against the 17.4px at which a centre-aimed click leaves the button.
    That is three times `(acw)`'s worst case.
  - **`(acw)`'s fix does not reach it and could not.** A hint is a bounded string, so bounding it
    made the reserve exact. A verify result is a **card listing problems** - unbounded by
    construction, exactly like `#drives-list` in `(acd)`, which is why that entry moved the region
    instead of reserving it.
  - ⚠ **The only fixes available are ones deliberately refused for `(ada)`'s reasons.**
    `#verify-result` is in card 1 and `#bk-preview` is in card 2, so moving state below its
    control means reordering the two cards - and `(ada)` says **`(abg)` must re-price this region
    rather than inherit it**, because it is about to put more state there. Choosing an arrangement
    now, against a region whose contents are about to change, is the mistake that entry warns of.
  - **Harm is lower than the number suggests and that is stated rather than assumed:** the block
    lands when the user has just clicked *Check now* and is reading the outcome, not reaching for
    *Preview copy* on the card below. Same argument `(acw)` accepted for the create-failure state.
  - **Do not fix this before `(abg)`.** File it against that work.

- **(ada) THE BACKUPS SCREEN NOW PUTS STATE BELOW THE FORMS, AND A ONE-COPY WARNING CAN FALL BELOW
  THE FOLD.** Split out of `(acd)` 2026-08-11 when that entry moved to `SHIPPED.md`. `(acd)` fixed
  a control that moved under the pointer by rendering `#drives-list` below every control; the cost
  was accepted at the time and is recorded here rather than left inside a closed entry.
  - ⚠ **CORRECTED 2026-08-12: THE PREMISE BELOW WAS ALREADY FALSE WHEN IT WAS WRITTEN, AND THAT
    MATTERS MORE THAN ANYTHING THAT MIGHT BE BUILT FOR IT** - a defect resting on a false premise
    gets re-read and re-proposed by whoever finds it next.
    - *"It now points nowhere"* is **wrong**. The banner carries `data-risk-action="copy"`, and
      `app.js` wires it to `$("bk-source").scrollIntoView({block: "center"})`. **The action works.**
    - Its prose reads *"Copy your library to another drive **above**"*, which **became true** when
      `(acd)` moved the forms above it. The sentence is correct as written.
    - **The user is not unwarned, they are inconvenienced**, and the difference is the whole size
      of this item. The rail's custody strip carries at-risk state (`custody-pips` toggles
      `at-risk`) at **every scroll position**, so the warning is on screen permanently - just in a
      different place from the remedy.
  - **What is genuinely left, measured rather than inherited:** at 1280x800 with one drive, the
    banner's top is at **1035px against an 800px viewport**, so it is below the fold. Adjacency,
    not absence.
  - **What was traded:** the Backups pass deliberately put state ABOVE remedy so the at-risk banner
    pointed down at the copy form. The forms now come first, and the banner renders **inside**
    `#drives-list`, so a user whose files are in only one place meets two forms before it.
  - **Why it was accepted:** a control that cannot be reliably clicked is worse than one met before
    its context. That reasoning holds and is not being reopened here; what is filed is the residual.
  - ⚠ **`(abg)` must re-price this rather than inherit it.** It will put more state into exactly
    this region, and the ordering was chosen against a defect that no longer exists.
  - **NOT REORDERED while closing `(acw)` 2026-08-12, on this entry's own reasoning.** Choosing an
    arrangement now - against a defect that no longer exists, for a region whose contents `(abg)`
    is about to change - is the mistake the line above warns of. `(adg)` is filed against the same
    constraint.

- **(act) AN UNNAMED ROOT IS LABELLED WITH THE LITERAL STRING `Library`, WHICH COLLIDES WITH
  ITSELF.** Recorded 2026-08-10, split out of `(acr)` deliberately rather than folded in: `(acr)`
  is a correctness fix at the moment of naming, and this is a **behaviour change at registration**
  that alters what gets written into a marker on a user's disk. Mixing them would put a change of
  behaviour inside a fix.
  - Three of the four registration sites mint `label=path.name or "Library"`
    (`service/drives.py:310`, `service/organize.py:847`, `cli.py:2010`). `Path("/").name` is `""`,
    so **organizing to a filesystem root** - or any path whose final component is empty - produces
    the literal label `Library`. Two of them are indistinguishable by name, and unlike a folder
    called `Backup` this one was never a name the user chose.
  - **`(acr)` makes it survivable, not fixed.** Two `Library` drives are now told apart by their
    recorded paths wherever they are named together, so this is no longer a wrong pointer. It is
    still a placeholder presented as a name.
  - **Not urgent, and small.** The fallback fires only for a root-like path, which no measurement
    has yet seen in a real catalog. Worth a decision - a better fallback, or refusing to mint a
    label at all and asking - not a rush.

- **(acy) THE NAMING LAYER - characterised across four rounds, measured against what already
  ships, and deliberately NOT built.** Recorded 2026-08-11. The shipped folder rule produces a
  usable name on **9 of the 10 real clusters** in the measurable library; the tenth is the
  cohort-prefix case nothing solves. A ~2B model at IQ4_XS, given the same clusters, was
  **identical-or-worse on 10 of 10 and strictly worse on 3** - it keeps a year the rules strip and
  fills three candidate slots with one reading. Full record and the cluster table:
  `local-naming-research.md` §6.
  - ⚠ **TWO PREMISES DIED, BOTH THE MAINTAINER'S, AND THIS IS THE PART MOST LIKELY TO BE
    RE-PROPOSED.** Someone reading rounds one to four finds four sessions of favourable
    measurement and will reach for exactly these two again:
    1. *"The gazetteer is useful with no model at all."* It is not. On the 16 real unfenced folders
       `cities500` flags **3, all false positives** - two device folders named after people, one of
       which (`Thala`) is a genuine town of 18,230 people, so **no length or population floor
       removes it**. Zero true positives. Additive use is safer and still does not earn 12.9 MB, a
       CC BY obligation and a lookup path.
    2. *"A multi-candidate screen is a shippable first stage."* It is not. The rules already return
       the right name for the real trip cluster, and **only one ancestor level qualifies at 70%**
       (76% against 24% and 27%), so a levels-based stage offers exactly one candidate - today,
       with more code.
    **Both rested on a folder inside the fence**, which is redacted and unreachable, so the case
    for either cannot be re-measured even by someone who wants to.
  - ✅ **WHAT THE FOUR ROUNDS DID PRODUCE, so this does not read as wasted and none of it is
    re-measured if the line reopens:**
    - the model **characterised at a size and quantisation** with real numbers - file size, peak
      RSS, load time, per-string latency, and a full-library extrapolation
    - **IQ4_XS removes overhead, not just weights** - 108 MB of file against 593 MB of peak RSS at
      the 2B size, the same pattern at three sizes - and **KV-cache quantisation is worth 5 MB**
      here, which inverts the advice everyone reaches for first
    - **the "1 GB working ceiling" never existed** - a phrase repeated between two documents with
      no constant, gate or test behind it (`ENGINEERING_STANDARD.md` §4, thirty-fifth member)
    - **§1 was narrowed with a ruling behind it**, so an online naming path is permitted per use
      and nothing else moved
    - **the fabrication class is understood**: every size invented a different confident answer for
      a venue absent from every gazetteer, and none said it did not know
    - **the unsolvable case is named** rather than left to be rediscovered
  - **What would reopen it, and it is one measurement this machine cannot produce:** the same
    10-cluster comparison **on a library whose folders are camera defaults**. The rules' entire
    input is the folder name; where that is `DCIM` they produce nothing, and so does a model
    reading the same nothing - which makes **GPS** (`(acu)`) the candidate evidence for a naming
    helper rather than a language model. Until then the honest position is that this product's
    naming already works as well as anything measured, on the only material available.
  - **Not softened in either direction:** this library's folders were named by hand, so the
    premise that a model reads a *messy* folder better than rules do is **untested, not
    disproved** (§4's twenty-first member). And a decision to build still needs evidence, of which
    there is none.

- **(acv) THE PRIVATE PATHS IN GIT HISTORY ARE ACCEPTED, NOT OVERLOOKED - and the repository goes
  private at launch.** Ruled 2026-08-11. `16d7b14` removed the maintainer's cloud-storage and
  private-folder strings from the working tree; **history still carries them and deliberately
  will.** Recorded because an accepted risk that is not written down is indistinguishable from one
  nobody noticed.
  - **What is exposed**, counted rather than characterised - and named by kind, because this entry
    may not reproduce the strings it is about (the widened guard refused its first draft, correctly):
    the **fenced folder's name** in **15 commits**, the **cloud mount path** in **4**, and the
    maintainer's **home-directory path** in **11**. That last appears in **zero tracked files
    today**, which is the reason this entry exists in this form: **a clean working tree is not
    evidence about history**, and it had already been mistaken for exactly that once.
  - ✅ **What `16d7b14` actually achieved, stated precisely: the leak is STOPPED, not removed.**
    Every future commit is clean, and `test_no_incidental_naming` now bans the terms so a
    recurrence is a test failure rather than a discovery. That is the half that mattered - without
    it the exposure kept widening with each commit, which is a different problem from the one
    already in the log.
  - **Why a rewrite was declined.** `git filter-repo` plus a force-push invalidates every clone and
    **several hundred SHAs cited in the docs** as `file:line` and commit references - the
    provenance trail this project is largely made of. GitHub also keeps unreachable objects
    readable after a force-push until support is asked to purge them, so the rewrite is not even
    self-completing. Days of work and a broken citation graph, to close a window that **closes
    itself at launch**.
  - ⚠ **The residual, stated plainly rather than minimised.** Someone who clones the repository and
    reads old commits learns that the maintainer uses a cloud storage service, and can see
    fragments of his folder tree. **No photos, no catalog, no credentials** - the catalog is
    gitignored and was never committed. That is the whole of it, and it is accepted for the
    remaining public window.
  - ✅ **THE MITIGATION IS A REQUIRED LAUNCH STEP, NOT A MEMORY:** *make the repository private*,
    recorded in `PROJECT_STATUS.md` §2. The repository stays public until launch for the Actions
    minutes and goes private then. A rule that depends on someone remembering is not a control
    (`ENGINEERING_STANDARD.md` §4, twenty-seventh member), which is why this is a checklist line
    with a cited reason rather than a resolution.

- **(acu) POI LOOKUP FROM GPS - the strongest form of location naming, measured and NOT built.**
  Recorded 2026-08-11. Take a photo's coordinates, ask what named buildings are nearby, and a
  folder called `EA Mall` gets `Express Avenue`. The technique is standard - OpenStreetMap's
  Overpass API returns named POIs within a radius - and it is the strongest version of this idea
  **because it RETRIEVES a fact instead of asking a model to recall one.** That is the same
  instinct as splitting place-identification out to a gazetteer: a lookup cannot invent a mall,
  and every model size measured invented one (`Emaar Mall`, `Chennai International Trade City`,
  `Eco Park Mall`, `East Avenue Mall`; the answer is Express Avenue, and not one said it did not
  know).
  - ✅ **It would have worked, and that is measured rather than assumed.** One Overpass query,
    400 m around Express Avenue's coordinates, returned the way `Express Avenue Mall` and two
    nodes named `Express Avenue` / `Express avenue`.
  - ⚠ **But it returns CANDIDATES, not an answer**, which is the part a design has to own. The
    same query returned **60 named features** in that radius - `Royapettah`, `Melody` (cinema),
    `Lifestyle` (clothes), `Escape Cinemas`, a clock tower, a church. Choosing among them, and
    matching the user's `EA Mall` to `Express Avenue Mall`, is a separate decision that the
    lookup does not make. OSM's own naming is inconsistent here (three entries, two spellings),
    so an exact string match is not the bridge either.
  - **The offline cost, as numbers rather than an adjective** (measured 2026-08-11): the full
    planet extract is **94.2 GB** (`Content-Range` on `planet-260803.osm.pbf`), the India-only
    extract **1.6 GB**, against **12.9 MB** for the `cities500` gazetteer. The density is the
    reason, and it is measurable directly: in one Chennai bounding box OSM holds **11,053 named
    POIs against 64 `cities500` rows - 173x**. A name-and-coordinate-only index derived from a
    POI extract would be far smaller than the raw file; **that derived size was not measured**,
    and is stated here as a gap so it is not mistaken for a finding.
  - ⚠ **Three things block it here, and none of them is the technique.**
    1. **There are no coordinates for the case it would solve.** `(kk)` measured GPS on **3.6%**
       of this library - 83 of 2,275 files, from one phone of nine - and the `EA Mall` photos are
       2013-2015, when location was off by default. The evidence this feature runs on is absent
       exactly where the motivating example lives.
    2. **An online lookup sends COORDINATES, which is a location history**, and a far larger
       exception than the folder-name hole §1 was just narrowed to permit. A folder name is a
       word the user typed; a coordinate is where they physically were, per photo. Verified
       2026-08-11: Nominatim's policy is *"no heavy uses (an absolute maximum of 1 request per
       second)"* and *"periodic requests from apps are considered bulk geocoding and as such are
       strongly discouraged"*; Overpass asks for **under ~10,000 requests and under 1 GB per
       day**, shared across ~30,000 daily users. Neither is a production dependency, and neither
       refusal is about our volume - it is what those services are for.
    3. **A self-hosted instance is the server this product does not have.** §2 and §3 are built on
       there being none; standing one up for naming would be a larger commitment than the
       licensing server, which is itself unbuilt and needs its own design pass.
  - ⚠ **Licence, unread and therefore not cleared:** OSM data is **ODbL** (verified on
    `openstreetmap.org/copyright`), the same share-alike family `(acp)` records for timezone
    boundaries. It must be read before any commercial tier ships data derived from it. Recorded
    as a question, not an obstacle.
  - ✅ **Why this is kept rather than refused, and it is the whole reason for the entry.** For a
    user arriving today with a modern phone, GPS coverage is near-total, and for someone whose
    folders are all `DCIM` this is **the best naming evidence that exists** - better than the
    folder name, because there is no folder name. That user is real even though this maintainer is
    not one. §4's twenty-first member is the rule being applied: one library is a test bed, never
    a specification, and `(kk)` already records the same asymmetry for place names. **Do not read
    "3.6%" as a verdict on the feature; it is a fact about a 2013-2014 library.**

- **(acp) GPS-DERIVED TIMEZONE - understood, costed, and deliberately NOT built.** Recorded
  2026-08-10 from the P41 date/timezone measurement. **This entry exists so the idea is not
  re-derived from scratch; the record is worth more than the feature.**
  - **It is a DIFFERENT CLASS of work from the place-name geocoding in
    `reverse-geocoding-research.md`, not a harder version of it.** Naming is a human question -
    Wayanad is a district and not a populated place, Chennai's nearest point is a neighbourhood,
    `Tiruchirappalli` or `Trichy` depends on who is asking - and there is no ground truth, only
    conventions. Timezone lookup asks **which polygon contains this point** and returns one IANA
    identifier: no synonyms, no administrative history, no phrasing expectation. Closed-form.
  - **Cost, for whoever prices it later.** `timezone-boundary-builder` is the standard source,
    **ODbL**, roughly 50-90 MB as GeoJSON and a few MB packed - against the 400 MB download and
    **1,683 MB peak RSS** that GeoNames class P cost. Point-in-polygon has an honest failure
    mode the place-name lookup lacked: a point at sea returns **no timezone**, where the
    nearest-neighbour place lookup confidently returned an island 920 km away.
  - **The asymmetry that would justify it:** a wrong place name is cosmetic and visible - the
    user reads it and shrugs. A **wrong timezone silently moves a photo to the wrong day**, and
    near midnight the wrong month, into a tree the user then trusts.
  - ⚠ **Two cautions, and together they are why this is filed rather than built.**
    1. **It inherits the anachronism problem in a WORSE form than place names had it.** Zone
       boundaries and DST rules change, so a 2013 photo needs the **historical** rule as of the
       capture instant, not today's. IANA `tzdata` provides that, but only if the lookup resolves
       the zone *and then* the rule for that moment - two steps, and skipping the second is the
       silent-wrong-day failure this would exist to prevent.
    2. **Coverage is small.** GPS is on **3.6%** of this maintainer's library and 1-20% of the
       public corpora, so it would answer the question for a minority of photos and still need a
       fallback for the rest.
  - ✅ **And the closing argument: we may not need it.** P41 measured six midnight-straddling
    fixtures end to end and **five of six land correctly**, because Truestill never converts -
    `parse_exif_datetime` strips any offset and keeps the naive local wall clock, which is what
    `DateTimeOriginal` actually means. Placement was **identical across four extreme machine
    timezones**. The one wrong case is `(aco)`, and a timezone dataset is not the cheapest way to
    close it. Reopen this only if `(aco)` is ruled to need correcting rather than reporting.

- **(aco) A STILL WHOSE CAMERA WROTE UTC INTO `DateTimeOriginal` LANDS ON THE WRONG DAY.**
  Recorded 2026-08-10, measured in P41. Fixture: `DateTimeOriginal = 2026:07:31 20:30:00Z`,
  taken in India. 20:30 UTC is 02:00 IST on 1 August, so the photo belongs in `2026-08` and
  lands in **`2026/2026-07/`**. One of six midnight fixtures; the other five are correct.
  - **Why it is the only wrong one.** `parse_exif_datetime` strips `Z` and any `±HH:MM` and
    keeps the digits as local wall clock. That is right for every camera that writes local time -
    which is what the tag means - and wrong only for one that writes UTC into it.
  - ⚠ **A fix is not obvious, and this is the substance of the entry: knowing the stamp is UTC
    does not tell us where the camera was.** Converting needs a local zone, and there are only
    three sources for one, each with a real cost:
    - **GPS** - present on 3.6% of this library, and drags in `(acp)`'s historical-rule problem.
    - **A user-supplied zone** - the `--tz` flag already exists for Takeout, and could apply
      here. Honest, but it asks the user a question they may not be able to answer for a photo
      taken years ago on a trip.
    - **Refusal** - send it to `Undated/` and say why. Loses a date we partly have.
  - **The argument for doing nothing:** the digits are only wrong by the shooter's offset, so
    the photo is at most one day out and usually in the right month. `Undated/` is worse for a
    user than a date that is one day off, and the current behaviour is silently *right* for the
    far commoner camera.
  - **The argument against:** it is silent. The user is never told the stamp was UTC-marked,
    which is exactly the "wrong folder, no explanation" shape. **Reporting it costs nothing and
    is separable from correcting it** - the date-provenance view could say *"this file's time is
    marked UTC and was read as local"* without any zone lookup at all. That is probably the
    cheapest honest move and it is not a fix.
  - ⚠ **`OffsetTimeOriginal` does NOT solve this, and the claim that it would was wrong.**
    Measured across both public corpora, **1,434 stills**: only **25 (1.7%)** carry
    `OffsetTimeOriginal` at all, and in every observed case it **confirms what Truestill already
    assumes** - the digits are local - so placement is unchanged. Of the four UTC-marked stills
    found, the one that could be inspected (`exif-samples/jpg/tests/30-type_error.jpg`, a
    deliberately malformed test file) carries **no `OffsetTimeOriginal` at all**. The tag is
    EXIF 2.31 (2016); a camera broken enough to put UTC in `DateTimeOriginal` is not one that
    implements it. **Reading it would change placement in zero observed cases** - it is
    diagnostic only, and absent in precisely the case a diagnosis would help.

- **(acn) DOES A GPS FIX TIME COUNT AS CAPTURE EVIDENCE? A RULING, NOT A BUG.** Recorded
  2026-08-10 from the independent corpus measurement (`format-coverage-audit.md` §0). Three files
  carry `GPSDateStamp` + `GPSTimeStamp` and **no capture tag at all**, so they land in `Undated`
  while holding a satellite-stamped time. **Truestill already reads both tags** - nothing needs
  building to obtain them, which is why this is a question about what the product will assert
  rather than an extension list. Left open deliberately; the maintainer rules.
  - **For:** a GPS fix is **contemporaneous with the exposure** - the receiver stamped it while
    the photographer stood there. It is strictly better evidence than a filename convention,
    which `(kk)` already accepts and flags for review. And `Undated/` is not free: it is the bin
    a user must sort by hand.
  - **Against:** it is **not the camera's own claim about the photo**. Every other accepted source
    is the device asserting when it made this image; a GPS timestamp asserts when the *receiver*
    had a fix, which can precede or outlast the shutter, and on some devices is a cached
    almanac rather than a live fix. Truestill's promise is that a date is evidence, never a
    guess, and the line between the two is what this decides.
  - **Where it belongs:** with the date-provenance program, beside `(aax)` (`time_known` derived
    from provenance) - it would need its own `date_source` value so the honesty view can say
    *"from the GPS fix"* rather than laundering it into "from the file".
  - ⚠ **Also unresolved: GPS time is UTC.** Adopting it means choosing a local wall clock, which
    is the same problem the video UTC ladder (`(uu)`) exists for. Do not adopt one without the
    other.

- **(adf) A CLI-ORGANIZED LIBRARY LEAVES `path_hint.library` UNSET, so the app has no observed
  destination to prefill.** Found 2026-08-12 while verifying `(abx)` on real material, and
  recorded rather than fixed because the right answer is a ruling.
  - `service/organize.py` writes `LIBRARY_PATH_HINT` after a successful run. **The CLI's organize
    does not.** Measured: 161 real files organized with `truestill organize` leave
    `library_path` at `None` while `files` reads 161.
  - **Nothing is broken today.** `(abx)`'s first-run gate is `no declaration AND no files`, so
    such a library is correctly never re-asked; and `(abx)`'s declared `library.root` is now the
    thing that prefills a destination, which does not depend on the hint at all.
  - **What is worth deciding:** whether the CLI should write the hint too. For it - a user who
    organizes on the command line and then opens the app gets an empty Organized-folder field
    where the app-only user gets a filled one, which is one product behaving as two. Against -
    the hint is an app-side convenience and the CLI has always taken its destination as an
    argument, so writing it makes the CLI carry state for a surface it does not use.
  - Small either way; it is one `set_setting` call or one sentence saying why not.

- **(ace) THE MUTATION RESTORE RULE EXISTS, IS CORRECT, AND WAS VIOLATED TWICE IN ONE DAY -
  MAKE IT EXECUTABLE.** Recorded 2026-08-10. `ENGINEERING_STANDARD.md` §4 item 5 already names
  this exact failure: restoring a mutant with `git checkout -- <file>` restores from **HEAD**, so
  uncommitted work goes with the mutation; the prescribed fix is to save the original *by
  content*, write it back, and assert the file is byte-identical. That text is precise, it names
  the command, and it even names the tell (`grep -c` returning 0 on a restore that should be a
  no-op). It was still violated twice on 2026-08-10 while proving the readiness signal - once
  destroying three edits, once caught only because a scratchpad copy happened to exist.
  **A rule broken twice in one day by someone who can quote it is a mechanism problem, because
  prose cannot refuse to run.** That is the justification for building anything here at all:
  rewording a rule that was already precise would be answering the wrong question. My judgement
  is a `scripts/mutate.py` in the shape
  the repo already uses for its other guards - it takes `(file, anchor, replacement, pytest
  args)`, asserts the anchor appears **exactly once**, holds the original bytes in memory,
  restores in a `finally`, and then **re-hashes the file and fails loudly if it does not match
  what it saved** - so a mutation run cannot end with a modified tree and stay quiet about it.
  Baseline-from-content rather than refuse-on-dirty-tree, deliberately: refusing to run while the
  tree is dirty would force a commit before every proof, and the repo's own ordering puts the
  mutation results *in* the commit message. The prose rule stays; this is the thing that makes it
  unbreakable rather than well-known. Not built, on purpose - the mechanism is worth designing
  once rather than reaching for after the next restore eats something.

- **(aci) A DELETED DECISION BLOCKS DRIVE SAVES UNTIL A RESTORE RECONCILES THEM.**
  Recorded 2026-08-09 while building the decisions save, as the known false positive of its
  loss guard. Closed by restore; recorded so it is not rediscovered as a bug.
  - The save refuses to write a document that would lose decisions the drive already holds, which
    is what protects a re-attached drive from a rebuilt catalog. **A decision the user deleted
    locally looks identical**: the drive still carries it, so every later save reports
    `WOULD_LOSE` and the drive's copy stops being updated.
  - **Reported, never silently resolved.** Guessing which side is intentional is how the other
    direction loses data, and the other direction is unrecoverable.
  - **Restore closes it**: once the two can be reconciled, the user resolves it once and saves
    resume. Until then the drive keeps the older, larger set - the safe direction.

- **(acg) ALBUM MEMBERSHIP CANNOT LEAVE THIS MACHINE - the same class as `(ack)`, waiting.**
  Recorded 2026-08-09 from the schema while fixing `(ack)`. `file_albums` is
  `PRIMARY KEY (file_id, album_id)`: **both are catalog rowids**, and `file_id` is a rowid rather
  than a sha256, so album membership is **doubly** unresolvable on a machine that never saw this
  catalog. Not live only because `gather_decisions` takes album *names* and `apply_decisions`
  reports them under `not_applied` - the albums tables are empty today.
  - **Whoever implements albums inherits `(ack)`'s bug** unless membership travels as content
    hashes. The rule is already written in `decisions.py`'s module docstring: identity travels
    inside the row it identifies. A sha256 does; a rowid does not.
  - **`file_id` is the sharper half.** Even a self-contained album key leaves membership pointing
    at rowids. The document must carry member **sha256s**, which is what the approved plan said
    (`albums: name + member sha256s`) and what the gather does not yet do.

- **(ach) `ApplyReport.skipped_newer_locally` carries two meanings that need opposite words.**
  Recorded 2026-08-09 from code. Deferred **to Stage 4 deliberately**, where the multi-drive
  merge builds the reporting this feeds - Stage 4 widens the channel rather than inventing it.
  - `decisions.py`'s `date_confirmations` loop appends the same field from two branches: one when
    a local confirmation is **newer** (refused, correctly), one when the catalog has **never
    scanned that content**. Nothing is newer in the second case and nothing is overwritten.
  - **The user actions are opposite.** "Your machine has a later correction, the drive's was
    ignored" needs no action. "This drive holds a correction for a photo you have not scanned"
    means: scan the other drive, re-apply. `dict.fromkeys` then collapses both to one entry, so a
    restore hitting both reports one indistinguishable line.
  - The field's own docstring documents only the first meaning, which is how it stayed invisible.
    `(ack)`'s fix added two single-meaning fields rather than a third overloaded one; do the same
    here.

- **(acc) A decisions document on a drive would be found by nothing that currently looks.**
  Recorded 2026-08-09, from code, while building the decisions-on-drive feature
  (`truestill_core.decisions`). **Load-bearing for Stage 4** - moved out of a plan file in
  a home directory and into the repository, because a plan file does not survive a new machine
  and `docs/ui-inventory.md` was lost twice for exactly that reason. **The design itself now
  lives in [`decisions-on-drive-research.md`](decisions-on-drive-research.md)**; this entry is
  one finding out of it, not the design.
  - **CORRECTED 2026-08-09: this entry said "Stages 1-3 landed" and Stage 3 is half of one.**
    `write_decisions` exists, is atomic and is tested - and has **zero callers**. Stage 3 was
    "the write trigger and the file"; only the file was built. **So no document has ever been
    written to a drive**, the ongoing trigger is unbuilt, and so is the first-run-after-upgrade
    write - the one addition aimed at the user most at risk, who has a finished library and has
    stopped naming things. Checked by grep across core, CLI and app, not assumed.
  - **The design.** A copy of the decisions a rescan cannot recompute - trip and event names,
    drive label, settings, dismissed clusters, corrected dates - written as
    `.truestill-decisions.json` beside `.truestill-drive.json` at a drive root. Lose the catalog,
    plug in any drive, the names come back.
  - **NEITHER PATH THAT TOUCHES A DRIVE WOULD NOTICE IT**, checked rather than assumed:
    - `drive.reach_of` reads only the settings path hint and the marker. **It never looks at
      drive contents**, which is exactly why it is cheap enough to run on every listing.
    - `rescan` walks the drive, but `scan_source` prunes hidden entries into a census group that
      is deliberately skipped - *"a dot-file is not a photo"* - so a dotfile at the root never
      surfaces as stray.
    So a user who has just lost their machine, plugged a drive in, and is looking at the screen
    that lists it **would be told nothing**, and the restore path would sit one command away with
    nothing pointing at it. **That is the Adobe failure one step later**: their catalog backups
    existed and users could not find them. Storage was never the problem there either.
  - **SMALLEST HONEST FIX, for Stage 4.** The drive-listing path already opens the marker at that
    root, so reading a sibling costs **one extra `stat` and no walk**. When a reached drive
    carries a decisions document and the catalog holds none for it - the lost-machine case
    exactly - the listing says so and names the restore command. No new scan, no new surface, and
    it appears on the screen someone opens first after plugging a drive in.
  - ⚠ **CORRECTED 2026-08-09: THE LISTING IS THE WRONG PLACE FOR THE CASE THIS ENTRY NAMES**, and
    the error is mine - the finding was approved without checking where the listing looks.
    `_cmd_drives` iterates `catalog.list_drives()`. **On a lost-machine catalog that is zero
    rows**, so it prints the initialise hint and touches no path at all: the sibling `stat` never
    happens for the very user this was filed for.
    - **The lost-machine path is `drives --init <root>`**, which already holds the root, already
      reads the marker there, and already has `--adopt-existing` for re-attach.
    - **The listing keeps its stat too, for the PARTIAL case** - a catalog that exists, a drive
      that is registered, and decisions on it this machine does not have. Neither place covers
      the other, which is why both are wired.
    - **BUILT 2026-08-09.** `decisions.notice_for` decides what to say; both CLI screens print
      it. Measured rather than assumed: the catalog read the listing gained is **0.10 ms** on the
      real catalog against `list_drives`' existing 1.79 ms, and **4.48 ms** on a catalog stressed
      to 501 trips, 2000 events and 2006 skipped clusters - far past any real library.
  - **Not a reason to widen `reach_of`.** Its cheapness is the feature; a listing that walked
    drives would be worse than the problem. The `stat` belongs where the marker read already is.

- **(aca) The app and the CLI disagree about when an organize run needs confirming.** Recorded
  2026-08-08 while making the app's confirm word mode-aware.
  - **The divergence.** The app gates all three modes behind a typed word. The CLI's
    `_confirm_in_place` returns `True` immediately unless `--in-place`, so **copy and move ask for
    nothing at all**. One operation, two ceremonies, decided by which surface the user happened to
    open - the same shape as the clean-empty trash defect, where whether a folder was recoverable
    depended on the surface rather than on the operation.
  - **The word itself no longer diverges**: in-place asks for `move` on both, and copy asks for
    `copy` in the app, which the CLI never asks for at all. What is left is the *whether*.
  - **RECOMMENDATION, recorded although we are not acting on it: close it by RELAXING THE APP,
    not by tightening the CLI.** The typed word is a ceremony for an irreversible act, and it
    should cost something exactly where something is at stake. In-place moves a user's files with
    no copy left behind, which is why it earned a word on both surfaces. Copy writes new files and
    changes nothing; move is guarded by verify-then-delete and by `undo-organize`. Requiring a
    typed word for copy spends the user's attention on the safest thing they can do, and a
    ceremony that fires on everything stops meaning anything on the one case that matters - which
    is the same reason the irreversibility line was reframed rather than shown on copy.
  - **Tightening the CLI instead would be the wrong direction twice**: it would add a prompt to a
    non-interactive surface people script, and it would spread the ceremony rather than aim it.
  - **Not acted on** because it removes a guard, and removing a guard on the strength of an
    argument rather than evidence is how the guard was justified in the first place. It wants the
    maintainer's decision, not an engineer's tidy-up.

- **(aby) Organize screen: copy that repeats itself or explains its own button.** Recorded
  2026-08-08. **Editorial, no behaviour, deliberately kept out of the behavioural fix** - bundling
  it would drag a defect repair through a prose review.
  - *"Originals stay where they are."* is emitted from TWO sites onto one screen:
    `index.html:148` as the radio subtitle, and `app.js:1548` (`modeLine("copy")`) into
    `#org-mode-hint`.
  - The **Look inside** button is explained by a sentence next to it that says the same word:
    `index.html:177` and `app.js:2250`, *"Look inside first to see what is in the folder."*
  - The confirm banner prints the typed-word instruction twice, four lines apart -
    `app.js:1611` in the banner and again in the input label.

- **(abz) Organize shows one population three ways and connects none of them.** Recorded
  2026-08-08, editorial. On one flow: *"2109 photos and videos here"* (`app.js:1468`, from
  `/api/fs/validate`), then *"2,106 photos - 3 videos found"* (the preview summary, split by
  kind), then *"2,109 duplicates"* (`app.js:1974`, `s.exact_dup`). `2106 + 3 = 2109`: the SAME
  files each time, framed first as a location count, then a composition, then a verdict. Nothing
  says so, so the reader must infer that the third number is the first one again rather than a
  new pile of 2,109 things.

- **(abw) An already-named trip is re-asked, and until this commit the answer was discarded.**
  Three findings, recorded 2026-08-08 while checking a premise for folder-name suggestions. The
  first two are **closed here**; the third is **open and deliberately not fixed**.
  - **(1) CLOSED. Already-named trips are re-offered as cards.** `assemble_trip_review` never
    consults `trip_for_day` - its `claimed_days` set means "claimed by a proposal in THIS run".
    `trip_for_day` is called in exactly two places, both at commit time. Proven against the real
    catalog: it holds `('Wayanad', 2014-08-14, 2014-08-17)` and the card is offered anyway.
  - **(2) CLOSED. The screen could not tell.** `ReviewCardPayload` carried no name, so the card
    rendered an empty box indistinguishable from an unnamed one. It now carries `existing_name`,
    from `Catalog.named_trip_days()` (one read, O(claimed days), keyed by DAY so it survives the
    reordering merge and split do). The card shows the name as **text, not a field**, and says
    renaming is not available there - a question that is asked must be answerable.
    - **`existing_name`, not `name`, and the distinction is load-bearing.** The browser already
      uses `card.name` as its own store for what the user has typed (`syncEvNamesFromDom`,
      carried across merge/split by `takeEvNamesByKey`). A catalog name in that field would be
      indistinguishable from something the user wrote, and would be sent back as their answer.
      The plan for this work called that branch "dead"; it is not.
  - **(3) OPEN. `commit_trips` discards a new name for an already-claimed trip.**
    `decision.name` is never read on the `update_trip_days` branch, and `update_trip_days`
    documents that name and slug are untouched. Downstream, `apply_event_review_names` reports
    `"name": name.strip()` - what the user typed - so the reveal row would have named a trip the
    catalog had not renamed. Finding (2) removes the way to reach it from the screen; the code
    path is unchanged.
    - **Why it was not simply fixed.** The discard is deliberate and pinned by
      `test_re_ingest_one_photo_into_a_named_trip_does_not_re_ask`, whose docstring says a
      differing name proves "it is ignored, never used to rename". That pins
      `trip-grouping-research.md` §6 *"Trips must not re-ask"*, which exists so a re-proposal -
      recomputed from a fresh scan, knowing nothing about the name - cannot overwrite a name the
      user chose.
    - **The §6 threat model has no instance today, recorded so it is not re-derived.**
      `commit_trips` has exactly one production caller, `service/trips.py`'s
      `apply_event_review_names`, whose names come straight from the screen's `names[]` array and
      are always user-typed. There is no CLI trips path at all - neither `commit_trips` nor
      `assemble_trip_review` appears anywhere in `truestill-cli`. A re-offered card renders an
      empty box, so doing nothing already sends `null`. Every name that reaches the branch is a
      deliberate keystroke. A folder-name suggestion would not change that: the suggestion is
      never prefilled into `value=` and requires a click.
    - **THE OPEN QUESTION, which decides the cost rather than the staleness.** A trip already
      placed on disk spells its old name in every folder path (`2014-08-14 - Wayanad/...`), so
      renaming leaves the catalog and the disk disagreeing until a migration. That is the same
      forward/reconcile split a layout-template change already uses, and `record_event` already
      renames an event on re-commit with exactly this consequence - but it has not been costed,
      and it is what must be answered before the invariant is broken.
    - **(4) CLOSED. The event half of the screen defect.** `existing_name` is now answered for
      event cards from `Catalog.named_event_signatures()`, so an already-named event shows its
      name as text instead of an empty box, exactly as trips do. **"Already named" turned out to
      be two questions**, and deciding which one is asked was the whole job:
      - **Same signature** - the identical file set, already named. The trip bug again: show the
        name, invite nothing.
      - **Different signature** - membership changed, so this is a NEW cluster that merely
        *overlaps* a named one. It is not that event, and it must still be offered a name.
      Collapsing them silences every cluster that ever grew, or claims named-ness for something
      unnamed. Both are pinned, and a mutation that collapses them fails the second case - the
      difference in behaviour is the feature, not an edge of it. `ExistingNames` carries the two
      keyings side by side (day for trips, signature for events) because the two identities
      genuinely differ; it is one object rather than two loose maps so a third does not arrive as
      a third parameter.
    - **EVENTS HAVE THE IDENTICAL DISCARD, AND THERE ARE FAR MORE OF THEM.** This is the larger
      half of the finding, not a footnote to it. `event_review.commit_catalog` reads
      `event_by_signature` first and, when a row exists, takes its id and **never looks at
      `decision.name`** - exactly what `commit_trips` does. `record_event` would have renamed it
      (`ON CONFLICT(signature) DO UPDATE SET name = excluded.name`); it is simply not called on
      that branch. A library has one trip for every several events - the maintainer's own has 1
      trip against 21 clusters - so by volume this is where the discard actually bites, and it is
      **still live**: `ReviewCardPayload.existing_name` is hardcoded `None` for event cards, so
      an already-named event still renders an empty box exactly as trips did before this commit.
      Fixing the event half needs its own reproduction, because event identity is a membership
      hash (`events.signature`) rather than a day: adding one photo changes the signature, so a
      re-offered event is not always the same object. The SCREEN half of that is now closed by
      (4) above; what remains open is the same thing that remains open for trips - `commit_catalog`
      still discards a name for an existing signature, and nothing on the screen reaches it.
    - Work in progress exists for this and is preserved, not discarded: a `Catalog.rename_trip`
      that decides "did anything change" in its own `WHERE` clause, plus five tests including the
      one that matters - a blank reply must never erase an existing name, or a bare Save would
      strip every named trip in the library.

- **(abs) The ghost-drive rule refuses REGISTRATION and warns nobody else.** Recorded
  2026-08-07 with the fix, and **chosen deliberately rather than discovered** - which is the
  point of writing it down. `ghost_drive_at` is called by `_register_destination` (CLI) and
  `service/organize._identity_for` (app), the two places that MINT an identity. `rescan`,
  `verify` and `backup` read markers and never mint, so the data-loss path does not run through
  them and none of them needs the refusal.
  - **But "refuses to register" and "warns you this is a ghost" are different promises**, and
    only the first exists. Point `verify` at a drive whose recorded path is now an empty folder
    and it reports every copy MISSING - true of the record, and it never says the likely reason
    is that the drive is not mounted. `rescan` would call the whole library UNACCOUNTED for the
    same reason. Both are honest and both bury the one fact that explains them.
  - **The shape is the one-site-of-many again** - `(aak)`, `(abq)`, `(abr)`, the nine cancel
    buttons - so it is recorded as a decision with its reason instead of being found later by
    someone wondering why only two callers know the rule. The reason: minting is irreversible
    custody damage, reporting is not.
  - **What closing it looks like:** the read-only surfaces do not refuse, they *lead with it* -
    "this is where drive X was recorded and its marker is gone" before the counts, so the number
    is explained rather than alarming. That is a wording change on three surfaces, not a rule
    change, and it wants `(aba)`'s reconciliation vocabulary rather than its own.

- **(abt) The unhinted-residue prompt is CLI-only, because the app cannot ask mid-job.**
  Recorded 2026-08-07 with the fix.
  - **What exists.** Minting a drive identity while the catalog holds drives with no recorded
    location prompts for the typed word `new` in the CLI. It cannot be reached from the app:
    `service/organize` registers inside a running job, and a job has no way to stop and ask.
  - **The app is not unprotected, and the difference is worth stating precisely.** App organize
    has always written a path hint (`service/organize.py`), so app users accumulate the
    discriminating fact with every run and `(abs)`'s refusal covers them from the second run
    onward. **The gap is the FIRST run** - a user whose drives were all registered before hints
    existed, organizing into an unmounted mountpoint, gets no prompt.
  - **What closes it is a UI decision, not a core one.** The obvious shape is a **pre-run**
    confirmation on the Organize screen - the typed-confirm component already exists and is used
    for Rearrange and the date bake - shown before the job starts, where asking is still
    possible. The rule and its wording are already in core (`drives_without_a_known_location`),
    so this is a surface, not a second mechanism.
  - **Not urgent for the maintainer specifically:** his own path now records hints on every CLI
    run, so his first-run window closes the next time he organizes with `--apply`.

- **(abr) `rcRunArchives` passes no `onRefuse`, so a refused start would throw.** Recorded
  2026-08-07. One of **15** `runJob` call sites; the other fourteen all pass one.
  - `runJob` does `if (started && started.ok === false) { ...; onRefuse(started); return; }`, so
    an `{ok: false}` from `/api/ingest/archives/run` calls `undefined` and lands in `guarded`'s
    fatal-error banner instead of the refusal card.
  - **Probably unreachable today** - archive refusals are answered at `precheck`, and the run
    endpoint is not known to return `{ok: false}` - which is why this is filed rather than fixed.
    It was found by routing that endpoint to a refusal in a test, not by a real run.
  - **Filed because of the shape, not the severity.** One site of many differing from its
    siblings is `(aak)` / `(abq)` again, and the two before it were each found only after they
    cost something. The fix is one line; the value is that the next reader of `runJob` sees
    fifteen call sites that agree.

- **(abo) The hash cache cannot say "I computed one hash and not the other".** Recorded
  2026-08-07 when that ambiguity produced a live defect: `attach_drive` wrote `perceptual=NULL`
  rows and a later organize preview took them as hits, silently losing near-duplicate detection
  (measured `near_dup=1` -> `0`). **Fixed at the caller** - attach now opens the cache read-only,
  enforced by SQLite - so this entry is the **general** fix, not the outstanding half of that one.
  - **The shape.** `perceptual` is nullable and carries two meanings: *not an image* and *not
    computed*. `HashCache.get` has `need_sha` for exactly this ambiguity on `sha256` and **no
    `need_perceptual` counterpart**. §8 already names this and defers it as a cache **schema**
    change; it is filed here so it has a letter rather than living in a parenthesis.
  - **A third state is the fix**, not a `need_perceptual` alone: without one, a legitimately
    NULL perceptual (a video, a file Pillow cannot decode, an image over
    `MAX_PERCEPTUAL_PIXELS`) misses forever and is re-attempted on every run.
  - **BLAST RADIUS, by code path rather than by any one cache.** Poisoned rows are exactly the
    files an attach HASHED - `linked + unmatched + unreadable`, i.e. every file on the drive not
    already at a recorded `file_copies.relative`. **Measured 1:1**: a 200-file drive in that
    state produced 200 poisoned rows. The app attaches **both** source and target inside every
    backup **run** (`service/backup.py`; the preview is `write=False` and returns before
    hashing, so previews are clean). Whole-drive poisoning is the ordinary case, not the edge:
    a drive organized by the CLI before it registered destinations (`(abe)`), a first-time
    registration of a folder that already holds a library, or any re-attach after copy rows were
    lost. Attaching a 2,000-file drive poisons 2,000 rows, and look-alike detection is off for
    all 2,000 on any later organize that reads those paths.
  - **DETECTION: yes, and nothing runs it today.** `sha256 IS NOT NULL AND perceptual IS NULL`
    on a path with an image extension. Not exact - that ambiguity *is* this entry, and a
    genuinely undecodable image looks the same - but precise enough to act on. Without it a user
    whose cache is poisoned has no way to learn their look-alike detection is off: no error, no
    count, no degraded-mode notice.
  - **REPAIR: targeted, not a `SCHEMA_VERSION` bump.** The bump works - a version mismatch runs
    `DROP TABLE IF EXISTS hash_cache` - and it is the wrong tool, because it drops **every** row
    for **every** user including the exiftool `metadata_json`, which is ~74% of a cold preview
    (measured 0.168 s warm against 12.27 s cold on 2,224 files, 73x). On a cloud mount at the
    measured 3.9 MB/s a full re-hash of a 196 GiB library is **~15 hours**: a repair that
    silently becomes an overnight job. The targeted delete - the detector query above, as a
    `DELETE` - keeps every clean row and its metadata, keeps non-image rows whose NULL is
    correct, and re-hashes only what was damaged.
  - **The zero measured on the maintainer's own cache (1,836 rows, none in that state) says
    nothing about how common this is** and is recorded only so nobody re-derives it. He wrote
    the product and has not exercised the path; attaching a drive is a normal first-day action
    for a real user.

- **(abn) rescan, beyond the report. `truestill rescan` REPORTS; nothing acts on it yet.**
  Recorded 2026-08-07 with the report-only slice. The design note this carries was ruled by the
  maintainer against external evidence: Lightroom's *Synchronize Folder* has been broken since
  LR 6, its 2025 expert advice is "don't use it", and its damage case - a folder capitalisation
  mismatch showing the same images as both missing **and** new, losing all metadata and edits on
  confirm - comes from conflating two operations in one dialog.
  - **THREE CLASSES, not two, and this belongs in `IMPLEMENTATION_STANDARDS.md` when the
    corrective one is built.** *Additive* (new content -> new rows) is safe by construction.
    *Corrective* (known content, wrong recorded path -> `Catalog.relocate_copy`) **overwrites a
    recorded fact**, and is safe **because its evidence is a content hash and not a path** -
    weaken that to name-and-size and the corrective class silently becomes destructive.
    *Destructive* (remove a record) is never automatic.
  - **MEASURED, so the need is not theoretical.** A hand-moved file reaches
    `service/drives.py` line 363 with `sha in attached`: it is hashed, then counted in **no**
    bucket - `attach_drive` returns `linked=0, unmatched=0, unreadable=0, absent=0` about a drive
    whose record names a path with nothing at it. `verify` then calls the same file `MISSING`
    (`(aba)` symptom 1). Detection costs one branch; only the reporting and the repair are new.
  - **THE PROVENANCE-LOSS FINDING, which is our analogue of Lightroom's.**
    `Catalog.forget_organized` drops the copy row and then, when no copy of that content remains
    anywhere, runs `DELETE FROM files` - destroying `captured_at`, `date_source`, `date_tag`,
    `camera_make`/`camera_model`/`lens_model` and `gps_latitude`/`gps_longitude`.
    `date_confirmations` survives only because v15 keyed it on content in its own table.
    **A removal path must never call it.**
  - **EIGHT REFUSALS for whatever acts on the report.** Never write to the drive; never call
    `forget_organized`; refuse removal when anything was unreadable; refuse unless the drive is
    `CONNECTED` (`UNKNOWN` is the normal state for a CLI-only user); never adopt and remove in
    one confirm; never identify by anything but content; never remove the last recorded copy of
    content without naming that consequence; use `relocate_copy`, not `record_copy`, which also
    rewrites `copied_at` and would relabel a 2015 copy as made today.
  - **`(hh)`'s precedent line is wrong and should be corrected when `(hh)` is next touched.** It
    reads *"Precedent: Lightroom's Synchronize Folder, which is the same operation for the same
    reason and is well understood by the audience."* On this evidence it is a **cautionary**
    precedent - the specific thing to design away from - not a model.
  - **`(hh)` and rescan are NOT one feature**, and the line is sharp: `(hh)` runs adopted files
    through the organize pipeline and therefore **writes to the drive**; rescan never does. One
    walk, two consumers - `(hh)` consumes the STRAY list.
  - **STRAY has two sub-cases with different remedies**, deliberately not split in the report-only
    slice: content the catalog has never seen (needs `(hh)`'s full ingest) and content in `files`
    with no `file_copies` row for this drive (needs only a copy row - `(abe)`'s 31 rows).
  - **Not built, with reasons:** directory-mtime filtering (saves at most the ~14 s walk at
    33,000 files, and on a cloud-synced library every folder mtime is the moment the tree was
    uploaded rather than any per-folder history, so it would buy nothing - and confirming a FUSE
    mount updates it on entry add/remove needs a **write** to that mount); an app surface; and
    any repair or removal at all.

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

- **(abe) CLI-organized files were invisible to custody, and pre-existing rows are not repaired.**
  Recorded 2026-08-05, fixed forward the same day in `a0091cf`.
  - **The mechanism.** `organizer.py` has one `record_uploaded` call site, and `file_copies` is
    written only when `drive_uuid` is given. `cli.py` read a drive marker and never created one,
    so `truestill organize` into an ordinary folder wrote a `files` row with **no** copy row: in
    the dedup index, so a re-run skips that file forever, and outside custody, so `verify`,
    `status` and `where` cannot see it. The app never had this - it registers the destination
    before writing (`service/organize.py`).
  - **Fixed forward** by `cli._register_destination`, gated on `--apply`, rclone excluded.
  - ⚠ **Pre-existing rows are NOT repaired**, and that is the open half. On the maintainer's own
    catalog, 31 rows (ids 1-31, all 2026-07-25) sit in this state; every row from 2026-07-27
    onward has a copy. They now surface on Stats as "not on a registered drive".
  - **Is a repair path wanted? Undecided, and here is what it would cost.** A repair cannot be
    inferred: the catalog records no destination for those rows, so nothing knows *which* drive
    they were written to, or whether the files are still there. The honest options are
    (1) re-import from the originals, which the Stats copy already suggests and which needs no
    code; (2) a `truestill adopt`-style scan of a named drive, matching content by hash and
    writing the missing `file_copies` rows - which is `(hh)`, already filed for a related need;
    or (3) leave them and let the Stats count explain itself. **Option 2 is the only one that is
    new code, and `(hh)` would already cover it** - which argues for doing nothing here beyond
    making sure `(hh)` knows about this case.

- **(abf) A fix does not retroactively clean what it prevented.** Recorded 2026-08-05.
  - Row **id=1** in the maintainer's catalog has a `source_path` under a pytest temp directory -
    `/tmp/pytest-of-<user>/pytest-81/test_skip_undated_names_skippe0/src/…` - naming the test that
    created it. A **test run** wrote into a real catalog. (The username is elided here on
    purpose; the load-bearing part is the tmpdir and the test name.)
  - **`(aae)` is recorded as fixed and it was** - `TRUESTILL_DATA_DIR` / `TRUESTILL_CACHE_DIR`
    honoured on every platform, a root `conftest.py` redirecting both for the session, and
    `default_catalog_path` resolved per call so a test can isolate it. Nothing here reopens it.
  - **The point is the general one, and it is why this has its own letter:** a prevention fix
    leaves its own history behind. `(aae)`'s entry describes the stray file it found and deleted;
    this row is a *different* survivor, in a different catalog, still counted today - it is one
    of `(abe)`'s 31. **When a fix stops a class of damage, ask separately whether existing damage
    is being carried**, and record the answer either way. The two questions look like one.

- **(abg) The reassured state has no notion of staleness - "Schrodinger's backup".**
  - 📌 **READ THIS FIRST: THE EXPOSURE RANKING IN THIS ENTRY IS INVERTED, measured 2026-08-10 on
    the maintainer's own catalog.** The 395 on `Morrowkeep` are **already reported** - `status`
    says *"395 file(s) exist on only ONE drive"* and names the drive. The user is being told.
    The silent case is the other one: `Output` and `The Memory Cabinet` hold the **same 2,269
    files** (full overlap, checked), so those read as **safe in 2 places** - while `Output` is
    reachable, carries its marker, and contains **zero media files**. Nobody is told anything.
    **It is larger, it is silent, and it is the only one that is checkable.** Lead any fix with it.
  - ⚠ **AND `Morrowkeep` CAN NEVER LEGITIMATELY REACH `GONE`.** Its path is absent because the
    **entire cloud mount it lived on is absent**, so *gone* and *unplugged* are indistinguishable there. A
    `GONE` that fired on it would be the cry-wolf failure on the very case that motivated this
    entry. Reachability is a **precondition** for the state, not a detail of it.
  - ⚠ **`GONE`'s justification is narrower than this entry claims, and the narrower one is the
    real one.** `OFFLINE` is not "we have not looked recently": `drive_reach` is a **live** marker
    read and `drive.py:128` says verbatim *"we know where it was; it is not there now"*. So `GONE`
    is **not** the first state meaning we looked. What it adds is **durability** - it persists an
    observation that is currently computed and thrown away (`service/verify.py:72-79` produces
    `CopyStatus.MISSING` per copy and records nothing; `mark_copy_verified` fires only on
    success). A narrower claim honestly stated beats a flattering one.
  - ✅ **STAGE 2 SHIPPED 2026-08-11 - and it leads with a defect STAGE 1 INTRODUCED.** Stage 1
    carried `drives.last_verified` to the sentence a person reads. It did not ask what advances
    that date, and the answer was: every verify run, unconditionally, on both surfaces. So a run
    whose own summary said `missing: 2269` reported the claim as **checked today**, and so did a
    run cancelled at the first file. That is this entry's own thesis - history reported as state -
    reappearing inside this entry's own fix, and it is worse than what Stage 1 addressed: Stage 1
    made the claim datable and the date meaningless. Recorded as `ENGINEERING_STANDARD.md` §4's
    **thirty-sixth** member, because the mistake generalises to any freshness field.
    - **The drive's date is now DERIVED from its copies**, `MIN` and NULL the moment any copy has
      never been confirmed - which covers missing, unreadable, unverifiable and *not reached
      before the user cancelled* without enumerating them. Not a new rule: it is
      `custody_freshness`'s own weakest-leg argument one level down. Structurally incapable of
      over-claiming beats correct while every call site remembers.
    - **Rejected: "do not stamp when anything failed."** One `UNREADABLE` file on a 10,000-copy
      drive would leave the claim permanently undated. A different lie is still a lie.
    - **v19 `file_copies.missing_at` persists what verify already computed and threw away.** Only
      `MISSING`: `UNREADABLE` is *we could not look* and `MISMATCH` is a drive still holding
      something at that path - different facts needing different words, `(ach)`. **The row is
      never deleted**; it is the only remaining clue that content was once written there.
    - **TWO PRECONDITIONS WERE ALREADY STRUCTURAL AND WERE NOT BUILT. Do not "fix" the second.**
      `verify_run` starts by reading the marker and soft-fails without one, so `Morrowkeep` -
      where *gone* and *unplugged* are indistinguishable - **cannot reach the code at all**. And
      `verify_copies` answers every `MISSING` in `_partition`, **before any hashing starts**, so a
      cancelled run's set of absences is complete rather than truncated. The second is
      counter-intuitive and is what makes persisting from a cancelled run sound.
    - **Two counting rules, deliberately opposite.** A custody **promise** excludes what was looked
      for and not found (`custody_floor`, `single_copy_count`, `single_copy_shas`,
      `drives_holding`). A **history** gains a number rather than losing one: the drive card keeps
      `files` and adds `not_found`, so `Output` reads *"2,269 photos … 2,269 not found on
      2026-08-11"*. A count quietly dropping to zero destroys the only clue to what happened.
    - **Mutation found a hole reasoning did not:** removing the `missing_at = NULL` from
      `mark_copy_verified` killed no test, so a restored drive would have stayed uncounted with
      nothing the user could do. `ENGINEERING_STANDARD.md` §4's **thirty-seventh** member.
  - ⏳ **WHAT IS STILL OPEN IS STAGE 3, AND IT IS THE HARDER HALF: instance (2), `Output`.** Its
    marker went with its contents, so `read_marker` returns `None` and verify soft-fails - *the
    drive most in need of examination is the one the tool cannot be pointed at*, which is this
    entry's own line and is untouched by Stage 2.
    **The obvious route was examined and refused, so it is not re-derived from scratch:**
    `drive_reach` folds two different observations into `OFFLINE` - *the remembered path is not
    there* and *the remembered path is there and is not this drive*. Splitting them is one `stat`
    and would name `Output` exactly. **It would also name an unmounted USB drive whose mountpoint
    directory persists**, which is ordinary on Linux and is the cry-wolf case wearing the other
    case's clothes. Telling those apart needs `filesystem.facts_for()`, which already parses
    `/proc/mounts` and which custody has never consulted. **That is the design question Stage 3
    owns**; inventing an answer inside Stage 2 would have put a guess where `DriveReach`'s own
    docstring says to report the honest third answer.
  - **Related, and filed separately because it is a different defect:** `(acq)` - "place" counts
    somewhere Truestill organized INTO, not somewhere a copy is kept.
  - **THE MOST IMPORTANT OPEN ITEM ON THIS PROJECT.** Everything below is evidence for the
    paragraph that follows; the paragraph is the point.
  - **THE GENERAL CASE, in the maintainer's framing.** A user copies A -> B. Truestill records two
    copies. The user then **deletes A**, which is normal and is often the whole point of
    organizing. Truestill never looks at A again. **It keeps reporting two places for files that
    now exist in one.**
    Every instance recorded here is that shape with a different cause - a queued write that never
    uploaded, a folder emptied by hand, a mount that vanished. **The defect is none of those. It
    is that the catalog reports HISTORY as if it were STATE.** A `file_copies` row is a true
    statement about the moment it was written and is read as a true statement about now.
  - **WHAT THE CODE SAYS, checked rather than assumed.**
    - **Nothing re-checks a `source_path` after the copy that recorded it.** The only code that
      looks is `reclaim`, which counts `missing_sources` - *"catalog rows whose source_path is
      gone / unreachable"* - and it looks only when a user runs it, for a different purpose
      entirely: deciding what is safe to free. **Custody never asks.** A source deleted the day
      after an organize is indistinguishable, to every count in the product, from one still there.
    - **The custody count carries no freshness.** `last_verified` exists on both `file_copies` and
      `drives` and is surfaced per-drive in the drive list and in stats - but `library_status`,
      which produces the number a person actually reads, counts `file_copies` rows and **never
      consults it**. So *"kept in 3 places"* appears with no date beside it, and it is a claim the
      system cannot back: the data to qualify it is recorded and simply not carried to the place
      the claim is made.
  - **THE JOB IS SMALLER THAN "ADD FRESHNESS TRACKING".** `last_verified` already exists on
    `file_copies` and on `drives`, and is already surfaced per-drive in the drive list and in
    stats. `library_status` - which produces the number a person actually reads - never consults
    it. **So this is not building a new capability. It is carrying data that already exists to the
    place the claim is made.** That changes the size of the work and should be stated before
    anyone scopes it as a schema project.

  - **PRIOR ART, and it is better than anything invented here.** `git-annex` solved this directly:
    - **Believed versus verified.** `Annex/NumCopies.hs` states that the ordinary count compares
      copies *"believed to exist"*, and that this *"is good enough for everything except dropping
      the file, which requires active verification of the copies."* **Truestill counts believed
      copies and presents them as custody. That is the defect in one line**, and it is the
      distinction this entry has been circling.
    - **It refuses what it cannot back.** `drop` fails with *"Could only verify the existence of 0
      out of 1 necessary copies"* rather than deleting on the strength of a record.
    - **It arrived independently at `GONE`.** Its trust states are trusted / semitrusted /
      untrusted / **DEAD**, where dead *"indicates the repository has been irretrievably lost."*
      Corroboration for the name, from a system that has lived with the problem for years.
    - **Anything another process can write to is untrusted BY DEFAULT.** `importtree` remotes are
      always untrusted, on the stated grounds that something else could delete or change any file
      at any time, so trusting one for the only copy would cause data loss. Amazon Glacier is
      untrusted because its inventories may not represent the current state. **There is no
      category of place Truestill writes to that this does not describe** - every destination is a
      folder on a disk the user also uses. That is the general statement; the three instances
      below are only evidence for it.
    - **Consumer prior art for the interface.** Lightroom badges missing photos with an
      exclamation mark, greys missing folders with a question mark, and offers
      *Library > Find All Missing Photos*, which users run as weekly housekeeping. It does not
      prevent editing outside the app; it **detects and marks**. One documented gotcha worth
      inheriting the lesson from: that count is **not dynamic** and refreshes only when re-run, and
      users are confused by the stale number - which is this entry's defect in a competitor.
      Immich moves external assets to trash on rescan when they vanish.

  - **SETTLED PRODUCT DECISION (the maintainer, 2026-08-09).** **Organizing is the product.
    Custody is a REPORT, not a promise.** Truestill will not become responsible for backups: no
    scheduling, no monitoring, no syncing, nothing requiring a daemon it has decided not to have.
    Custody exists only because copying inevitably teaches Truestill where things went, and that
    knowledge is reported as **dated fact**, never as an ongoing guarantee.
    **The consequence is the direction the fix should take:** *"kept in 3 places"* is a claim the
    system cannot back. *"394 files copied here on 7 August, not checked since"* is a fact that
    **cannot go stale - it only gets older.** Same data, no promise.

  - **SHOULD A SOURCE EVER HAVE COUNTED AS A COPY? It never did, and the premise is worth
    correcting because it moves the defect.** Checked: `file_copies` is keyed
    `(sha256, drive_uuid)`, a source has no `drive_uuid` and never gets a row, and
    `library_status` reads `file_copies` and not `source_path`. **Truestill already agrees with
    `git-annex` here** - the folder a user is about to empty was never counted.
    So the 2,269 were **destination** copies, genuinely written to a registered drive, and the
    failure is not that a source was trusted. It is that **a destination copy is written once and
    never looked at again.** git-annex's answer applies anyway, just one step further along: a
    destination is *also* a place another process can write to, which is exactly why it treats
    such remotes as untrusted by default.
    **What the count should have said all along:** not *"2,269 files in 2 places"*, but
    *"2,269 files copied to Output on 28 July 2026, not checked since."* Both sentences carry the
    same data. Only the second stays true after the folder is emptied.

  - **THE SHAPE OF A FIX - a design note, not a TODO, because it is schema and vocabulary and
    wants thinking rather than a patch.** Truestill needs a drive state meaning **"recorded, and
    the place it was recorded no longer exists"**, distinct from `offline`, and **custody must
    exclude it from the count.**
    - **Suggested name: `GONE`.** Not `missing` - that reads as "we cannot find it", which invites
      looking again, and is what `offline` already implies. Not `lost`, which sounds like
      Truestill's fault and may be untrue. `GONE` is short, unambiguous, and admits no hope of
      the drive coming back on its own. The existing `DriveReach` triple is
      `CONNECTED` / `OFFLINE` / `UNKNOWN`, and `GONE` sits naturally beside them as the fourth:
      the three current values all mean *we have not looked recently*, and this one means
      *we looked, and it is not there.*
    - **What `status` should say.** Not *"exists on only ONE drive (3-2-1 wants >=2)"*, which is
      what it says today about 395 files that have **no** copies. It should lead with the count it
      can stand behind and name the shortfall separately - along the lines of
      *"2,300 files in 2 places. 395 files have NO copy: recorded on 'Morrowkeep', which is gone."*
      The number a person reads must never include a drive in this state, and the drive must be
      named, because the name is the only clue to what happened.
    - **Why a label is the wrong lever, recorded so it is not tried.** Renaming the drive
      `Morrowkeep (gone)` makes the list read better while the count stays wrong. **A cosmetic fix
      on a wrong number is worse than the wrong number, because it looks handled.**
  - **THREE OBSERVED INSTANCES, 2026-08-07/09, on the maintainer's own library. None is
    hypothetical.** Ordered by exposure, not by discovery.
  - **(1) THE WORKED EXAMPLE - written, believed, verified in place, and gone.** Follow one
    instance the whole way, because it is more instructive than the abstract statement:
    1. **Written.** An organize run copied 395 files to a cloud-mount destination. Every write
       returned success, so custody recorded a second copy.
    2. **Believed.** `status` counted all 395 toward the 3-2-1 goal for two days.
    3. **Verified in place.** `rescan` reported *"395, where the catalog says they are"* in
       **0.15 s** - the local index answering, not the disk. Not wrong by its own definition: it
       states that it reads no bytes. **The definition is the defect.**
    4. **Never actually stored.** The vendor's server index held about 5 of them; 391 sat behind
       an upload task dated 18 July that never moved.
    5. **GONE.** The vendor application was uninstalled on 2026-08-08 and its cache directory went
       with it. **Those 395 organized copies no longer exist anywhere.** Verified: the cache
       directory absent, the mount absent from `/proc/mounts`, free space back to 65 G.
    **And the catalog asserted custody at every one of those five steps**, including the last.
  - **THE VOCABULARY GAP IS THE FINDING.** After all of that, the drive list still reads
    `Morrowkeep  395  offline  LAST VERIFIED: never`, and `status` reports the 395 as
    *"exist on only ONE drive (3-2-1 wants >=2)"* - **recommending a second copy for files that
    have none.** `offline` is the same word the system would use for a USB disk in a drawer, and
    it is the closest thing available. **There is no state meaning "recorded, and the place it was
    recorded no longer exists".** Until there is, the honest answer and the reassuring one are
    spelled identically.
  - **WHAT WAS NOT LOST, so this is not read as a data-loss story.** The 2015 originals are on the
    vendor's servers, untouched, and `TruestillLibrary/Input` still holds the sources. **What was
    lost is an organize run, not photographs** - the arrangement, the naming and the placement,
    all of which can be produced again from material that still exists. The cost is real but it is
    work, not memory.

  - **(2) 2,269 copies recorded on an empty folder, and the tool cannot look.**
    `TruestillLibrary/Output` was emptied by hand - 0 files, 0 bytes - having held 2,269 files
    when `rescan` checked it the same day. The catalog still records 2,269 copies there and
    `status` still counts them. **`rescan` refuses**: the drive marker went with the contents, so
    it answers *"isn't a Truestill drive yet"*. **The shape is worth naming on its own - the drive
    most in need of examination is the one the tool cannot be pointed at.**
  - **(3) A write accepted into a queue and recorded as a copy.** The original instance: a cloud
    mount returns success for a write that has only been queued locally, and custody records a
    second copy on the strength of the return value.
  - **METHOD - how to tell a cache read from a server read on a cloud mount, with numbers.**
    Measured on this mount: **cache reads 2-92 ms; cold server reads 3.9 MB/s.** A 6.3 MB file
    therefore takes about **1.6 s** from the server and about **85 ms** from cache, so **a read
    faster than roughly `size / 3.9 MB/s` did not come from the server.**
    Written down because it is the check that would have caught a wrong conclusion in this very
    investigation: 13 files were hash-verified off the mount in 2-92 ms and reported as proof the
    server held them. It was proof the *cache* held them. The argument rested on the cache having
    been emptied, which the same turn had already measured to be false (38.73 -> 40.35 GB).
    **Anyone measuring a cloud mount will make this mistake without the ratio in front of them.**
  - **THE PRODUCT FINDING, and it is not the clean negative it looks like.** Truestill cannot read
    another vendor's private database and will not ship that. But **it is not true that no signal
    exists. Truestill HAS signals it does not use, and none of them proves storage.**
    - `filesystem.facts_for()` **already** parses `/proc/mounts` on Linux and queries Windows
      directly. It would return `fuse` for this mount. Archive ingest consults it for FAT32 size
      limits; **custody never consults it at all.**
    - `archive_extract.py` **fsyncs and documents why**, while `LocalDestination.upload` is
      `shutil.copy2` with no flush. The write path that records custody never asks the filesystem
      for durability. On this mount `fsync` would very likely return success anyway - but then the
      false statement is the vendor's, not Truestill's silence.
    - A **vendor-neutral tell** exists and was measured: writing 3.39 GB to this mount grew local
      disk usage by 3.41 GB, **1:1**. A destination whose writes grow *local* storage by the same
      amount is being cached locally, whoever makes it. No private database required.
    - **None of the three proves storage.** All three can distinguish "not obviously a local
      disk"; none can say the bytes are on a server. So: **custody today cannot distinguish
      WRITTEN from STORED, and does not even distinguish LOCAL from NETWORK-BACKED, which it
      could.** That is a finding about the product, not about one mount.
  - **Record only. Nothing here is fixed**, and no catalog row, drive or file was modified in
    reaching it.

  Recorded 2026-08-05. **Record only; the product question wants soak evidence, not a design.**
  - **What the strip claims.** "every file in 2 places" is true of the **catalog record**, not of
    the disks. `library_status` counts `file_copies` rows and never consults reachability:
    **offline drives, drives whose location was never known, and drives never verified all
    count.** `last_verified` is recorded on every copy and **is not read on this path**.
  - **Why the wording already hedges.** "safe" was removed from the strip on 2026-08-05 precisely
    because recorded copies are not verified copies; it says where files are, which is what the
    catalog knows. So this is a known limit that is *stated*, not a lie - but the reassurance
    still does not age.
  - **The forum name for it is "Schrodinger's backup": never tested, so simultaneously valid and
    invalid.** A copy written two years ago to a drive not seen since reads identically to one
    verified this morning.
  - **The product question, deliberately unanswered:** should the claim decay - a verified-within
    window, a "last checked N months ago" qualifier, or a distinct state once a drive has not
    been seen for long enough? Every version risks nagging about a drive-in-a-drawer that is
    perfectly fine, which is exactly the trade `(gg)` and the risk-first strip ruling had to make
    elsewhere. **Soak is the instrument**: real usage will show whether stale reassurance is a
    real complaint or a theoretical one.
  - The data is already there - `drives.last_verified`, `drives.last_seen`, and `DriveReach` -
    so this is a wording-and-policy question, not a plumbing one.

- **(abm) Attach counts three things and shows none of them.** Recorded 2026-08-06 while fixing
  the walk that produced the third.
  - `DriveAttachment.unreadable` (files), `.unmatched` (on the drive, unknown to the catalog) and
    now `.unreadable_dirs` (folders that could not be listed) are all computed, tested, and read
    by nobody: `service/backup.py` uses `src.linked + tgt.linked` for `will_read` and **discards
    the return value entirely on the run path**. So a drive can attach with folders skipped and
    the screen says only how many files were linked.
  - **Deliberately not fixed with the walk.** The walk fix stops the fact being *destroyed*;
    showing it is a payload key plus a render plus a browser test, and doing one of the three
    siblings would leave the other two - which is how they got here.
  - **`service/fs_browse.py:188` rides along.** Its `rglob` undercounts a locked subfolder in the
    browse dialog's media estimate. Left as `rglob` on purpose: that number is already advisory
    and already truncated by `cap` (`media_capped`), which distorts it more than a locked folder
    does, and there is nowhere on a file-picker row to name a folder. Swapping the walk without a
    surface would recreate exactly the computed-and-dropped value this entry exists to close.

- **(abk) The library has no per-folder view - "where is all this actually sitting".** Recorded
  2026-08-05, dropped from the resting panel because the data does not exist rather than because
  it is not wanted. A person with 2,300 files knows the total and knows nothing about the shape
  of it on disk.
  - **The query shape.** `files.relative` already holds the organized path, so the folder is its
    parent. One aggregate, no new column and no new table:
    `SELECT substr(relative, 1, length(relative) - length(replace(relative, '/', '')) ...)` is
    the fiddly way; cleaner is to compute the parent in Python over
    `SELECT relative, size FROM files` for a first cut, and only push it into SQL if the row
    count makes that slow. Group by parent, `COUNT(*)` and `SUM(size)`, order by size, cap the
    list and state the total - the `{total, shown}` discipline, not a silent top-N.
  - **Which parent depth.** `2019/2019-07/2019-07-04 - Wayanad/` is three levels; grouping at
    the leaf gives one row per day and is useless at library scale. The useful grouping is
    probably the YEAR or the event folder, and that is the design question, not the SQL.
  - **Where it goes:** the Organize resting panel, and Stats' Shape card, which already answers
    the same question by year and by format and is the natural home for a third axis.
  - **Not a payload key going unused** - unlike the facts already surfaced, nothing computes
    this today, so it is a new aggregate rather than a wiring job.

- **(abj) Find matches one substring; a two-word query silently finds nothing.** Recorded
  2026-08-05. `find_copies_query` builds `%term%` and ORs it across `original_name`, `relative`
  and `source_path` - no whitespace split, no AND. So `beach 2019` matches only that literal
  string, and a photo at `2019/2019-07/2019-07-04 - Beach/` never has it. **The placeholder that
  taught exactly this query is fixed; the search is not**, because splitting is a behaviour
  change and belongs in its own commit.
  - **The shape of the fix:** split on whitespace and AND the terms, one `LIKE` per term over
    the same three columns. `2019 beach` and `beach 2019` then both match, which is what a
  person expects from a search box.
  - **What it costs:** three `LIKE '%x%'` per term, all unindexable. `(bbb)`'s paging guard
    `EXPLAIN`s the shipped statement, so the cost is measurable before it is accepted, and
    `FIND_PAGE_SIZE` already bounds what is returned rather than what is scanned.
  - **Not free to get wrong:** an empty term, or a term that is only spaces, must not become
    an unfiltered scan of every copy.
  - **MEASURED 2026-08-09, and it reframes the whole entry: this is an FTS5 question, not an
    index question.** `find_copies` plans as `SCAN file_copies` on the real catalog, and **no
    index can change that** - a leading-wildcard `LIKE` defeats a B-tree by construction, so
    adding one would cost writes and buy nothing. The 2026-08-09 catalog audit checked every
    other query for missing indexes and found none; this is the only scan that is a *design*
    consequence rather than an oversight. Measured cost today: **4.59 ms at 2,695 files, 2.15 ms
    once `ANALYZE` had run** - so the AND-the-terms fix above is affordable now, and FTS5 over
    the searchable columns is the answer if Find ever needs to be fast rather than correct.
    See `PERFORMANCE.md` §7.

- **(abi) The geometric pillar T reaches nothing.** Recorded 2026-08-05. `brand/pillar-t-geometric*.svg`
  is committed and pinned, but `scripts/build_brand_assets.py` still generates every icon and the
  ICO from the Libre Caslon font, so the mark is in the repo and in no output. Wiring it means
  teaching that script to consume an SVG, and deciding whether the T replaces the `TS` monogram
  (one mark or two). Blocked on a dark-rail ramp - the current stops measure 2.45:1 and 1.11:1 on
  `#14161b`.

- **(abc) `check_product_name.SUBCOMMANDS` should be derived, not transcribed.** Recorded
  2026-08-04, when Analyze 3b tripped over it: the list had never gained `analyze` or
  `repoint-sources`, so writing either invocation in prose was flagged as the product name in
  lowercase. Both entries were added; the class was not fixed.
  - **Why it is a class and not a typo.** The guard's own docstring says the list *"mirrors the
    parser rather than guessing"*. It does not mirror anything - it is a copy, and it has now
    drifted twice. Same shape as the `ALL_RULES` tuple in `test_layout_scheme.py`, which stopped
    covering the one rule whose routing had changed, and was fixed by deriving it from the enum.
  - **Why it was not done here.** The authority is `cli.py`'s dispatch table, so deriving it
    means a repo script importing `truestill_cli` - a direction nothing in `scripts/` currently
    takes, and one that changes what `make check` needs installed to run. That is its own
    decision, not a footnote to a streaming commit.

- **(abb) The other capture-filename conventions.** Recorded 2026-08-03, when
  `rule_camera_filename` shipped with **one** pattern: Android's `IMG_`/`VID_` plus a full date
  and time, verified against the AOSP Camera commits that introduced it. Deliberately scoped to
  the convention the real library actually held.
  - **What is not covered, and why each is a separate decision rather than more regex.**
    `PANO_`, `MVIMG_` (Google Motion Photo) and `TRIM_`/`VID_TRIM_` share the date-and-time
    shape and are plausibly the same rule. `IMG_1234.JPG` (iPhone, Canon), `DSC_2286.JPG`
    (Nikon, Sony) and `P1010101.JPG` (Panasonic, Olympus) are **not**: they are counters, they
    carry no capture record, and a rule claiming them would put every unlabelled file with a
    camera-ish prefix onto someone's timeline on the strength of three letters. That is the
    cry-wolf `test_camera_filename_convention.py` already pins against, so widening this needs
    an argument, not an entry.
  - **What would make the counter conventions safe** is a second signal - a plausible capture
    date from somewhere, or sibling files sharing the convention in one folder - which is a
    different rule shape from a filename table and should not be smuggled into one.
  - **Cost of being wrong is asymmetric and worth restating**: a file wrongly left in `Saved/`
    is findable, and a file wrongly placed among the owner's own photos is not.

Everything here has work left. **Two entries are partial and say so in their own text:**
`(bbb)` (the safety half shipped, the `_original` recovery offer did not) and `(r)` (the hash
cache shipped, Analyze mode itself did not). A partial entry lives here, not in the built
section, because what is left is the part that still has to be written.

- **(aba) Nothing reconciles the catalog's recorded location with where a file actually is.**
  Found 2026-08-03 by tracing what happens when a user tidies by hand - the maintainer moved a
  file out of `Saved/` into its trip folder after an organize. **Three symptoms, one root
  cause**, filed together because they share it and would otherwise be fixed three times; each
  is separately actionable and separately ranked below.
  - **The good news first, so nobody "fixes" it into a regression.** With the catalog that
    recorded the run, **no organize path undoes a hand-move**. `DedupIndex.from_catalog_rows`
    seeds from `(source_path, sha256, perceptual)` - **content, not location** - so a re-run
    matches the unchanged source and `execute` skips it before any write path:
    `if resolution.exact_duplicate is not None: ... continue`. The destination is never
    examined. Confirmed on a real 2,109-file re-preview: 2,108 exact duplicates.
  - **SYMPTOM 1 - `verify` reports a hand-moved file as MISSING. A real defect, and the one to
    fix.** It re-hashes each recorded copy, finds nothing at `files.relative`, and returns
    `CopyStatus.MISSING` - *"the file is gone from the drive"* - while being entirely blind to
    the same bytes sitting safely at the new path. **This is the worst possible place for a
    false alarm**: `verify` is the feature whose whole value is being trustworthy, and a user
    who tidies one folder and is then told twelve files are missing learns to ignore the report
    - including the run where something really is gone. The likely fix is cheap: on a miss,
    look for the content elsewhere on the drive before saying "gone", and distinguish *"not at
    the recorded path"* from *"not on this drive"*. **Do not simply reword it** - a file that
    genuinely vanished must still be loud.
  - **SYMPTOM 2 - `--in-place` on a FRESH catalog silently reverts the move.** Narrow, but it
    is literally "Truestill undid my tidying". `_already_at_target` is the only thing that
    would move a file back, and it sits *downstream* of the duplicate skip, so a live catalog
    never reaches it - its own docstring says so: *"With a live catalog dedup catches this
    first; on a fresh catalog this is the only thing that does."* With a different `--db`, a
    lost catalog or a re-clone, dedup is empty, the check compares the file's current path
    against the **rule-derived** target, finds they differ, and moves it back. Journalled, so
    `undo-organize` reverses it - but silent at the time.
  - **SYMPTOM 3 - a changed-layout migration halts on a path that no longer exists.**
    `plan_migration` plans from the catalog, so it computes `old -> new` from the recorded
    `relative`. With the layout unchanged the file falls into `plan.unchanged` and nothing
    happens; with the layout changed it plans the move, `relocate` finds `old` absent and
    raises `cannot relocate missing copy: <old>`, **halting the whole migration**. Loud, which
    is right, but it names a path and not the cause - a user who tidied three weeks ago cannot
    connect the two.
  - **`ALREADY_PLACED` never covered this**, checked rather than assumed: set in exactly one
    place, gated on `relocation is not None` (in-place only), and it asks
    `(dest_root / computed_relative).samefile(source)` - *"is this file where the rules say"*.
    A hand-moved file is by definition not, so it reads as "needs moving". It recognises a file
    **Truestill** placed, never one the user did.
  - **Why one entry and not three, stated because three were asked for.** The three share one
    cause - a recorded location that nothing ever re-checks - and the fix for symptom 1 (find
    the content elsewhere before declaring it gone) is most of the fix for the other two. Three
    entries would fragment one design question and invite three partial repairs. All three are
    named, ranked and separately actionable above.

- **(aaz) `ModifyDate < DateTimeOriginal` as a back-dating signal. RECORD ONLY - do not build.**
  Filed 2026-08-03 alongside the future-date refusal, which found its case on the real library.
  - **The signal.** A file cannot logically be modified before it was created, so
    `ModifyDate` earlier than `DateTimeOriginal` is characteristic of a date that was edited
    after the fact. It would catch back-dating, which the future check cannot: a date moved
    *backwards* is not impossible, merely wrong.
  - **`ModifyDate` is NOT in `REQUESTED_TAGS` today** (checked, not assumed), so this is not
    free. Adding it changes `tags_fingerprint`, which invalidates every cached metadata row and
    forces one cold exiftool pass over the whole library - the same cost profile recorded for
    `GPSAltitude`. That is the reason this is filed rather than built.
  - **And the signal is weaker than it looks.** Any lossless rewrite - our own metadata bake
    included - updates `ModifyDate`, so a true positive and an ordinary edit are the same
    shape. It would need to be reported as a question, never as a verdict.

- **(aay) JPEG XL (`.jxl`) is classified as unrecognized. RECORD ONLY - do not build.**
  Found 2026-08-03 by running `truestill analyze` over a deliberately format-diverse corpus,
  which put 7 `.jxl` files in the skipped census.
  - **It is genuinely media.** JPEG XL is an ISO/IEC 18181 still-image format, not an oddity,
    and it is a plausible future capture format rather than only an archival one.
  - **Recognising it is not enough, which is why this is recorded and not fixed.** Pillow still
    has **no native JXL support** (checked 2026-08-03); it needs the third-party
    `pillow-jxl-plugin` (Rust bindings, actively maintained). Adding `.jxl` to
    `IMAGE_EXTENSIONS` without that plugin would produce files truestill dates and categorises
    but **cannot perceptually hash** - near-duplicate detection silently absent for a format we
    just told the user we support. Exact dedup would still work.
  - **So it is a dependency decision, not a one-line extension.** §7's stdlib-first policy
    applies, and the honest options are: add the plugin and support JXL fully; or leave `.jxl`
    unrecognized, which is at least never-silent because the skipped census names it.
  - **Not urgent.** Zero `.jxl` in either real corpus measured so far - the 7 came from a test
    suite. Revisit when a real library contains them.

- **(aax) `time_known` is derived from provenance, not from the value. POST-LAUNCH.** Filed
  2026-08-03 while fixing the stacked date prefix, which this shape is what made possible.
  **Record only - do not build.**
  - **The shape.** `organizer.py:520` sets `time_known=date_source in (EXIF, INFERRED_LOCAL)`.
    That asks *where did this date come from*, and then uses the answer for *does this date
    have a time*. **Precision is a property of the value; trust is a property of the source**,
    and deriving one from the other is the defect - the two questions have different answers.
  - **Where they already disagree.** `TAKEOUT` is in `_TRUSTED_DATE_SOURCES` (`models.py:117`),
    so a Google `photoTakenTime` is trusted enough to file by without review - yet it is
    **not** in the `time_known` pair, so the copy is named date-only. `photoTakenTime` is a
    real capture instant with a time in it. The time is discarded for no stated reason, and
    `dated_filename`'s own justification ("embedded metadata" vs "filename-derived") describes
    a distinction Takeout falls between and no longer matches either side of.
  - **It is what made the stacking bug reachable.** A Takeout or filename-dated file gets the
    short name; the same content organized again once EXIF is readable derives the long stamp,
    and before 2026-08-03 that stacked. The anchored-prefix fix closes the *symptom* on every
    path. This entry is the *cause*, and closing it would have prevented the class.
  - **Why post-launch and not now.** Changing `time_known` changes the **names of organized
    copies** for every Takeout-sourced file, which is a migration question (existing libraries
    keep their names; new ones would differ) rather than a bug fix. It also needs a ruling on
    whether `TAKEOUT_UPLOAD` - an upload time, genuinely not a capture time - should be
    date-only for the opposite reason: its value has a time and its *meaning* does not.
  - **The shape to aim at, not a design:** resolve a date to a value that knows its own
    precision, so naming asks the value and review asks the source. Do not smuggle this into a
    naming change.

- **(aaw) Cross-process drive lock ("P1-lite"): design settled, build POST-SOAK.** Designed
  2026-08-03; filed as its own entry rather than folded into `(vv)` because `(vv)` is a recorded
  *limit* and this is an approved *design*, and `(vv)` now points here. **Do not build before
  soak** - the maintainer's ruling, on the analysis below.
  - **What shrank this from "P1", and it is the load-bearing measurement.** SQLite already
    serialises writers, so **the catalog cannot be corrupted by two truestill processes**.
    Measured directly, 2026-08-03: `journal_mode = delete`, `busy_timeout = 5000` (Python's
    `connect(timeout=5.0)` default, not set by us); a second writer blocks **5.009 s** and then
    raises `sqlite3.OperationalError: database is locked`. A **reader is not blocked at all**
    under a held write lock, which is why only writing surfaces are exposed. The hazard is
    filesystem interleaving and plan staleness, not catalog damage.
  - **The one genuine silent-loss path.** Two concurrent `organize --apply` runs. `_free_relative`
    resolves a destination-name collision by *asking the filesystem*, so both processes can pick
    the same free name and one silently overwrites the other. Every other overlap found is loud:
    migrate compares against its journal snapshot and **raises** (see `(vv)`), undo replays rows
    already applied, reclaim deletes idempotently. **It requires deliberately running two
    applies at once**, which is why this waits for soak rather than jumping the queue.
  - **Where the lock lives.** A lock file **local** to the machine, under `app_paths`' data dir
    (the `session_link` precedent), **not** on the drive: FUSE and network mounts are exactly
    where advisory locking is least reliable, a stale lock on the user's own drive is the thing
    they would delete by hand, and the drive marker is meant to be stable identity rather than
    a high-churn runtime file. Keyed by **`DriveRef.key`'s existing scheme** - `uuid:<marker>`
    for a marked drive, else `path:<resolved>` - so the same drive reached by two mountpoints
    still collides and two different drives never block each other. The in-process design
    already answered the granularity question; this is its on-disk twin.
  - **Kernel-enforced, with no PID liveness check and no TTL.** `fcntl.flock(LOCK_EX | LOCK_NB)`
    on POSIX, `msvcrt.locking(LK_NBLCK)` on Windows. The decisive property is that **the OS
    releases these when the process dies** - SIGKILL, crash, or power loss - so "the user is
    locked out of their own library" is a state this design *cannot reach*, and there is no
    stale lock to detect or clear. A PID check would require us to judge liveness and could be
    wrong in the direction of stranding the user; a TTL solves only the cross-machine case that
    is deliberately out of scope. PID, hostname and operation are written **inside** the locked
    file as advisory content for the refusal message only - the flock is the truth.
  - **The FD-not-path trap, which is the real implementation risk.** Both primitives bind the
    lock to the **file descriptor**, so closing the file releases it silently; the FD must be
    held for the operation's whole lifetime. This is the same ownership-window shape as the
    listening-socket handover, and the established in-tree answer is `contextlib.ExitStack` with
    `pop_all()` at the boundary (`__main__.py:235`). A test must assert the lock still holds
    *after* the acquiring function returns.
  - **RULED: hand-rolled, not `filelock`.** `filelock` 3.32.0 is already in `uv.lock` but only
    via `virtualenv`/`python-discovery`, i.e. dev-side, so adopting it is a genuine new runtime
    dependency. It is cheap (pure Python, zero deps of its own) and it **does not solve FUSE** -
    same OS primitives, and its `SoftFileLock` fallback strands a stale lock on a dead process,
    the exact failure this design refuses. The precedent is **`psutil`, rejected** in "Settled
    technical stances" to keep ~60 lines of hand-written platform code; this is ~25. The
    `platformdirs` precedent points the other way but is **weaker here**, because it was
    justified by *"edge cases we would rediscover as bug reports on machines we do not have"* -
    and we have all three machines on every push. Recorded so it is not re-litigated.
  - **RULED: single-machine scope.** CLI-vs-app, CLI-vs-CLI, and app-vs-app across processes.
    Two machines sharing one cloud mount is **a documented limit, not a defended case** - no
    mechanism is reliable there, and saying so beats pretending.
  - **RULED: no `--force`, for a structural reason rather than a policy preference.** Because
    the lock is kernel-enforced, a refusal **always** means a live holder; a crashed process
    leaves nothing to force past. So `--force` could only ever override a *running* operation,
    which is the one thing it must not do. The escape hatch is naming the holder's PID in the
    message, so a user with a genuinely hung process deals with the process rather than the file.
  - **Where it is acquired: the entry layers, never core.** `truestill-core` is a library, and a
    caller that already holds the lock must still be able to use it. App side is **one** call
    site, `server._start_drive_job`. CLI side is the mutating handlers only - organize/ingest
    under `--apply`, migrate-layout, migrate undo, undo-organize, reclaim, clean-empty - roughly
    seven, all already behind `--apply` or a typed confirm. **Read-only paths take nothing**, and
    there is no shared read lock: a preview run during an apply gives a stale preview, which is
    not data loss, while blocking previews would be a worse product than the race.
  - **Two commits.** (1) the primitive and its tests, used by nothing - independently testable,
    and where all the platform risk lives; (2) the wiring, reviewable as a list of call sites,
    with a parity guard that every mutating handler acquires (the shape
    `test_every_drive_touching_route_starts_through_the_locked_helper` already established).
  - **Six named tests.** (i) **two real processes** contending via `subprocess` - a
    single-process test would be coverage theatre, since `JobManager._lock` already covers
    threads; (ii) a killed holder's lock recovered (SIGKILL on POSIX, `terminate()` on Windows),
    proving the never-stuck property, and skipped on no lane; (iii) a live lock respected;
    (iv) a read-only preview not blocked; (v) the FD retained past the acquiring call, which a
    naive `with open(...)` fails; (vi) the Windows branch **exercised on the Windows lane rather
    than skipped**, with an anti-vacuity assertion that the platform branch actually ran.
  - **Already taken, and deliberately not this:** the `database is locked` refusal shipped
    2026-08-03 as the cheap part of this analysis. It converts the *symptom* into an actionable
    sentence on both surfaces; it is **not** a lock and does not serialise anything.
  - **Known gap left open on purpose.** The app's synchronous settings writes (layout,
    organize mode, sidebar, events settings, `dates/confirm`) are not covered by that refusal:
    they are sub-second writes on HTTP routes, and covering them would mean a new HTTP status
    plus teaching `api()` about it, for a millisecond-wide window. A user sees the raw failure
    text in the error banner and retries the click. Recorded rather than built.

- **(aan) A "verified against code" clause must still resolve.** Recorded 2026-08-01 while
  moving `(aae)` and `(jj)` into the built section. **Record only - needs its own
  measured-scope pass before it is built.**
  - **The failure it prevents.** `(aae)` sat in the wrong section asserting a *"Current state,
    verified against code 2026-07-31"* that named `DEFAULT_CATALOG_PATH`, `catalog_startup.py`,
    `cli.py` and `server.py` line numbers. The symbol had been deleted and the line numbers had
    moved. **A document saying it was code-verified is not evidence**, and a cold start has no
    way to tell which of those citations still means anything.
  - **Why the obvious guard is the wrong one, measured before proposing it.** A check keyed on
    completion vocabulary appearing in the section for open work **misses `(aae)` entirely**,
    because that entry carried none of it - it said *record only*. It also cry-wolfs
    immediately on `(bbb)` and `(r)`, which are legitimately partial, say so, and are licensed
    by this section's own preamble. So the discriminator is not status vocabulary. It is
    whether the entry's factual claims about code still hold.
  - **The check that fits:** every backticked **symbol** inside a verified-against-code clause
    must exist under `packages/*/src`. Symbols, never line numbers -
    `IMPLEMENTATION_STANDARDS.md` already states that symbols are cited over line numbers
    because line numbers drift by design.
  - **The cry-wolf surface, which is why this is recorded and not built.** A backtick in these
    documents holds a Python symbol, a table name (`file_copies`), a column
    (`files.date_source`), a CLI flag (`--apply`), a setting key
    (`layout.everyday_day_threshold`), a typed confirm word (`delete forever`) and a filename.
    Only the first is checkable this way and no regex separates them by shape. Whatever rule is
    chosen needs the measured before/after row this repo asks of every guard - the worked
    example is `test_backlog_references.py`, scoped against the real file rather than a
    plausible phrase list.
  - **A second instance of the same class, in case the guard should generalize.**
    `scripts/benchmark_hashing.py` says `TRUESTILL_CORPUS` is *"named by environment variable
    (`docs/PROJECT_STATUS.md` §6)"*. §6 exists and documents nothing of the kind - the variable
    appears nowhere in that file. A live citation to a real section that does not carry the
    claim, which an anchor-existence check would not catch either.
  - **A third instance, and this one landed in the BINDING CONTRACT.** `956953f` deleted
    `dedup.LINEAR_SCAN_ALARM`; `IMPLEMENTATION_STANDARDS.md` §8 went on naming
    `dedup.LINEAR_SCAN_ALARM = 10_000` as live machinery until it was swept a commit later, and
    `dedup.py`'s own docstring pointed at `BACKLOG.md (v)` after `(v)` had moved to
    `SHIPPED.md`. **Both were found by a manual grep that only happened because someone asked
    "why was it built this way?"** - which is not a process. Two things this instance settles
    about the guard's design: the contract needs to be in scope (it is the document a conflict
    resolves *toward*), and a backticked `Module.SYMBOL` is the highest-value shape to check
    first, since it is unambiguous where a bare word is not.
  - **Related, not the same.** `test_backlog_references.py` already guards the opposite
    direction - a settled item described as pending elsewhere - and deliberately scans only
    settled sections. Noted while here: its `_SETTLED` markers do not match
    `## Shipped (kept for provenance)`, so that section is currently outside its scope.

- **(aas) An undated file cannot be assigned to an event the user knows it belongs to.**
  Recorded 2026-08-02 while ruling on `(aar)`. **Post-launch. A missing convenience rather than a
  defect - nothing here is wrong, something is absent.**
  - **The gap is structural, not an oversight.** `camera_copies_for_events` selects
    `WHERE ... f.captured_at IS NOT NULL`, so Trips & events excludes undated files **by
    construction**: the one screen that could group them cannot see them. No other surface
    assigns a file to an event.
  - **The case that produces it.** A friend sends photos from a shared trip over WhatsApp. A
    normal send strips EXIF, so there is no trustworthy capture date and R1 correctly declines to
    invent one from the sent-date - the file lands in `Undated/`. **The tool is right not to
    guess. The user knows exactly where those photos belong and has no way to say so.** Declining
    to guess is correct; declining to *ask* is the gap.
  - **Scope, now that `(aar)` has shipped.** A document-mode send keeps its EXIF and is dated and
    placed from it, so it never reaches this. What is left is files with genuinely no recoverable
    date - the smaller and harder set.
  - **Shape, unruled:** it is an assignment, so it inherits the event flow's posture - a proposal
    the user confirms, never an inferred date written back as though it were evidence. Whether
    assigning an event also implies a date is the open question.

- **(aau) A zero-warning test lane, and why it is not one today.** Recorded 2026-08-02 after two
  cleanup commits took the suite from **36 `ResourceWarning`s to 1**. **Record only - the lane
  cannot land until the last warning is either owned or proven un-ownable.**
  - **A gate that cannot pass on the day it is added is a broken gate.** One warning survives, and
    a lane that fails on its own first commit teaches everyone to ignore it.
  - **The survivor, described rather than blamed.** An unclosed `sqlite3.Connection` is collected
    during `test_layout.py::test_parse_rejects_empty_and_empty_segments`, reported against stdlib
    `inspect.py`. **That test opens no catalog, and `test_layout.py` constructs no `Catalog`
    anywhere** - the connection was allocated by something else and merely finalised there. That
    is the whole difficulty: a collector-timed warning lands on whichever test happens to be
    running. Without `tracemalloc` the allocation site is unknown, and enabling it across the
    suite costs more than the warning does.
  - **The existing policy stays, for its recorded reason.** `pyproject.toml` exempts
    `ResourceWarning` from `filterwarnings = ["error"]` because it is about *when* the collector
    runs, not about an API: *"turning a real deprecation gate into a flaky one is how gates get
    switched off."* A zero-warning lane sits beside that policy; it never replaces it.
  - **The shape it should take if the survivor proves un-ownable:** assert **no warning
    attributable to our code** - keyed on whether any frame under `packages/` appears - rather
    than a raw count of zero. A count gate fails on someone else's finalizer; an attribution gate
    fails on ours, which is the only one worth waking up for.

- **(aak) The skipped-file summary is written twice.** `organizer._skipped_extension_counts`
  and `service/organize._skipped_summary` are the same logic in two homes - extension counts
  plus the plain exiftool-backup label. **Pre-existing; found while building `(aac)`**, which
  had to thread one new field through both. The companion rule (`ENGINEERING_STANDARD.md` §4)
  says prefer deleting a copy to guarding two, so the fix is one shared helper in core that the
  app calls, not a parity test over the pair. Small, and worth doing the next time either is
  touched rather than as its own errand.

- **(aai) The plain copy path does not verify at write time.** Recorded 2026-07-31, and
  **re-scoped 2026-07-31 after the original reasoning was found to be wrong.** **DEFERRED with
  the cost stated - not an open item awaiting work.**
  - ⚠ **The original entry was wrong, and its "fix" would have been a regression.** It said the
    path records "the hash of what was sent, not what landed", and proposed re-reading the
    destination so the recorded hash described the bytes that actually arrived. That is
    backwards. `verify` compares **the file on disk against the recorded hash**, so:
    - recording the **source** hash (what ships) means a truncated or half-flushed copy
      **fails** verify - the user is correctly told that copy is bad;
    - recording **what landed** would have `verify` compare a file against a hash taken from
      *that same file*. It would **pass**. A corrupted copy would be blessed VERIFIED, forever.

    So the change would have made verify **tautological on the copy path** and destroyed the
    protection it exists to give. It is recorded here rather than quietly replaced because it
    would have looked like an obvious improvement to whoever picked it up - and because it is
    the bake's reasoning applied where it does not belong: a bake needs the landed hash
    *because it deliberately changes the bytes and no source-truth claim survives*; a plain copy
    has a source, and the source is the truth.
  - **THE INVARIANT THIS ENTRY IS REALLY ABOUT, stated positively 2026-08-12 because the entry
    argued the negative and the positive is the stronger case: every path that DESTROYS a source
    re-reads the destination first, and copy mode destroys nothing.**
    - `organizer._move_source` - "delete a source only after its destination copy re-verifies.
      Never deletes on doubt": `destination.checksum(final_relative) == copy_sha`, and any failure
      keeps the source.
    - `reclaim.run_reclaim` - "re-verify fresh, immediately before deleting: never delete on a
      stale check", through `reclaim._verify`, which re-hashes the file on the drive.
    - Plain copy leaves the source where it is. **So the asymmetry is correct rather than merely
      tolerable**, and it is the answer to "why does move verify and copy not": verification is
      the price of destruction, and copy does not destroy. Nothing is at risk during the
      detection window, which is why the latency below costs nothing.
  - **What the real gap is: detection latency, not correctness.** `organizer._upload_copy`
    writes and returns nothing, and `copy_sha` is the source hash. Nothing re-reads the
    destination, so §1's `copy -> record -> re-verify` ordering - which `_move_source` really
    does perform for `--move` - has no equivalent on the plain copy path. A bad write is
    reported as `organized` and is discovered **at the next `verify`, rather than never**. The
    copy is protected either way; what is missing is catching it at the moment it happens.
  - **Why it is deferred rather than open.** Two measured constraints, both of which make this a
    design exercise rather than a fix:
    - **Cost:** a full re-read of every written file. **Measured directly 2026-08-12, replacing
      the proxy below, and it is worse than the proxy said.** On 1.50 GB of the real library: the
      copy itself 0.96 s, the re-read **2.22 s**. So verifying takes the write phase from 0.96 s
      to 3.18 s - **3.3x, not the 30-50% estimated here** - paid always, on every organize.
      (Superseded proxy, kept because it is what the deferral was originally argued on: ~6.3 s
      per 6.2 GB local, ~22 s on a cloud FUSE mount, from the attach work.)
      - **And the re-read is from the DESTINATION, which is usually the slowest device present** -
        a USB drive or a cloud mount, not the NVMe these numbers came off. At the 3.9 MB/s
        measured for cloud-mount content reads, verifying a 6.3 GB organize would add ~27 minutes.
      - **If it is ever built, do not use a second read.** A chunked copy that hashes as it writes
        was measured on the same 1.50 GB at **1.99 s** - 2.1x the bare copy, but **37% cheaper
        than copy-then-verify** and one pass over the destination instead of two. The cost is
        giving up `shutil.copy2`'s in-kernel fast path. Recorded so it is not re-derived.
    - **It cannot be unconditional:** `RcloneDestination` has **no `checksum`** and the base
      raises `DestinationError`. So a post-write verify either skips silently on rclone - a new
      silent hole, which is worse than the one being closed - or needs its own
      UNVERIFIABLE-style outcome plumbed through the organize report. That is design.
  - **If it is ever built**, the recorded hash must **stay the source hash**; the verify step is
    an additional check, never a replacement for what is stored.

- **(aaf) Persisted skip record - "show me what was skipped last week".** Ruled by the
  maintainer, 2026-07-31, from the duplicate-naming gap check. **Record only - do not build.**
  - **What is already done, and what is not.** The *current run* now names every match it
    skipped, on both surfaces (`duplicate_explain`, `organize._duplicate_report`). What is
    missing is asking **afterwards**. `stats.py` states the reason in its own payload today:
    `"exact_duplicates_found": None`, because *"Exact-duplicate skips are not stored in the
    catalog; computing this would require a new scan outside the read-only stats contract."*
    That sentence was written as `(ddd)`'s "intentional omission"; this entry is that omission
    promoted to an item of its own.
  - **Why it is (m)-sized rather than another payload fix.** `Resolution` objects live only for
    the duration of the job and are discarded with it. Nothing persists a skip, so there is no
    row to read later and no amount of payload plumbing produces one - **it needs a new table**,
    plus a retention policy (a 40,000-file re-run would write 40,000 rows nobody asked for) and
    a decision about whether an undone organize retracts its skip records.
  - **Market evidence, recorded because it will not be re-derivable later.** The single
    most-repeated complaint about photo tools, unchanged 2007-2026, is a tool that declares a
    file a duplicate and will not show *which* file it matched. One Lightroom thread has been
    open since **2018** with **21,798 views**, and users call it an *"absolute dealbreaker"*.
    The live half of that complaint is answered; this is the historical half.
  - **Open questions for the design pass:** which table and whether it belongs beside the
    catalog or in it; retention; whether the record survives `undo-organize`; and whether this
    is the same surface as (m)'s inventory of unknown media or a different one.

- **(aag) Near-duplicate grouping and burst review.** Ruled by the maintainer, 2026-07-31, from
  the same gap check. **Record only - do not build.** ⚠ **Overlaps `(m)`**, whose "visual
  side-by-side compare" clause is this item; scope the two together.
  - **This is a review surface over behaviour that is already correct, which is what makes it
    deferrable.** truestill already **keeps** near-duplicates and flags them - `Resolution`
    carries `near_duplicate` and the file is organized anyway, never dropped (`should_upload`
    ignores it), and both surfaces now name what each one resembles and say it was kept. On the
    behaviour the market complains about, truestill is **ahead** of the tools being complained
    about: the complaint is about tools that silently discard.
  - **The distinction that decided the order.** The duplicate-naming payload gap was a **§9
    contract violation** - an outcome counted but not named - and contract violations are not
    deferrable. This is a **feature**: choosing between look-alikes a user can already see
    listed. Same subject, different kind of work, and only one of them was a defect.
  - **Market evidence.** Second most-repeated complaint after the naming one: *"group photos
    that are not quite duplicates, let me pick which to keep"* - burst shots, bracketed
    exposures, near-identical retries.
  - **Open questions for the design pass:** grouping (by perceptual distance, by capture time,
    or both); what "pick which to keep" does given the copy-only invariant, since truestill does
    not delete - it would have to be a *reclaim* offer or a side-bin move, and (§1) constrains
    both; and whether the existing distance threshold is the right grouping key or only the
    right detection key.

- **(aad) Desktop installers - LAUNCH-BLOCKING for the paid product.** Ruled by the maintainer,
  2026-07-31. **Record only - no design pass yet, and it does not block the current
  date-provenance program.**
  - **The problem.** PyPI reaches developers only. `pip install` needs Python present, a
    terminal, and knowing what pip is. The target buyer - someone with a messy photo library -
    has none of the three. **A perpetual licence (`DECISIONS.md` D6) cannot be sold to a user
    who cannot install the product**, which is what makes this blocking rather than merely
    desirable: every other launch item improves a product that person still cannot reach.
  - **Needed:** download-and-double-click installers per platform - Windows `.exe`/`.msi`,
    macOS `.dmg`, Linux AppImage or `.deb` - built by CI on tag and served from `truestill.app`.
  - **PLATFORM SCOPE RULED (2026-08-01): Windows and Linux only, unsigned - `DECISIONS.md` D9.**
    Zero spend; no certificate is bought. macOS keeps its CI lane and its tests but is **not
    published**, because Gatekeeper refuses unsigned apps outright and only the $99/yr Apple
    Developer account changes that - building without publishing is what stops macOS rotting
    unnoticed. **This unblocks the bundler decision**, which can now be made for two platforms
    with no signing step in the pipeline. D9 also carries a launch-page requirement: Windows
    users are told what SmartScreen will show *before* they download.
  - **ACCEPTANCE CRITERION, added 2026-08-04: the frozen artifact must run
    `cleanup.trash_backend()` and report a real backend.** Not a nice-to-have check on the
    bundle - a **safety** one, and the reason is that the consequence of dropping this dependency
    changed on the same day the criterion was written.
    - **What the bundle can silently lose.** `trash_backend` reaches `send2trash` through an
      `import` inside a `try`, which is the shape a bundler's static analysis misses. PyInstaller
      6.21.0 ships **no hook** for it (checked 2026-08-04), and the platform sub-imports inside
      `send2trash/__init__.py` are themselves guarded, so the risk is real rather than theoretical.
    - **Why it is worse than losing the trash.** Before 2026-08-04 a missing backend meant folders
      were **destroyed** instead of trashed. That branch is now closed - an absent backend is a
      refusal (`IMPLEMENTATION_STANDARDS.md` §1) - **but a bundle that drops the dependency
      restores the conditions the closed branch existed for**: on Windows and macOS, with no
      `gio` either, empty-folder cleanup would refuse every folder on every run. Loud rather than
      destructive, which is the improvement, and still a shipped feature that never works on the
      launch platform.
    - ⚠ **The CI guard from commit 1 does NOT cover this, and must not be read as covering it.**
      `test_trash_backend_is_available.py` runs against the *source tree* on the
      {ubuntu, macos, windows} matrix. It says nothing about a frozen artifact, where the
      collection question lives. A green matrix plus a broken bundle is exactly the state that
      would read as verified.
    - **What satisfies it:** the artifact itself printing the resolved backend, the way the
      windowed-launch probe reports console state - not an inspection of the spec file, which is
      a claim about what should be collected rather than what was.
  - **ACCEPTANCE CRITERION, added 2026-08-05: the frozen artifact must serve
    `/static/fonts/DejaVuSansMono.ttf` with a 200 and the byte count of the source file.**
    - **Why it needs saying.** Bundlers collect *imports*; a font is a **data file**, and no
      bundler collects one from a directory unless told (PyInstaller `datas`, or the equivalent).
      The hatchling wheel does carry it - verified, `favicon.ico` is already in there - but the
      wheel is not the installer.
    - ⚠ **Severity is LOWER than the send2trash criterion above, and must not be read as equal.**
      A dropped font falls through to the retained CSS stack, which is exactly the pre-2026-08-05
      behaviour: the type signature varies per OS again. **Cosmetic drift, not a safety
      regression.** It is listed because it is silent, not because it is dangerous.
    - **The CI guard does not cover it.** `test_bundled_font_ships_with_its_licence.py` and
      `test_bundled_mono_font.py` both test the source tree; a green suite plus an installer that
      dropped the file is exactly the state that reads as verified.
    - **The licence rides on the same check.** Bitstream Vera binds the notice to *copies of the
      typefaces*, so an artifact carrying the fonts without `LICENSE-DejaVu.txt` is a licence
      defect, not just a missing file. Assert both paths serve.
  - **PyPI stays**, as the developer / self-hosted channel. It stops being the *primary* one.
  - **MEASURED, THEN DECLINED (2026-08-01). The ~90 MB stays in the build.** Ruled on product
    grounds: at this size the download is unremarkable for a desktop app - **VS Code is ~350 MB
    and Cursor ~600 MB** - the saving buys nothing functionally, and the mechanism that achieves
    it is a permanent maintenance surface plus a landmine for whoever adds a hashing-algorithm
    option later. Recorded with the numbers so it is a decision rather than an oversight.

    | build (PyInstaller 6.21.0, Linux, whole `dist/` tree) | bytes | |
    |---|---|---|
    | with scipy + PyWavelets | 218,212,013 | **208.1 MiB (218 MB)** |
    | with both excluded | 132,045,324 | **125.9 MiB (132 MB)** |
    | difference | 86,166,689 | **82.2 MiB (39.5%)** |

    **THREE CORRECTIONS TO THE RULING'S PREMISES, verified rather than argued - read these
    first if this is ever reopened, because each one points the opposite way from the belief it
    replaces.**

    1. **`--exclude-module` DOES work here.** The ruling assumed it cannot, because `imagehash`
       imports scipy at module level. It does not: `imagehash/__init__.py` imports only `sys`,
       `numpy` and `PIL` at module level (lines 33-36); `scipy.fftpack` is imported *inside*
       `phash` and `phash_simple` (lines 273, 293) and `pywt` *inside* `whash` (line 361). The
       exclusion was run and it worked - `xref-{name}.html` showed **scipy absent from all
       1,213 modules** and pywt as `ExcludedModule`. So the 82.2 MiB is genuinely available
       with two flags and no shim at all. **This is a free-standing option, not a blocked one.**
    2. **PyInstaller #1584 and #3265 do not establish the limitation they were cited for.** Both
       are real and both **closed**; they show `--exclude-module` surprising users, but neither
       documents a module-level-import limitation. Cited accurately here so the next person does
       not treat a closed issue as a standing blocker.
    3. **`dhash_int` does not exist in `imagehash`, and no `imagehash` function silently returns
       a wrong value.** This was carried into the ruling as the decisive danger - that under
       exclusion `dhash_int` falls back to NumPy and returns wrong hashes while `phash` raises.
       Verified against the installed source: `grep dhash_int` over `imagehash` 4.3.2 (which is
       also the newest release) finds **nothing**, and `phash`, `phash_simple` and `whash` each
       do a bare `import` and raise with **no fallback path**. Removing the module cannot
       produce a wrong number, only an exception.

       **Where the belief comes from, because it is not baseless:** `dhash_int` is a real
       function in **Ben Hoyt's separate `dhash` package** on PyPI, which is a different library
       that truestill does not depend on, declare, or install. The asymmetry it describes is not
       a property of anything in this build.

    **What the actual risk is, stated plainly for whoever reopens this:** with scipy excluded,
    `phash`/`phash_simple`/`whash` raise `ModuleNotFoundError` naming an internal package, from
    four frames inside a vendored library - undiagnosable for a photo user, but **loud**. There
    is no silent-wrong-value failure mode to fear. The real cost of reopening is the one the
    ruling identified correctly: a shim is a permanent maintenance surface, and a build where an
    algorithm works in a source checkout and raises when frozen is a trap for whoever adds an
    algorithm option. Nothing in the product calls those three today.

    **The mechanism, if it is ever wanted:** `--exclude-module scipy --exclude-module pywt` for
    the bytes, plus a packaging-layer shim replacing `imagehash.phash`, `phash_simple` and
    `whash` with a refusal naming the algorithm and the alternative rather than the module,
    installed via `--runtime-hook` so a source checkout is untouched. Both halves were built and
    verified working, then removed under this ruling; `git log` for `feat(aad): drop 82 MiB` has
    the implementation if it is wanted back.

    **`dhash` is bit-identical with and without the exclusion** - source, baseline and frozen
    builds all returned `8bcb9521242eca28` for the same fixture. Whatever is decided later, that
    is the bar: the catalog stores hash output as identity.

    **Untested and belonging to the packaging work:** whether the exclusion interacts with the
    `_MEIPASS` layout on Windows, and the Windows byte figure, which will differ.
  - **~90 MB of the install is a code path that never runs** (dependency audit, 2026-08-01).
    `imagehash` declares `scipy` and `PyWavelets` as hard requirements with **no extras split**,
    so every install pulls **81 MB scipy + 8.6 MB PyWavelets**. They back `phash` and `whash`,
    imported lazily inside those functions; truestill defaults to `dhash`, and a `dhash` call in
    a clean process loads neither (verified). Nothing can be done at the dependency layer - the
    only levers are a bundler `--exclude-module` or vendoring, which makes this **(aad)'s
    decision, not core's**. Worth deciding deliberately: 90 MB is a visible fraction of a
    download aimed at people who will judge the product by how heavy it feels. **Unverified
    here:** whether the bundlers' static analysis picks up those function-level imports, and so
    whether an exclude is needed at all - that is a build-time question for the packaging work,
    and per the "stop measuring" ruling it was not measured now. If the exclude is taken,
    `phash` must fail loudly rather than at first use: it is reachable today via
    `perceptual_hash(algorithm="phash")`.
  - **Open questions for the design pass, deliberately not answered here.** Recorded so the
    pass starts from them rather than rediscovering them:
    - Packaging approach: PyInstaller, Briefcase, Nuitka, or something else.
    - The **exiftool binary dependency** and how it ships. It is not a pip package
      (`IMPLEMENTATION_STANDARDS.md` §7 records it as an external binary), and every metadata
      path needs it.
    - **Code signing and notarization** on macOS and Windows. Unsigned installers are blocked
      or scary-warned on both, which is fatal for a product whose whole proposition is trust.
    - Installer size and startup time.
    - How it interacts with the **parked Tauri-vs-local-web decision** (`(o)` and the Product /
      strategy section) and with **D5's licensing/update server**, which is separately unbuilt.
  - **Throwaway measurements, 2026-08-01. Recorded because they rule things OUT; they do not
    choose a bundler, and Linux alone cannot.** Both builds ran on Linux, in scratch venvs
    outside the repo.
    - **PyInstaller 6.21, one-dir.** App starts, serves a page, writes its URL file. exiftool
      resolution **failed at first**: `--add-binary` content lands under `_internal/`, and
      `dirname(sys.executable)` is not `sys._MEIPASS`, so `bundled_bin_dirs()` came back empty
      inside a bundle that had shipped exiftool. Fixed by adding the `_MEIPASS` rule, then
      re-measured in the artifact: resolution now finds it.
    - **Briefcase 0.4.4, `linux system`.** All four assertions pass against the fixed contract.
      But `sys.frozen` and `sys._MEIPASS` are **both absent** - it ships an ordinary
      interpreter - so `is_bundled_install()` reads **False**, and the layout is FHS
      (`usr/bin/<app>` with code under `usr/lib/<app>/{app,app_packages}`), so the
      beside-the-executable rule looks in `usr/bin/bin/` and **misses**.
    - **What that rules out:** the hoped-for "Briefcase needs zero packaging config" advantage
      **does not hold on Linux**. Measured, not assumed.
    - **What stays open, and why Linux cannot close it.** `linux system` is a *distro package*,
      so its FHS layout is required rather than chosen. **Windows Briefcase is one directory
      with the executable on top**, where a `bin/` sibling is natural - and Windows is the
      platform installers actually matter for. **Do not extrapolate the Linux result to a
      recommendation.** A Windows measurement is the missing input.
    - **Friction - and this entry OVERSTATED it; corrected 2026-08-01.** Briefcase's
      `linux system` target took **three failed builds** in the throwaway: a PEP 639 `license`
      declaration (not `license.text`), an actual licence **file** via `license-files`, and a
      **changelog** with a recognised name. **Two of those three were artifacts of the
      throwaway being a bare project.** This repo already has `LICENSE` and `CHANGELOG.md` at
      root, so a real truestill Briefcase project hits **one** of the three, not three. The
      original wording read as evidence against Briefcase and was not.
      **What survives as real friction:** it must run under the **distro's** python3 rather than
      a venv's, because a `linux system` package links against system Python; it downloads a
      **support package and stub** at build time; it is **pre-1.0** (0.4.4); and `sys.frozen` is
      absent, so `is_bundled_install()` needs a replacement signal. PyInstaller needed one
      command and built first try on both platforms.
    - **The `is_bundled_install()` signal for Briefcase, ranked but NOT implemented** - it is
      only needed if Briefcase wins. The criterion is *does it survive the bundle being
      incomplete*, and it does the ranking on its own:
      1. **The running code's own location** (`truestill_core.__file__` under `app_packages/`) -
         the only candidate that **cannot be absent while the code is executing**.
      2. *Path shape* (`app/` + `app_packages/` siblings) - survives a missing binary; if
         `app_packages` were gone nothing could import at all.
      3. *A marker file we ship* - **weakest**: in a bundle broken by missing files, the marker
         can be the missing file. That is the failure this rule exists to prevent.
      4. *`BRIEFCASE_*` environment variables* - **none exist at runtime**; not available.
         `sys.prefix` is `/usr`, indistinguishable from any system-python script.

  - **WINDOWS measurements, 2026-08-01 (run 30692798020, both builds succeeded). The bundler is
    NOT decided, and the reason is the first item below.**
    - **CORRECTED 2026-08-01, same day: the console result was MY MEASUREMENT, not Briefcase.**
      The first reading of this run said the Briefcase app "has a console despite
      `console_app = false`", and scored PyInstaller as winning windowed-ness. **Both claims
      were wrong**, and the mechanism is the valuable part.
      - **Briefcase's configuration applied exactly as written**, on three independent
        confirmations: the build downloaded **`GUI-Stub-3.13-amd64-b11.zip`**
        (`stub_type = "Console" if is_console_app else "GUI"`); the executable was named
        `TruestillProbe.exe`, the **`formal_name`** form Briefcase uses for GUI apps rather than
        the `app_name` form it uses for console ones; and the stub was downloaded and its **PE
        header read directly - `Subsystem = 2 (WINDOWS_GUI)`**. `console_app` also defaults to
        `False`, so it would have been GUI even if the setting had been ignored.
      - **The cause was the launcher. A GUI-subsystem process does not get a console
        ALLOCATED, but it still INHERITS one from a parent that has it** - the subsystem field
        controls allocation, not inheritance. The job launched both artifacts with PowerShell
        `Start-Process`, and the runner's PowerShell owns a console.
      - **It contaminates PyInstaller equally, in the other direction.** Its `--noconsole`
        bootloader frees and nulls the standard streams *in software*, so it reports no console
        **however it is launched**. The two were never compared on equal terms. The run's own
        `AttachConsole` data shows exactly this asymmetry: PyInstaller's control attached
        successfully (**no console attached to that process**) while Briefcase's failed with
        `ERROR_ACCESS_DENIED` (**already attached to one**).
      - **The narrow true statement, as the current state of knowledge:** PyInstaller guarantees
        null streams regardless of how it is launched; Briefcase's GUI stub relies on there
        being no console to inherit. **For a double-clicked shortcut both should be
        console-free - and that is UNMEASURED.**
      - **So "PyInstaller wins windowed-ness" is withdrawn.** It rested on a contaminated
        measurement. The re-run launches both detached, so the comparison is finally fair.
    - **PyInstaller layout - `_internal/` holds on Windows exactly as on Linux.**
      ```
      sys.executable          = D:\a\truestill\truestill\dist\truestill-probe-pyinstaller\truestill-probe-pyinstaller.exe
      dirname(sys.executable) = D:\a\truestill\truestill\dist\truestill-probe-pyinstaller
      sys._MEIPASS            = D:\a\truestill\truestill\dist\truestill-probe-pyinstaller\_internal
      bundled_bin_dirs()      = [D:\a\truestill\truestill\dist\truestill-probe-pyinstaller\_internal\bin]
      exiftool resolved       = D:\a\truestill\truestill\dist\truestill-probe-pyinstaller\_internal\bin\exiftool.EXE
      ```
      ``dirname(sys.executable) != sys._MEIPASS``, so **the `_MEIPASS` rule is the only reason
      exiftool resolves at all**. Stated plainly because it justifies `92774fb` retroactively:
      **without that commit this Windows build fails assertion 2 as well**, not only the Linux
      one it was written for.
    - **Briefcase layout - the beside-the-executable rule FIRES on Windows.**
      ```
      sys.executable          = D:\a\truestill\truestill\packaging\build\truestill_probe\windows\app\src\TruestillProbe.exe
      dirname(sys.executable) = D:\a\truestill\truestill\packaging\build\truestill_probe\windows\app\src
      bundled_bin_dirs()      = [D:\a\truestill\truestill\packaging\build\truestill_probe\windows\app\src\bin]
      exiftool resolved       = D:\a\truestill\truestill\packaging\build\truestill_probe\windows\app\src\bin\exiftool.EXE
      ```
      One directory with the executable on top, so `bin/` beside it is exactly where the
      zero-configuration rule looks. **The advantage that died on Linux's FHS layout is real on
      the platform installers actually matter for** - measured, not assumed.
    - **`sys.frozen` is absent under Briefcase, now confirmed on Windows**
      (``sys.frozen: null``, ``is_bundled_install(): false``). The limit recorded when that
      signal was chosen holds, and **the replacement ranking already stands**: the running
      code's own location is the only candidate that cannot be absent while the code executes -
      here ``...\windows\app\src\app_packages\truestill_core\binaries.py``.
    - **STOP MEASURING. The remaining questions CANNOT decide the bundler** (2026-08-01, after
      two runs that produced no measurements, both lost to rig faults rather than to the
      bundlers). Recorded so nobody restarts the rig looking for an answer it cannot give.
      - **Windowed-ness is already settled by mechanism, not pending measurement.** PyInstaller
        `--noconsole` produces a GUI-subsystem binary; Briefcase's stub **is** GUI-subsystem -
        its PE header was read directly, `Subsystem = 2 (WINDOWS_GUI)`. A GUI-subsystem process
        gets **no console allocated**, and a double-click from Explorer has **no parent console
        to inherit**. So both are console-free when double-clicked. A run would confirm that; it
        cannot decide anything, because **the answer is the same for both**.
        The one real difference slightly favours *Briefcase*: PyInstaller additionally nulls the
        streams in software, so run from a terminal it skips the legacy probe even though the
        user chose that directory, while Briefcase consults it correctly.
      - **`CREATE_NO_WINDOW` is not a bundler question at all** - see the separate note below.
      - **What actually decides it was never measured, and no probe could have measured it:**

        | | PyInstaller | Briefcase |
        |---|---|---|
        | Produces an **installer** | **No** - a binary; then WiX/Inno, dmgbuild, appimagetool | **Yes** - MSI, DMG, deb/AppImage natively |
        | **Signing / notarization** | Wire it per platform yourself | Built in |
        | Build simplicity | One command, first try, both platforms | Project config + support download |
        | Maturity | 6.x, large install base | 0.4.4, pre-1.0 |

        The rig measured **runtime layout**, which `TRUESTILL_BIN_DIR` already solves in one
        line for either bundler. Installers and signing are what `(aad)` exists for.
    - **THE LEAN, recorded as CONDITIONAL rather than decided.**
      - **Briefcase if all three platforms ship**, on the installer-output and signing column,
        with the version pinned and its config expected to break on upgrade.
      - **PyInstaller + Inno Setup if Windows ships first** - more proven and simpler, and the
        three-platform argument that favours Briefcase does not bite yet.
      - **This turns on a product question - which platforms launch first - not an engineering
        one.** Do not resolve it in code.
    - **When packaging resumes, go straight to a real installer.** Not another probe: a
      double-click on a real machine answers the console question more directly than any rig,
      and a real installer answers the table above by existing. Two gates first, and neither is
      engineering: **the signing decision** (an unsigned installer is fatal for a product
      selling trust, per this entry's own reasoning, so building one now yields an artifact that
      cannot ship) and **soak closing** (`PROJECT_STATUS.md` §2 puts installers at #3, behind
      the soak gate).

  - **`CREATE_NO_WINDOW` suppression is NOT a bundler question, and is recorded separately so it
    stops riding along in the wrong rig** (moved out of the comparison 2026-08-01).
    - **It is our flag, not a bundler's.** It lives in `truestill_core.binaries.run` / `.popen`,
      and whether it suppresses a console window is a Windows question with the **same answer
      under either bundler**. It was measured inside the bundler rig purely because the rig was
      the only Windows lane, and that made two runs look like they were about the choice when
      they were not.
    - **The technique used was also wrong, independently of the rig.** `AttachConsole`
      attachability cannot distinguish suppressed from unsuppressed, because
      `CREATE_NO_WINDOW` creates an **invisible console** - the child *is* attached to one -
      while `DETACHED_PROCESS` is the flag that yields no console at all. The right observable
      is the console's **window**: `GetConsoleWindow()` returns `NULL` for a console that has
      none.
    - **Its real weight is cosmetic**: black console windows flashing while exiftool runs in
      batches. Worth fixing, not worth a bundler decision, and cheap to check on any Windows
      machine once one is to hand. Status recorded in `PROJECT_STATUS.md` §3.

  - **Settled 2026-07-31: do NOT run a VirusTotal comparison to choose the bundler.** It was
    proposed, approved, and then withdrawn on the design pass. Recorded here with the reasoning
    so it is not proposed again from the same premise - *"the AV claim is load-bearing and
    testable"*. It is load-bearing. It is not testable in a way that would decide anything.
    - **The deciding argument: signing dominates, and it is the same decision either way.** The
      gate a user meets is SmartScreen, which is reputation-based per file hash and per
      certificate. Unsigned, **both** candidates get warned on; signed, **both** accrue
      reputation on the certificate. So the AV question is **orthogonal to the choice it was
      meant to inform**.
    - The artifacts are not comparable anyway. PyInstaller ships a self-extracting bootloader -
      the packing behaviour heuristics target - while a Briefcase MSI is a native installer that
      packs nothing. The result would confirm from measurement what the mechanism already
      predicts, while reading as "Briefcase is safer".
    - The number would not even be stable. Detection counts track the **bootloader build's**
      reputation, not the approach (`pyinstaller#8164`: counts change with the PyInstaller
      version), and VirusTotal's raw count is unweighted, with a handful of engines producing
      most false positives. A single artifact per tool cannot separate signal from that noise.
    - **What a scan is still good for**, and where it belongs: a **release smoke test** on the
      signed artifact we actually ship, to catch a regression. Not a selection input, and not
      before there is something signed to scan.
  - **Not designed here on purpose.** The questions above are genuinely open and several are
    coupled (the shell decision changes the packaging answer, which changes the signing answer);
    picking one now would be guessing in public.

- **(aac) Organize must name and count unreadable source files the way verify does.** Ruled by
  the maintainer, 2026-07-30, from the Pass 1 F2/F1 asymmetry left after the code-quality audit.
  **Scan tier and residue 1 built 2026-08-02; residues 2 and 3 keep this entry open.**
  - **What shipped.** F1 gave `verify` `CopyStatus.UNREADABLE`, a count, and filenames on CLI
    and app. F2 kept `compute_hashes` alive on an unreadable source (empty hashes +
    `BrokenExecutor` guard) so an organize preview/run no longer aborts the whole pass.
  - **RE-SCOPED 2026-08-01, and the finding is sharper than "unreported": the fact is
    DESTROYED, not merely unsurfaced.** Traced end to end. `scan._hash_one` catches `OSError`
    per file and returns `(path, None, None)`, so an unreadable file becomes
    `FileHashes(None, None)`. That is **the same value** the size pre-filter produces for a file
    it legitimately chose not to hash - `DedupIndex.check`'s own docstring says so: *"`sha256` is
    `None` for a unique-size file the pre-filter chose not to hash"*. The two states are
    indistinguishable downstream by construction, so no consumer can count them apart even if
    one wanted to. Nothing in core or the app reads an absent sha for reporting; grep finds no
    such consumer.
  - **Which surface is still silent, precisely.** The **run** path catches it late and by
    accident: the copy raises and the file is reported `ActionStatus.FAILED`. The **preview**
    path attempts no copy, so there is no status to report and nothing is said at all - the
    user is told the file is fine. A locked or `EIO` file in the source tree is therefore
    invisible in exactly the pass whose job is to say what will happen
    (`IMPLEMENTATION_STANDARDS.md` §9).
  - **Requirement.** Organize preview and run summaries must count and name unreadable sources
    the way verify reports unreadable copies - which first needs the scan to stop conflating
    "could not read" with "did not need to". Do not treat empty hashes as a finished answer.
  - **The docstring that read as though this were already closed: fixed 2026-08-02.**
    `SourceScan`'s docstring said an unreadable file *"surfaces as `ActionStatus.FAILED` when the
    copy raises"* full stop, with no **run only** qualifier, so the comment standing next to this
    code announced a resolution the code had not reached. It now names the run path it is true
    of and cites this entry.
  - **THE SCAN TIER IS BUILT (2026-08-02). THE ENTRY IS NOT CLOSED.** `UnreadableReason`
    (permission / I/O error / missing / other) rides on `FileHashes`, so *"could not read"* and
    *"correctly did not hash"* are no longer one value. `scan._probe_readability` opens every
    path and reads one byte **before the hash-cache split** - `stat` succeeds on an unreadable
    file, so a stale-cache hit would otherwise skip the worker entirely - and `_hash_one` keeps
    its own handler for the late failure a 1-byte probe cannot see. The CLI names the files on
    preview and run with the FAILED set subtracted; the app payload carries `{total, shown}`;
    `app.js` renders it **and the `unreadable_folders` key that had been reaching the browser
    unrendered since it shipped**. A preview that found one now exits `1`. Contract row in
    `IMPLEMENTATION_STANDARDS.md` §9; cost in `PERFORMANCE.md` §3.2.
  - **RESIDUE 1 - BUILT 2026-08-02. Ruled: disjoint buckets, enforced by a conservation law.**
    The shipped build reported *"organized (unique): 5"* and *"files that could not be read: 2"*
    for the same seven files, with both unreadable photos inside the 5. `partition_for_report`
    now splits every scan into four buckets that are disjoint **and** exhaustive, and
    `new_unique + near_dup + exact_dup + unreadable == files` is asserted on both the printed
    summary and the app payload - so a category added later that forgets to be disjoint fails a
    test instead of double-counting the way this one did. Unreadable is tested **first**, because
    a cache hit gives an unreadable file real hashes and it can therefore match the exact or
    perceptual tier; filing it as a routine skip would bury the fact that truestill could not
    read it (the *skipped error* vs *skipped success* distinction AWS DataSync draws).
    **The plan was not touched, and that was the finding rather than a compromise.** `execute`
    never consults `should_upload` - it branches on `exact_duplicate` directly - so the report
    was separable from the plan. It also *should* be: on a run the unreadable file is still
    attempted, the copy raises, and that is what produces the `ActionStatus.FAILED` the user
    sees. `preflight_for_run` must keep sizing the destination for it. Excluding it from the plan
    would have deleted the run's only report of the file. Fixing the tally alone is what makes
    preview and run agree: *"4 organized, 1 unreadable"* predicts *"4 organized, 1 failed"*.
    Applied to all five report sites, `ingest` included - it shares `_run_pipeline` and so
    already printed the unreadable block beside the same contradiction.
  - **RESIDUE 2 - the app's *run* completion has no `unreadable_files`.** Preview only, matching
    the design that was accepted. The CLI reports on both. An unreadable file that was never
    copied - a cached exact duplicate - therefore has no app-side surface on a run, though the
    CLI names it.
  - **RESIDUE 3, and what changed about it: the perceptual tier's overloaded `None`.** Recorded
    2026-08-02 while verifying a proposed HEIC feature that turned out not to exist.
    `perceptual_hash` returns `None` and discards the reason, so one sentinel carried four
    meanings: a video (correct - none exists for it), not an image at all, above the 300 MP
    ceiling, or **could not be decoded**. `DedupIndex.check` skips the tier on `None` and
    `register` omits the file, both silently.
    **The scan fix evacuated the unreadable meaning from those four**: a file that cannot be
    opened is now named by the probe, so its perceptual `None` is no longer the only trace of it.
    What remains is narrower and is the honest statement of this residue: **a file that is
    readable but undecodable** - a truncated JPEG, a corrupt HEIC - still returns `None` and is
    still indistinguishable from a video that never had a hash. That is a *corruption* report,
    with a different remedy from a permission one, which is why it is deliberately not folded
    into the scan fix: `test_a_corrupt_but_readable_image_is_not_called_unreadable` exists to
    keep the two apart. Nothing counts or names a per-file perceptual failure; the whole-library
    case is loud (`heic_perceptual_skipped`, and the CLI's note when `HEIF_AVAILABLE` is false),
    which is exactly what makes the per-file case easy to believe is covered.

- **(vv) Known limit: app per-drive job lock is process-local; CLI↔app overlap is not serialized.**
  Recorded 2026-07-29 when Commit 3 of (oo) shipped the server-side one-op-per-drive guard.
  - **What is covered.** Concurrent jobs inside one `truestill-app` process (reload, second tab,
    double-click) are refused with `DriveBusy`.
  - **What is not.** The lock lives in `JobManager` memory. A `truestill` CLI invoke in another
    process does not see it, and a restarted app starts empty (no stale lock - deliberate).
    Catalog/journal crash-safety still applies; this is not a claim that two writers cannot
    touch the same drive across processes.
  - **Do not assume solved** when designing reclaim, migrate, or backup concurrency. A real
    cross-process guard (e.g. flock on the drive marker or catalog) is a separate design if
    soak ever shows CLI↔app races mattering in practice.
  - **Date-provenance step 4 narrows this, and does not close it (2026-07-31).** The bake
    refuses to write while a migration is journalled and unfinished on the same drive, reading
    `Catalog.pending_migration` - the journal lives in the shared catalog, so unlike this lock
    it **is** visible across processes. It re-checks before **every file**, so the exposure is
    the gap around a single write rather than the length of a run. **That is a check, not a
    mutex, and the residual race belongs to this item:** closing it needs the cross-process
    on-disk lock described above, deliberately not smuggled into step 4.
  - **CORRECTION 2026-08-03: "app-vs-app is already complete" was wrong, and this entry said
    it.** The 2026-07-31 note above claimed that coverage was complete because every job route
    goes through `server._start_drive_job` keyed on `uuid:<marker uuid>` (pinned by
    `test_every_drive_touching_route_starts_through_the_locked_helper`), leaving only CLI-vs-app
    and CLI-vs-CLI. **That is true within one process and false across two**, which is exactly
    the distinction this whole entry is about - so the claim contradicted its own headline.
    - **The mechanism, read in the code rather than assumed.** `bind_listening_socket` tries
      `for candidate in (preferred, 0)` (`__main__.py:167`): if the preferred port is taken it
      binds an **ephemeral** one instead of refusing. A second `truestill-app` therefore starts
      **successfully**, on another port, with its own `JobManager` and its own empty
      `_occupied` map. Neither instance can see the other's locks. **Double-clicking the icon
      twice is enough** - no unusual invocation is needed.
    - **The session link makes it worse, not merely equal.** `session_link.write` is *replaced,
      never appended*, so the second instance overwrites the first's URL file; and the file is
      *removed when the process exits*, so quitting the second instance **deletes the link to
      the first, which is still running**. The ephemeral port is by then the only way in, and
      nothing records it.
    - **What was actually right in the old note:** the in-process guard and its test. They
      cover what they claim. The error was reading "every route goes through one locked helper"
      as "there is only one `JobManager`".
    - **It had been copied twice more**, which is why the grep matters and not the care:
      `service/bake.py` said the lock covers app-vs-app *"completely"* and
      `test_bake_refuses_during_migration.py` said it *"fully"* and *"already solved"*. All
      three corrected in one commit. `code-quality-audit.md` repeats it too and is left alone -
      it is a dated record of what was believed then, not a live claim.
    - So the exposure is **CLI-vs-app, CLI-vs-CLI, and app-vs-app across processes**. The
      design that closes all three is `(aaw)`.
  - **What the residual actually costs, stated so nobody over-corrects for it.** If the check
    does interleave, migrate compares the relocated file against its journal snapshot, finds the
    baked bytes, and **raises** - a loud, recoverable stall. `destination.relocate` copies rather
    than renames, so the file is preserved at its old path with an orphan at the new one and the
    journal row still pending; nothing is lost. That outcome is *why* `(aah)` was closed rather
    than built: weakening the comparison to avoid this stall would cost a real check, and the
    right fix if soak ever shows it biting is the on-disk lock above.
  - **Not fixed here, on purpose** - recorded only, per instruction.

- **(ss) Organize preview hashes every file before showing anything - slow on a network mount.**
  Ruled by the maintainer from a soak finding, 2026-07-29: measured **9.9 files/sec on a 2,064-file
  folder over a cloud FUSE mount, ~8 minutes to see a preview at all** - against an industry
  baseline of tens of thousands of files/sec for SHA-256 (the bottleneck is I/O, not the
  algorithm), which points at the network mount, not the hash.
  - **Checked in code before recording: both proposed fixes are already built.** The size-group
    pre-filter is not a gap - `scan.py`'s `_needs_sha` already hashes only files whose byte size
    collides within the scan or is already known to the catalog (`compute_hashes`'s whole
    stated purpose, "concurrent hashing pass with a byte-size pre-filter"). The hash cache is
    already wired into preview too - `service.organize_preview` opens `HashCache.beside(db)`
    and passes it through to `resolve(...)`, the same cache backlog **(r)** shipped. So the
    slowness is not explained by either mechanism's absence; **do not build them again** -
    whoever picks this up should confirm they are live on the affected path first.
  - **Cold-preview phase profile measured 2026-07-29** - see
    [`docs/preview-performance-profile.md`](preview-performance-profile.md). Numbers came from
    **`Vault/Photos/Archive/.../Wayanad '14`** (2,064 files) - that tree is now
    **OFF LIMITS** (`PROJECT_STATUS.md` §4); keep the figures as historical only. On that
    run, **exiftool is 74% of cloud-mount wall** (231 s); hashing wall is 26% and is almost
    entirely unconditional `perceptual_hash` (SHA-256 already ~1% of files via `_needs_sha`).
    FUSE vs local gap is 13×, ~75% of it exiftool. Stat/walk are noise. Local twin was
    `TruestillLibrary/Input/2014/Wayanad '14`.
  - **Requirement for any fix:** measured **before/after on an allowed real cloud / FUSE
    corpus** (relocated Memory Cabinet, Output, or `<cloud mount>/2015`) - not a
    synthetic fixture, and **not** anything under `Vault/` (`PROJECT_STATUS.md` §4).
- **(xx) Absolute-path columns and hash-cache keys are not machine-portable.** Ruled by
  the maintainer from the 2026-07-30 move audit. **Record only - do not fix in the loud-failure
  series.** Commits 1-3 (**(ww)** path hints, catalog startup announcement, reclaim/undo
  staleness) made a machine move **survivable by failing loudly**; the remaining work is
  **portability**, not safety. User procedure:
  [`docs/moving-machines.md`](moving-machines.md).
  - **`files.source_path`** - absolute. Used by reclaim and by display labels (`where`,
    near-dup "matched" paths). After a move the recorded sources are gone; reclaim reports
    the missing count rather than a silent empty plan. A future rewrite (relative-to-drive,
    or clear-on-reclaim-only) is product design, not a hotfix.
  - **`inplace_runs.source_root` / `dest_root`** - absolute. Undo refuses unreachable stored
    roots and points at `--source-root` / `--dest-root`. Making the journal remount-native
    (uuid + relatives only) is later work; the overrides already exist.
  - **`reclaim_journal.source_path`** - absolute. Crash/audit resume only; stale after a
    move. Low urgency once reclaim no longer pretends mid-flight old paths are live.
  - **Hash-cache non-portability** (`catalog.cache.sqlite`, keyed by absolute path + size +
    `mtime_ns`, plus a tag-set fingerprint for metadata). Machine-local and disposable by
    design (`IMPLEMENTATION_STANDARDS.md` §8). Copying the sidecar to a new machine does
    **not** preserve the ~170× warm metadata win; first preview is cold.

    | | Absolute keys (today) | Drive-relative (`uuid` + relative) |
    |---|---|---|
    | Survives remount with preserved mtimes | No | Yes for **organized drive copies** |
    | Helps arbitrary unmarked `--source` trees | Yes (path-scoped) | No |
    | Cross-machine copy that resets mtime | Miss anyway | Miss anyway |
    | Wrong-file collision risk | Lower | Higher if relative reused / wrong root |
    | Matches custody model | Intentionally **not** in the catalog | Closer to custody, couples cache to "is this a drive?" |

    Prefer leaving the cache disposable over a half-portable key until a concrete trigger
    (measured remount pain that loud failures do not cover) appears.
  - **Not fixed here, on purpose** - recorded only, per instruction.

- **(aap) Registering a folder must not mint a second identity for a library already known.**
  **BUILT 2026-08-02**, split out of `(yy)` after the design pass observed it. Shipped first
  because it prevents a loss where `(yy)` only repairs an inconvenience.
  - **Observed, not reasoned.** With a drive unmounted, `verify` printed *"isn't a truestill
    drive yet - register it with `truestill drives --init`"*, and following that advice on a
    library whose marker was lost minted a fresh uuid with no warning. `moving-machines.md`
    already named this the worst failure mode of a move; the CLI was steering people into it.
  - **The two surfaces failed in opposite directions, and the app's was worse.** The CLI showed
    the new drive with **0 files** - visibly wrong. The app registers as a side effect of
    backup, and `attach_drive` matches by content, so the phantom drive got *all* the files and
    `truestill status` then said *"All catalogued content has at least two drive copies. Nicely
    redundant."* about photos existing in exactly one place. A custody tool overstating
    redundancy is the worse failure, so the guard sits at the point of minting rather than on
    the screen that reads the count.
  - **Detection is two-stage and bounded**: stride-sampled `stat` of up to 40 recorded
    `file_copies.relative` paths per known drive, then - only if half are present - 3 full
    SHA-256 reads that must **all** agree. Measured 0.12 ms median on a small library; the cost
    is per known drive and never walks the tree, which is what keeps it usable on a slow mount.
  - **It never adopts.** The evidence for *"this drive moved"* and *"this is a clone"* is the
    same evidence, and a product that counts how many places a photo is safe in must not
    resolve that by guessing. The CLI refuses and names both ways forward
    (`--adopt-existing` / `--force-new-identity`); the app refuses and points at the CLI.
  - **Still open, deliberately:** the app has no register screen - registration happens inside
    backup - so its half is a refusal, not an offer. Giving the app its own adopt flow needs a
    surface that does not exist yet, and is not blocking `(yy)`.

- **(yy) Reconnect a moved location (Lightroom-style Find Missing Folder).** Ruled by
  the maintainer 2026-07-30 after research into how Lightroom Classic repairs a moved library -
  the closest mature analogue. **BUILT 2026-08-02** as `truestill repoint-sources OLD NEW`:
  preview, content proof, typed `repoint`. Cross-reference **(xx)** (`files.source_path`
  absolute), which stays open for the two journals below.
  - **The proof is the feature, not the rewrite.** `reclaim` deletes `files.source_path`, and
    its gate re-hashes the **destination copy on the drive** - `plan_reclaim` only checks that
    the source *exists*, and never hashes it. So a path repointed at the wrong tree would have
    reclaim delete a file it never verified at all, on the strength of a different file being
    intact. The repoint therefore refuses unless `drive_adoption.inspect_root` proves the new
    root holds the recorded content: stat-sample, then 3 full reads that must all agree. Reused
    rather than reimplemented - it is the same question `(aap)` asks, with the same measured
    thresholds. **This is a stronger claim than "reclaim re-verifies", which is what the
    original scoping assumed; that re-verification is of the copy, not the source.**
  - **Out of scope, decided rather than forgotten.** `reclaim_journal.source_path` is crash
    resume: a row exists only between the record and the clear, and one that survives describes
    a deletion already in flight. Rewriting it could point a stale journal row at a *live* file
    in the new tree, which is worse than leaving it stale. `inplace_runs.source_root` /
    `dest_root` are undo state with `--source-root` / `--dest-root` overrides that already
    work; rewriting undo records is its own decision on a reversal path. Neither belongs in a
    change about source provenance.
  - **Why Lightroom's version works at scale.** Reconnecting the *top-level* missing
    folder cascades to every subfolder in one action. That cascade is load-bearing: without
    it, a moved library is a per-folder slog; with it, the fix is roughly two minutes.
  - **Scope for truestill - narrow on purpose.** Needed **only** for `files.source_path`
    (and the reclaim / search / near-dup labels that read it). After a move those absolute
    sources are dead: reclaim reports missing rows instead of offering deletes, and Find /
    near-dup display cites old paths. **Drive-relative copies need no repair at all** -
    custody is uuid + `file_copies.relative` under the marker; do not invent a reconnect
    flow for organized drive trees or anyone will over-build what already survives a remount
    (see [`moving-machines.md`](moving-machines.md)).
  - **Design when built.** Point once at the new root; rewrite the stored absolute prefix
    for every affected `files.source_path` row; preview-then-typed-confirm like every other
    bulk change in this product; never silent. Cascade from the chosen root the way
    Lightroom cascades from the top folder - one action, all descendants.
  - **Not fixed here, on purpose** - recorded only, per instruction.

- **(bbb) exiftool `_original` backups.** Ruled by the maintainer, 2026-07-30. When anyone edits a
  photo's date with exiftool, the default is to leave `file.jpg_original` beside it holding the
  **original** metadata (only `-overwrite_original` skips this).
  - **Safety - Built 2026-07-30.** Measured first: on the default path, `*.jpg_original` was
    already skipped as unrecognized (suffix `.jpg_original`, not `.jpg`). The residual bug was
    `--all-files`, which organized both the live file and the sidecar as near-copies (same
    pixels, different SHA/dates). Fix: `is_exiftool_original_backup` refuses
    `{live_filename}_original` at `scan_source` / `discover` for every caller, including
    `--all-files`. Skipped report uses the plain label **exiftool backup**, not a bare
    `.jpg_original` extension count. Matcher covers any extension (exiftool appends `_original`
    to the full filename). Collision pinned: a legitimate `vacation_original.jpg` ( `_original`
    before the extension) is **not** a backup and is still organized.
  - **Recovery - BUILT 2026-07-31 (step 6), with item 4 PARTIAL.** The offer ships in the rescue
    flow: `date_rescue.original_candidates` finds a ``{name}_original`` beside the recorded
    source, reads its date with the same resolver everything else uses, and offers it **only
    when it parses and differs**. Accepting pre-fills the rescue field; the commit is the same
    typed `confirm_file_date`, so a sidecar date is not a second route into `HUMAN_CONFIRMED`.
    Items 1, 2, 3 and 5 are satisfied as written.

    **Item 4 is one half built and one half DECIDED AGAINST - `(aaj)`, now in *Consciously out
    of scope*.** Verified against code, not assumed:
    - *"the human wins"* - **satisfied, structurally.** `confirm_date` writes
      `captured_at` + `date_source = HUMAN_CONFIRMED`; `migrate` renders from
      `files.captured_at` and `rederive_rules` re-reads metadata for **ambiguous labels only**,
      never dates; `record_uploaded` re-applies a confirmation on re-ingest. All five whole-disk
      operations are pinned by O4 in `test_confirmation_survives.py`.
    - *"note the embedded conflict (never silent)"* - **not built, and not going to be.** The
      only disagreement surfaced anywhere is the **sidecar's**, and only as an offer. Nothing
      compares the live file's embedded EXIF against a confirmation, and `confirm_date` sets
      ``date_tag = NULL`` - so the machine's prior evidence is *discarded*, and the catalog can
      no longer say what the file claimed without re-reading it.

    **Which comparison ships, because the design flagged this as a trap:** against **recorded
    provenance** (`files.captured_at`), never the file's current embedded metadata. After a bake
    the organized copy agrees with the confirmation while the *source* still does not, so
    comparing live metadata would make every rescued file report a conflict with itself forever.
    That trap is avoided - but honestly, it is avoided because the live comparison was never
    built, not because it was built carefully. It was then **decided against** on 2026-07-31,
    once the design showed the only constraint-satisfying route needs a column storing a value
    the system has already ruled wrong; see `(aaj)`. **The trap is recorded there, not open
    here** - and it applies again only if `(aal)` is ever built.

  - **Recovery - original design, kept for provenance** (see **Converged programs**):
    not a parallel `_original` tool. Full design (do not invent a separate surface):
    1. **No silent substitution.** Reading `_original` never auto-wins over the live file's
       embedded date in `resolve_capture_datetime`.
    2. **Same provenance as (ii):** if the user accepts the sibling date, record
       **`human-confirmed`** (highest tier), durable via the date-source column **(n)** and
       **(ii)** share. Machine suggestion only; human commits.
    3. **Same rescue seam:** when the live file has a date *and* a sibling
       `path.name + "_original"` exists with a different parseable capture date, offer a rescue
       candidate on the (ii)/(n) surface ("why this date?" → action). Wording like: "exiftool
       backup beside this file still has 2014-08-17 - use that date?" Confirm → place by
       confirmed date + provenance.
    4. **Disagree visibly:** if live EXIF and `_original` disagree after a human confirm, keep
       human-confirmed; optionally note the embedded conflict (never silent).
    5. **Dedup / identity:** rescue edits the catalog row for the **live** file; `_original`
       stays an unorganized sidecar (never ingested as a second library copy).
    - **Out of scope for recovery:** inventing merges, rewriting live EXIF from `_original`
      without confirm, treating `_original` as a second library citizen.
    - **Sequencing:** recovery UI waits on the (ii)/(n) provenance column - same screen. Safety
      shipped independently so this item is not "untouched".

- **(nn) Prove destination timestamp parity against a live rclone remote.** The destination
  timestamp seam is implemented for rclone as `touch --no-create --timestamp`. The installed
  rclone help was checked and a unit test pins the exact invocation, but **no real remote has
  exercised it**. That is command-shape evidence, not backend parity. Before claiming parity,
  run a dated normal copy against a disposable configured remote and verify its reported
  modification time equals the capture timestamp, the local source timestamps stay unchanged,
  and the failure path cannot create a zero-byte remote object.

- **(r) Analyze mode - the hash cache half is SHIPPED.** The placement clause fired: a soak run
  previewed an unchanged 2,275-file source twice and re-hashed it both times, so the cache was
  built first. Per the clarified binding, cache-first alone is fine - what the binding forbids
  is shipping Analyze *without* it, and Analyze will now arrive with it already underneath.
  - **Shipped:** `hash_cache.HashCache`, a sidecar `catalog.cache.sqlite`. Measured on
    12 MP-class photos, a repeat preview at 2,275 files went **15.8s -> 4.7s (3.3x)**; the
    remaining 4.7s is exiftool. Invariants in `IMPLEMENTATION_STANDARDS.md` §8.
  - **The measurement that changed the recorded spec:** it said "path+size+mtime -> sha256".
    That alone would have recovered ~5% of the wait - the size pre-filter already spares
    SHA-256 for ~94% of realistic-size files, while the *perceptual* hash runs for every image
    at ~69.8 ms against SHA-256's ~8.5 ms. Caching both is the feature.
  - **Next, on this evidence:** exiftool is now essentially the whole cost of a repeat preview.
    A metadata cache is the natural follow-on and is deliberately a **separate item** - metadata
    feeds *dating*, so a stale row could change where a photo lands, a class of risk the hash
    cache structurally cannot have.
  - **Still to build:** Analyze mode itself, minus tier 0 (below).
  - **Tier 0 SHIPPED on the CLI, 2026-08-03** - `truestill analyze <folder>`. The census only:
    file count, total bytes, photo/video/audio split, per-extension formats, the skipped and
    unrecognized census, and folders that could not be listed. **Measured 0.31 s wall for
    2,269 files / 6.65 GB** on a local disk, which is what makes it the tier that earns trust:
    it answers before a user wonders whether anything is happening.
    - **It jumped the post-launch placement deliberately**, and only this tier. It is a
      reporting layer over `inventory_source`, which `(tt)` had already shipped app-only; the
      asymmetry - a fact the app could state and the CLI could not - was most of what tier 0
      cost. Nothing in the expensive path moved.
    - **Requires a folder and nothing else**: no destination, no catalog, no registered drive,
      and it deliberately does **not** accept `--db`. Pinned by
      `test_no_destination_no_catalog_and_no_registered_drive_are_needed`, because a later
      refactor that added a destination parameter would kill the funnel silently.
    - **The one engine change:** `SourceInventory` now carries `unreadable_dirs`.
      `scan_source` already found them and `inventory_source` discarded them, which made "no
      files found" and "that folder could not be opened" the same answer - `(aac)`'s defect on
      a new surface. Plumbing, not a new fact: no extra walk, no extra `stat`.
    - **Known gap, recorded not built:** the app's `/api/organize/inventory` payload still
      omits `unreadable_folders`, while the preview's empty branch carries it. That asymmetry
      predates this commit and belongs with the app work.
    - **Polished 2026-08-03 from the first real-library run** (32,628 files / 192.49 GB on a
      cloud FUSE mount), which surfaced two things 2,269 test files could not:
      - **The unrecognized extension list was unbounded** - 279 files carried 200+ distinct
        one-off extensions (apparently truncated transfers) and printing them all buried the
        report. Now capped by **two** bounds, count and rendered width, with the total left
        exact. A count alone does not bound a line: those artefacts are ~25 characters each,
        so a twelve-entry cap still produced a ~300-character line. The elision names how many
        of the hidden extensions were **seen once**, which is arithmetic; it does not say they
        are truncated transfers, which would be a diagnosis the census cannot support.
      - **Elapsed wall time is now reported**, with a files-per-second figure **withheld below
        one second** - under that it describes interpreter startup and the page cache rather
        than the source. This is expectation-setting, not a benchmark: tier 0's wall time is a
        direct signal of how the source behaves, so a slow one tells a user the expensive
        tiers will be long before they commit to them. `PERFORMANCE.md` still owns benchmarks.
    - **Commit 2 shipped 2026-08-03: the facts that existed but were unreachable.**
      `bytes_saved`, `bytes_near_dup`, `oldest` and `newest` were computed inside the app's
      `_completion` and were therefore available only *after* an organize - the wrong way round
      for a preview. They now live in `truestill_core.insights`, which the CLI preview, the app
      run and (later) Analyze all call. **Sizes are injected rather than measured**: a finished
      run sizes the file where it landed, a preview can only size the source, and baking either
      choice into core would make one of the two lie.
      - **Near-duplicate bytes are not savings, and the type refuses to imply otherwise.**
        Truestill *keeps* a near-duplicate, so no operation returns those bytes;
        `reclaimable_bytes` is exact-duplicates only. Pinned on the **wording** as well as the
        numbers - a rewording to "freed" would be a promise the product does not keep, and no
        numeric assertion would catch it.
      - **The move is proven, not assumed.** `test_insights_match_the_run_summary.py` is a
        characterization test that was green **before** the refactor and stays green after. It
        matters because the two sides select differently: `_completion` filters on
        `ActionStatus`, the core producers partition on the resolution's duplicate fields.
      - **New:** a per-year capture histogram (undated counted, never dropped, so the column
        reconciles with the file count) and a capped largest-files list. **Counts, not bars** -
        a real library spans three orders of magnitude between its quietest and busiest year,
        so a linear bar saturates and a log bar makes a proportion claim that is not true.
      - **Still tier 1-2 facts.** They appear in the organize *preview*, which does the
        expensive pass. `truestill analyze` remains tier 0 and still says *not yet analysed*.
    - **Commit 3b shipped 2026-08-04: each tier reaches the screen as it completes.**
      `(r)`'s own escape clause - *"earlier if the soak shows repeat-run pain at real scale"* -
      was satisfied by evidence rather than argument: `truestill analyze` on the 192 GB library
      took **54 minutes at 3% CPU**, about 105 s of computation stretched over 54 minutes of
      waiting on the mount (~31x I/O to CPU). Tier 0 finished in 21 s and **the remaining 53
      minutes produced nothing at all**.
      - **The sequencing was already right, which is the finding that shaped the commit.**
        `test_the_census_prints_before_the_expensive_work_starts` has pinned since 3a that the
        census prints first. It was invisible anyway, for two reasons that are not ordering:
        **nothing reported progress** during the slow tiers (`_analyze_deep` passed no
        `progress=` to either `read_metadata` or `resolve`), and **stdout is block-buffered when
        it is not a terminal** - demonstrated before the fix: a redirect file stays *empty* for
        the whole of the slow tier. So the work was progress, a stream split and a flush; no
        write was re-ordered.
      - **Results to stdout, progress to stderr** (`IMPLEMENTATION_STANDARDS.md` §9), so
        `truestill analyze <path> > report.txt` leaves a clean report while the terminal shows
        the run. **Nothing that reads the output moved**: every result line stayed on stdout,
        which is where all 42 existing analyze assertions read it, and no test anywhere asserted
        progress text. Verified: no script or package shells out to this CLI.
      - **The `\r` flooding is fixed as a side effect**, which is why it belonged here rather
        than in the ergonomics pass: the same branch decides it. A non-terminal gets no carriage
        return, no 60-column padding, and a line only every `_PROGRESS_INTERVAL_SECONDS` -
        without `\r` to overwrite with, one line per file is the same flood in a new shape. The
        real run left **127 KB** of it; the equivalent piped run now leaves a handful of lines.
      - **The throttle got its own clock.** Borrowing `_CLOCK` - the report's elapsed-time
        source - broke five unrelated timing tests, whose fixtures yield an exact number of
        readings. Two measurements with nothing to say to each other should not share one
        injection point.
      - **Three of the tests were weak and mutations proved it**, each fixed rather than
        accepted: one "some progress appeared" check that tier 2a alone satisfied (so tier 1
        could go silent unnoticed), one flush check that the forecast's own flush satisfied (so
        the census could stop being flushed), and one absent-or-tagged check driven through the
        interrupt path, which returns *before* `_print_not_yet_analysed` is ever reached.
    - **Commits 4 and 5 are unbuilt and still post-launch**, per the placement clause on
      `(r, remaining)`. **"Commit" and "tier" are different numberings** - see the staging note
      there. An earlier version of this line said *"Tiers 3-4 (streaming, app screen)"*, which
      is a category error: there is no data tier 3 or 4, and it made "tier 2" ambiguous between
      the data tier and the commit. Corrected 2026-08-03.

- **(r, remaining) Analyze mode.** Promoted from
  "ideas" and bound to the previously-standalone hash-cache item, because the pairing is what
  makes either worth building.
  - **Analyze mode.** An explicit **"Analyze"** entry point (CLI + app) that runs the existing
    dry-run engine and returns a richer **read-only** report: file counts, photo / video /
    audio split with per-extension formats, exact duplicates with the bytes they waste,
    look-alikes with their potential savings, the capture-date range, and the category split.
    Nothing is written and nothing is organized -- it answers *"what is actually in here?"* for
    someone who wants insight before, or instead of, committing to a run.
    - **Free tier by design.** It is the funnel: the moment someone learns something true
      about their own library is the moment the product earns trust. Gating it would gate the
      argument for using truestill at all.
    - **Shares its soul with the parked web dedup teaser**: same question, same honest answer,
      one in the terminal or app and one in a browser. Build them knowing that.
  - **THE TIERS (designed 2026-08-03). Four data tiers, reported as each completes.** Numbered
    0/1/2a/2b, and **that numbering is data tiers only** -- the *commits* that build them are
    numbered separately below, and the two vocabularies must not be mixed.

    | tier | what it answers | what it reads | cost at 32,628 files / 192 GB |
    |---|---|---|---|
    | **0** census | counts, bytes, formats | directory entries + one `stat` | **sub-second** (measured) |
    | **1** dating | date range, per-year, undated | file *headers*, via exiftool | minutes of CPU, bounded I/O |
    | **2a** exact duplicates | identical copies and the bytes they waste | full bytes of the size-colliding minority | **~12 GB** read |
    | **2b** look-alikes | the same photo at another size or quality | **full bytes of every image** | **~200 GB** read -- the hours |

    - **The split at 2a/2b is the load-bearing part, and collapsing it throws away ~15x on the
      fact users most want.** `compute_hashes` applies a size pre-filter, so SHA-256 runs only
      for files whose byte size collides -- it spares ~94% of realistic-size files
      (`PERFORMANCE.md` §4, and the same figure in the hash-cache entry above). The *perceptual*
      hash has no such filter: it decodes every image, so it reads the whole file. **The
      headline number -- "you are wasting N GB on identical copies" -- therefore needs only
      2a**, the cheap tier. One undifferentiated "duplicates" tier would price the cheap answer
      at the expensive one's cost.
    - **2b's savings are a softer claim and must be worded as one.** Truestill *keeps*
      near-duplicates by design, so their bytes are never reclaimable -- see `insights.py`,
      where `reclaimable_bytes` is exact-only for exactly this reason.
    - **Order is 0 → 1 → 2a → 2b, by measured cost.** Tier 1 is not a prerequisite for 2:
      metadata and hashing are independent passes in `resolve`. Cost is the only reason for the
      ordering.
    - **Not separately invocable; stoppable at any tier, keeping what completed.** Four entry
      points would multiply the surface and invite someone to run 2b without 0. One entry point
      that streams gives the same control under one name -- and the engine already supports the
      stop: `resolve` returns the partial result on cancel, and `HashCache` means a resumed run
      skips what it already hashed.
  - **THE STAGING: four commits, and commit 3 is the one to be careful with.** These are
    **commit** numbers, not tier numbers - commit 1 shipped tier 0, and commit 3 does not build
    a "tier 3".

    | commit | what it does | status |
    |---|---|---|
    | 1 | `truestill analyze`, tier 0 over the shipped `inventory_source` | **shipped** `e8c2692`, polished `58f40fe` |
    | 2 | the facts that existed but were unreachable, moved to `insights.py` | **shipped** `dc9a7d7` |
    | 3a | tiers 1 and 2a reachable from `analyze`, no destination | **shipped 2026-08-03** |
    | 3b | tier streaming and partial-truth reporting | unbuilt |
    | 4 | the app screen, plus export | unbuilt |

    - **Five, not four (corrected 2026-08-03).** Commit 3 split once building it began: 3a is
      the value (the free tier currently stops one tier short of its own headline number,
      because dates and duplicates are reachable only through `organize --dry-run`, **which
      requires a destination** the funnel's audience has not chosen). 3b is the risk. Splitting
      lets the value ship without waiting on the correctness feature, and 3b waits on tier 2a
      being timed against a real library.
    - **3a's sequencing, ruled 2026-08-03: print tier 0, then continue.** The census reaches
      the screen in under a second - the property commit 1 shipped for - and only then does the
      expensive work begin. **This is sequential printing, not 3b**: 3b is the app payload and
      the never-render-zero field tagging.
      - **A forecast prints before the wait**, which is the whole reason the forecast exists:
        *"checking for identical copies, needs to read X GB of your Y GB"*, plus the HEIC note
        when it applies, plus that Ctrl-C keeps what is above. An unexplained wait becomes an
        informed one, and the user can still decide not to have it.
      - **An interrupt reports the unfinished tier as not analysed, never as a partial count.**
        A duplicate total is a claim about the whole set: an unscanned file may be the twin of a
        scanned one, so the pairs found understate by an unknown amount. Unlike a file count it
        has **no honest partial reading**. Tiers complete in sequence, so an interrupt during 2a
        still reports tier 1 in full.
      - **The README's "about a second" claim was reworded** rather than left to become false.
    - **3a has a prerequisite, shipped 2026-08-03:** the read-only hash cache. Tier 2a wants
      SHA-256 without the perceptual hash, and recording that would poison the cache - see the
      hash-cache bullet in `IMPLEMENTATION_STANDARDS.md` §8. Found before building rather than
      after.

    - **Commit 3 is where this stops being a formatting feature and becomes a correctness one.**
      A tier that has not run must say *not yet analysed* and **never render a zero**. Get that
      wrong and the tool tells someone *"no duplicates"* when it has not looked - the worst lie
      this product could tell, and `(aac)`'s discipline arriving on a new surface. Concretely:
      every tier-scoped field is absent-or-tagged rather than defaulted, and the conservation
      law `new_unique + near_dup + exact_dup + unreadable == files` holds **only** once tier 2
      completed, so a partial report must not print a summing block that does not sum.
    - Commits 1 and 2 were each independently valuable and shipped alone, which is the property
      to keep: 3 and 4 must not become one commit.
  - **Why the cache is not a separate item.** Analyze's expensive tiers (1, 2a and 2b above)
    are the same dates-and-hashes pass an organize does. Without a cache the natural journey
    *Analyze → Organize* pays for that pass **twice**, which makes the free analysis feel like a
    tax on organizing rather than an invitation to it. With it, the second pass is nearly free,
    and preview→run and
    repeat batches get faster as a side effect. Shipping Analyze without the cache would ship
    the funnel and the friction in the same release.
  - **Design (unchanged from the original entry).** A small SQLite table keyed on
    `(filepath, file_size, mtime)` → content digest; a lookup validates the file is unchanged
    (size **and** mtime) before trusting the cached digest. Reference implementation to study:
    PixSort `backend/pixsort/utils/hash_cache.py`.
  - **Invariants, restated because they are the whole safety argument:**
    1. **mtime is for invalidation only, never for dating.** The absolute rule
       (`IMPLEMENTATION_STANDARDS.md` §1) is untouched: mtime never influences where a file is
       placed. The cache reads it to ask "did this file change?", which is the one question
       mtime can answer honestly.
    2. **Any size *or* mtime mismatch → hash it fresh.** Never a partial-match heuristic.
    3. **The cache can only ever cost extra work, never produce a wrong answer.** A miss means
       re-hashing; there is no path where a stale entry decides an outcome. If a design choice
       ever trades that away for speed, it is the wrong choice.
    4. **A single cache layer** -- never a second parallel store. PixSort's dual-store drift
       was a defect, not a design.
    5. **Cleanup is wired into the run lifecycle.** PixSort *defined*
       `cleanup_stale_entries()` and **never called it anywhere**, so stale rows accumulated
       forever. Pruning must actually run as part of a run, not merely exist.
  - **Placement:** the **first post-launch wave, alongside (n)**. Earlier if the soak shows
    repeat-run pain at real scale -- that evidence would move it, nothing else needs to.
- **GPS-derived per-photo timezone.** Deferred during Takeout Rescue Mode. `--tz` is a single
  fixed offset for the whole run, which cannot correctly date a library that spans timezones;
  the real fix derives each photo's timezone from its GPS. The near-midnight caveat is
  surfaced honestly in the ingest report until this exists.

- **(kk) Persist GPS at ingest - it is read and then thrown away.** Found while designing trip
  grouping (`trip-grouping-research.md` §5), and the scope is much wider than trips.
  - ✅ **CORRECTED 2026-08-09: THE CAPTURE HALF SHIPPED AT v17 AND THIS ENTRY WAS WRONG.**
    Traced end to end rather than assumed: `exif.py:72-73` requests `GPSLatitude`/`GPSLongitude`,
    `models.py:310` converts them into `CaptureContext`, `catalog.py` writes
    `files.gps_latitude`/`gps_longitude`. Measured on the real catalog: of 395 files ingested
    after v17, **388 carry a camera and 138 carry coordinates**; the 2,300 ingested before it
    carry neither, because v17 deliberately does no backfill. `GPSDateStamp` is still not stored.
  - ⚠ **The paragraph below is the ORIGINAL 2026-07-31 finding and was true when written.** It is
    kept rather than edited because a record that is rewritten to stay correct stops being one -
    but read the correction above first: the catalog has had the columns since v17.
    Verified 2026-07-31: the catalog has **no latitude/longitude columns and no `GPSDateStamp`**.
    `(kk)` was split by ruling - the **`GPSDateStamp`** half belonged to the date-provenance
    program (as the cross-check for a suspect dead-clock date), the lat/lon half serves
    places/map and is separate. **The date-provenance program completed 2026-07-31 without the
    `GPSDateStamp` half**, so this is not "the rest of a mostly-done item": both halves are
    unstarted, and a reader should not have to infer that from the program's closure notes.
  - **The defect.** GPS is read live from exiftool during an organize run and used for the
    event-clustering jump cut (`event_review.py:80` builds `EventItem.gps`), and then it is
    **never written to the catalog**. `files` has no latitude/longitude column at all, and
    `camera_copies_for_events` selects `sha256, captured_at` and nothing else. The data is
    obtained, used once, and discarded.
  - **WHAT THIS MAINTAINER'S LIBRARY SAYS, AND WHAT IT DOES NOT.** Measured 2026-08-09 with
    exiftool over the real 2013-2014 source: **83 of 2,275 files carry GPS - 3.6%** - and they
    come from **one phone out of nine**. The Lumia 820 geotagged 83 of its 114 photos; the P780,
    the Canon IXY, the C5502, the Nexus 5 and four others recorded none at all. Location was off
    by default on that generation.
    **That is a fact about his files and not about the product.** A user arriving today with any
    modern phone has coordinates on nearly every photo, and for them GPS is not a 3.6% signal but
    the **primary** one - and the only naming evidence available to someone whose folders are all
    `DCIM`, which is most people and exactly the user the folder-name suggester has nothing to
    offer. A measurement of one library is a test bed, never a specification.
  - **PRODUCT-LEVEL CAUTION THAT DOES GENERALISE: dense-urban lookup is where this fails.** Both
    measured sets collapse into a handful of ~1.1 km buckets in one metro area - 4 buckets for
    the 83 source points, 7 for the 138 in the catalog. Offline reverse geocoding from GeoNames
    `cities500` gives each place a **single centre point**, so a lookup in a dense area is
    nearest-point and often wrong: Immich issue #8941 (neighbourhoods classified as cities) and
    discussion #12641 (one town's coordinates 12 km out; a 7,000-person district absent from
    `cities500` entirely) are real users hitting exactly this, open since April 2024. Taking the
    **modal place across a whole cluster** rather than tagging one photo is a genuinely safer
    design than theirs - but only if clusters have coordinates.
  - ✅ **CORRECTED 2026-08-10: THE BLOCKER BELOW IS TRUE OF THE INTEGRATION AND FALSE OF THE
    LOOKUP.** Reverse geocoding is a **pure function** - coordinates in, place name out - and is
    testable with a table of known coordinates and **no photos at all**. What needs clusters is
    taking a *modal place across a cluster*; that half is still blocked exactly as described.
    Conflating the two is what made this read as unbuildable. Measured the same day against a
    16-point fixture (Tamil Nadu across scale, a district, four continents, two adversarial
    points), all five GeoNames tiers, licence CC BY 4.0 throughout:
    - **The village case is a tier problem, not a GeoNames problem.** `cities500` misses every
      village under its threshold and answers with a neighbour 2-6 km away; `allCountries`
      filtered to class P (5,220,666 entries) returns `Mūngittoluvu` and `Ūrmenalagiyan` at
      **0 km**. On the 14 non-adversarial points, `cities500` scored 6 exact / 7 right-region /
      1 wrong; class-P scored 5 exact / 9 right-region / **0 wrong**.
    - **But class P is worse where it matters most**, and this is the finding: it answers Chennai
      with `Vepery` (a neighbourhood, population 0) and Paris with an arrondissement. More
      entries buys villages and loses cities, unless lookups are ranked by feature code and
      population - which is exactly what HoudahGeo does and what Immich issue #8941 is about.
    - ⚠ **`Wayanad` does not exist as a populated place.** One row in the whole dump, feature
      class **A** (`ADM2`), population 817,420. Every reverse geocoder filters to class P, so a
      district name is unreachable by construction. This is the motivating case and no tier fixes
      it; it needs admin polygons, which is a different dataset and a different problem.
    - **The name-form question is answered and it is not blocking.** The lookup returns the
      canonical long form (`Tiruchirappalli`, `South`), and `North` / `Tanjore` are both
      present in the `alternatenames` column **already inside the tier files** - 81.7% of
      `cities500` rows carry it. The separate `alternateNamesV2.zip` is 193 MB and is **not
      needed** for this. So a subtraction rule can fire on either form.
    - **Cost is not a constraint.** 150,000 lookups is 0.25 s on `cities500` and 0.39 s on
      class P; the index build is the whole cost (0.5 s versus 10.8 s).
    - ⚠ **Class P breached the 1 GB memory ceiling in this naive form: 1,682 MB peak RSS** to
      hold 5.2M points and a KD-tree, against 145 MB for `cities500`. Any use of it needs a
      packed on-disk index rather than "load it all", and that is a build, not a download.
    **Full record: `reverse-geocoding-research.md`** - tiers, accuracy, name forms, licence,
    and the two questions the design must answer. Nothing committed, no dependency added.
  - ✅ **P34, 2026-08-10: THE DISTRICT IS REACHABLE AS AN ATTRIBUTE, NOT AS A LOOKUP TARGET.**
    The maintainer's hypothesis, verified: every class-P row carries `admin1_code` and
    `admin2_code`, and the nearest populated place to the Wayanad fixture point (`Polacchikuni`,
    0.6 km) has **admin2 = `Wayanad`**. So the motivating case is solved by a **join**, not by a
    bigger dataset - `admin1CodesASCII.txt` (0.14 MB) and `admin2Codes.txt` (2.26 MB), 2.4 MB
    total. Measured with a streaming bounding-box filter at **38.7 MB peak RSS**, against the
    1,683 MB the full class-P load cost.
    - **Coverage:** admin1 on 100.0% of class-P rows, admin2 on **80.7%** globally but 98-99.5%
      for India, France, Japan, Australia and Brazil. Two of fourteen fixture points still came
      back with a **blank** admin2 - Tokyo and Oodnadatta - so a join cannot be assumed to
      resolve and needs a defined answer when it does not.
    - ⚠ **The name forms are the weak half, and the subtraction idea depends on them.** Of the
      eight district forms checked, six are reachable but **only via the admin2 entry's
      `alternatenames`, which `admin2Codes.txt` does not carry** - it has four columns and no
      alternates, so reaching them means joining its geonameid back into the 400 MB
      `allCountries.txt`. Raw, the file offers `Thoothukkudi` (not Thoothukudi), `Tiruppur` (not
      Tirupur), `Kanniyakumari` (not Kanyakumari), `Rāmanāthapuram` with diacritics, and 1,988 of
      47,549 names carrying a redundant `" district"` suffix. `Tirupur` is not among its
      alternates at all.
    - ⚠ **The admin names are not uniformly current, in BOTH directions, within one state.**
      `IN.25.628` is still `Tirunelveli Kattabo` - a form retired in 1997 - while `IN.25.733`
      `Tenkasi district` reflects a 2019 split. France's `FR.84` is still `Rhône-Alpes`, merged
      into Auvergne-Rhône-Alpes in 2016.
    - 📌 **And the finding neither of us anticipated: the era problem.** The Oormelalagiyan point
      returns **Tenkasi**, which is administratively correct *today* and was **Tirunelveli when a
      2013 photo was taken there**. Labelling an old photo with a current district is an
      anachronism the user may reasonably call wrong, and no dataset choice avoids it - the
      boundary moved, not the data. Any design has to decide whether a place name describes
      **where the camera was** or **what that ground is called now**, and say which.
  - **THE REAL BLOCKER: it cannot be BUILT next because it cannot be TESTED here.** *(Read the
    correction above first - this is true of the cluster integration only.)* The catalog
    holds **zero events**, so there is no cluster to take a modal place across, and the 138 points
    that exist sit in one metro area. Building against fixtures we invent is how the junk
    classifier came to be written and never once fired. §4's rule is that a fixture modelled on
    the current library inherits its blind spots; the inverse applies here - **a fixture modelled
    on nothing inherits nothing.**
  - **The cheap unblock, the maintainer's to provide:** a few dozen photos from a current phone
    with location on, taken in two or three different places. That makes the whole thing testable
    at once, including whether non-Western place names come back usably from `cities500`.
  - **Why it matters beyond trips.** A places / map view is a **high user expectation** in
    `org-structure-research.md`, and it is unbuildable without stored coordinates. The trip-edge
    case is only the symptom that exposed it: an arrival evening 80 km from home is trivially
    distinguishable from an evening at home, and truestill had that fact in memory and dropped it.
  - **It is permanently lost for already-organised libraries.** Every library placed before this
    lands has no stored GPS, and recovering it means re-reading every file. **We already pay the
    read cost** on every run - this is a column, not a pass.
  - **Scope:** persist latitude/longitude at ingest; persist `GPSDateStamp` alongside, since
    `date-layering-gap-check.md` §4(b) already ruled it the cross-check for a suspect dead-clock
    date and it is the same exiftool read. **`GPSDateStamp` is part of the date-provenance
    program** with `(n)` / `(ii)` / `(bbb)` recovery (see **Converged programs**) - the lat/lon
    columns also unlock places/map views, which are a separate product surface on the same write.
  - **Open question, deliberately not answered here:** whether existing libraries get a backfill
    pass. It is a re-read of the whole library, so it is opt-in work with a real cost, and it
    wants its own decision rather than being smuggled in with the column.

- **(ll) Sub-day event identity that survives a changing file set.** The day-event half of the
  identity defect recorded in `trip-grouping-research.md` §6.
  - **The defect.** `EventCandidate.signature` (`events.py:109`) is a SHA-256 over the member
    `sha256`s, and that is the `UNIQUE` key `event_by_signature` looks up. Membership *is*
    identity, so ingesting one more photo from an already-named day changes the signature and the
    event is proposed again as new, with the name already given orphaned.
  - **The trip fix does NOT apply here, and this is the point of the entry.** Trips are keyed on
    `trip_days.day` because a day belongs to at most one trip. **Day events are not days.**
    2014-08-16 alone produced two clusters (565 and 157 files) and 2014-08-17 produced three;
    keying on the date would collapse a morning outing and an evening one into one identity and
    silently merge two separately-named events. **Do not apply the day-key remedy to events.**
  - **What is needed instead:** an identity stable under a changing file set that still separates
    several events within one day - a time-anchored key (day plus cluster start, tolerance
    matched) is the obvious candidate and needs its own design pass and its own evidence.

- **Recognize additional real-world video extensions (l).** The metadata-chain corpus surfaced
  container formats truestill's `MEDIA_EXTENSIONS` doesn't recognize, so they are skipped (now
  *reported*, not silent). Recognize the ones that are actually common - **`.vob`, `.ts`, `.m2v`,
  and the `.asf` family at minimum** - with the final list driven by **prevalence evidence, not
  the whole corpus zoo** (`.swf`, raw `.hevc`/`.mjpeg` elementary streams are not "photos to back
  up"). Each extension added must have its **category and date handling verified via the corpus
  probe** before inclusion. **Post-launch, demand-driven.**


- **(aam) Sidebar reference: profile header, section labels, submenus.** Ruled by the
  maintainer, 2026-08-01. **Record only - not built, and one question below blocks building.**
  - **Why the profile header applies at all, corrected.** It was first set aside on the
    assumption that truestill has no accounts. `DECISIONS.md` **D5** supersedes D1: truestill
    **requires a user account**, created at activation against a self-hosted licensing server.
    So an identity in the UI is not scaffolding for a feature that will never exist - it is the
    surface D5 needs. **Cursor is the model:** sign in once, work offline afterwards, identity
    visible in the interface rather than hidden in a settings page.
  - **Profile header:** avatar, name, and **licence state** (Pro / free - **not** trial; see
    `DECISIONS.md` D6 §4, which abolished the trial after this entry was written) in the position
    the reference gives a role line. This is also **where the account surface lands when D5's
    licensing server ships**, so it is built once rather than added beside something later.
  - **Wordmark** from [`brand.md`](brand.md), above or beside the profile header. Which of the
    two is a decision for the build, not now.
  - **Section labels** (`MAIN` / `SETTINGS`), **pill active state**, and a **collapsed icon rail
    with tooltips** - the rail is already built in `(fff)`, so this reference confirms it rather
    than adding it. **Flyout submenu on hover when collapsed** is the new part.
  - **The bottom action is not "Logout".** A one-click logout next to Help treats activation as
    a session, and it is not one: activation happens **once**, and a perpetual licence
    (`DECISIONS.md` D6) is not a login. The bottom item is **account or licence details**, with
    sign-out available *inside* it. Recorded with the reasoning because the failure mode is
    specific and severe: **a casual logout button can strand a user from software they have paid
    for**, on a machine that may be offline, for a product whose whole proposition is custody.
  - **BLOCKING QUESTION, deliberately not answered here: do any screens get NESTED SUBMENUS?**
    truestill's screens are flat today. Adopting the reference's hierarchy means deciding which
    screens have children and which do not, and that is **information architecture, not
    styling** - it changes what the product says its parts are. Needs a ruling before any of
    this is built; the flyout behaviour above is meaningless until it has one.
  - **The cost, recorded so it is priced rather than discovered.** A hover flyout **needs a
    keyboard equivalent**. `(fff)` already established this exact rule for the collapsed rail -
    tooltips on hover **and focus**, recorded there as "not optional polish" - and a submenu
    reachable only by hover is **unreachable by keyboard**, which is worse than a tooltip that
    is merely invisible: the navigation itself becomes unusable. Whatever the answer to the
    nested-submenu question, the flyout is two implementations, not one.

## Settled technical stances (recorded so they are not re-litigated)

- **(aat) `(aar)` is forward-only, and `migrate-layout` will not carry it backwards.** Recorded
  2026-08-02, found while writing `(aar)`'s CHANGELOG entry and checked against the code rather
  than reasoned about. **A known limit with an accepted workaround.**
  - **The mechanism.** `WhatsApp` is a deterministic side-bin label
    (`categorize.deterministic_side_bin_labels`), so `label_routes` returns route `side bin` with
    `needs_decision=False` - *"only a screenshot, messenger or fallback rule can produce this
    label"* - and `rederive_rules` re-reads **ambiguous labels only**. Files already filed under
    `WhatsApp/` are never re-examined, whatever their EXIF says.
  - **`migrate.py` is not wrong.** Its premise survives `(aar)` intact: the filename rule is still
    the only producer of those labels. Re-reading every side-binned file would buy an exiftool
    pass over the largest bin in most libraries to change a handful of them.
  - **The consequence is real, though.** A library organized before 2026-08-02 diverges from what
    a fresh run decides on the same files, and only a re-import from the originals closes it.
  - **Why this is a stance and not work.** Deleting the output and re-running from source is
    acceptable here - the sources are never touched, so it always is. Should rescuing
    already-organized side-bin files ever be wanted, `(ii)`'s rescue flow is the surface that owns
    that question.

- **The catalog stays SQLite.** Parquet and Feather were considered and rejected on three
  grounds, each sufficient alone: they are **immutable** (no row update without rewriting the
  whole file, and the catalog updates a row per organized file), they offer **no transactional
  safety** mid-migration (the journal that makes `migrate-layout` resumable and reversible
  depends on it), and they would add a **heavy `pyarrow` dependency** against §7's stdlib-first
  policy. Columnar formats are right for analytics over immutable batches; this is a mutable
  transactional record. JSON remains in exactly one place - the small, human-readable drive
  marker - where being readable by a person with a text editor is the point. This is also what
  `(z)` means by catalog-first; **no change is pending.**

- **No charting library for Analyze's screens: rejected, hand-rolled SVG instead.** Ruled
  2026-08-03 while designing Analyze, and recorded before the screens are built so commit 4 does
  not re-open it. The app is **offline-first with no build step** and one deliberately
  un-bundled `app.js`, so a chart library cannot be a dependency line - it has to be **vendored
  into `static/`**, which is a permanent maintenance surface, installer weight, and a file
  nobody in this repo wrote. Against that: two bar charts. **The 2026 landscape was checked
  rather than assumed** - Chart.js, ECharts and ApexCharts are the live vanilla-JS options;
  Recharts is React-only and this app is vanilla; Google Charts has been unmaintained since
  2014. The conclusion is not ignorance of the options, it is that none of them is worth
  vendoring for this. Same shape as the `psutil` ruling below: a dependency declined to keep a
  small amount of code we own. Revisit only if a screen genuinely needs interactive charting,
  which two bar charts do not.

- **Treemaps for Analyze: rejected.** Ruled 2026-08-03. Every well-known disk analyzer leads
  with one, so this will be proposed again, and the reason it is wrong here is specific rather
  than aesthetic. **A treemap answers "which subtree is eating my disk?", which presumes a
  hierarchy the user built and understands.** Analyze's whole premise is the opposite: it is
  pointed at an unsorted pile whose folder structure carries no signal, so a treemap of
  `Camera Uploads/` is one large rectangle and tells nobody anything. The proportions worth
  showing are **by media kind and by year**, which are bars or a sparkline, not a treemap. Note
  also what the terminal report already ruled for the same data: **counts, not bars**, because a
  real library spans three orders of magnitude between its quietest and busiest year, so a
  linear bar saturates and a log bar makes a proportion claim that is not true.

- **`psutil` for filesystem detection: rejected.** It would delete `parse_proc_mounts` and the
  `ctypes`/`GetVolumeInformationW` branch in `filesystem.py` - roughly 60 lines including a
  hand-written parser - and `disk_partitions()` reports `fstype` on macOS via `getfsstat`, which
  is the one thing truestill currently cannot answer. Rejected anyway, on four counts: it is a
  **compiled C extension in the runtime graph** of a stdlib-first product; it is a large,
  general-purpose library carried for one function; `disk_partitions()` returns *mounted*
  partitions, so the **longest-prefix match still has to be written on top of it**; and what it
  buys is macOS, which today returns **unknown** and therefore refuses nothing - an honest
  answer, not a broken one.

  **The gap, named so the trade can be reopened on evidence:** on macOS `facts_for` returns
  `FilesystemFacts(filesystem=None, max_file_bytes=None)`. Nothing is refused there, so a macOS
  user copying a >4 GB video to a FAT32 card gets the improved EFBIG *message* after the failure
  instead of the preflight *before* it. If macOS detection ever becomes load-bearing - a report
  of that exact failure, or a feature that needs the filesystem name rather than its limit -
  this is the decision to revisit, and psutil is the candidate to weigh again.

- **`imagehash`: watch, do not move.** Last PyPI release **2025-02-01**, last repository commit
  **2025-04-17**. That is quiet, and quiet is **not** abandoned - the distinction is worth
  keeping, because it decides whether to act. The repository is **not archived**, its 26 open
  issues are open rather than closed en masse, there is no maintainer statement winding it down,
  and **no fork is positioned as a successor**. That is the opposite of the httpx picture, where
  the issue tracker and discussions were closed and Pydantic's `httpx2` was named by the
  maintainers as the path forward - which is why httpx was a move and this is a watch.

  **What would turn it into a move:** an archive notice, a maintainer statement, a security
  finding left unfixed, or a successor with real adoption. Absent one of those, the cost of
  switching a perceptual hash is the point: the catalog stores its exact bit output, so any
  replacement re-hashes every library or silently changes what counts as a near-duplicate.

- **Distributed task queues (Taskiq, Celery, Dramatiq) stay out of the desktop app.** They are
  *distributed* queues: their purpose is dispatching work across a network to separate worker
  processes, and each requires a broker - Redis, RabbitMQ, NATS or Kafka. Taskiq's own
  introduction says it exists because nothing could send async functions over distributed queues
  like RabbitMQ. That is a real problem, and it is not this one.

  truestill is a single-user desktop app: one process, no network, no worker fleet. Adopting one
  would mean asking a photographer to install and run Redis before organising their photos -
  precisely the install friction recorded against Immich's Docker requirement in
  `docs/org-structure-research.md`, and the thing this product is positioned against.

  **What is already there instead:** `JobManager`, roughly one module. Background threads
  in-process, SSE progress, cancel, and a per-drive lock. It covers every long operation -
  organize, verify, backup, migrate, trip apply, archive ingest, undo - with no service for the
  user to run and nothing to keep alive between sessions.

  **Where one WOULD be a reasonable choice, so this rejection is not over-read:** the
  self-hosted licensing and update server (`docs/DECISIONS.md` **D5**) is a genuinely networked
  service, and a queue is a fair question there. That is post-launch, unbuilt, and its own
  decision. Nothing here rules on it.

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

- **(aal) How often is the machine wrong about dates, and about what?** Recorded 2026-07-31,
  separated from `(aaj)` deliberately. **Idea - do not build schema for it now.**
  - **The question.** Across a library, where does human correction disagree with machine
    derivation - which tiers, which cameras, which filename patterns? truestill is the only tool
    that records both a machine tier and a human override, so it is uniquely able to answer it.
  - **Why it is not `(aaj)`.** A conflict *note* is one sentence on one file. A conflict *rate*
    is an aggregate over time, and it is the use that would genuinely justify keeping the
    superseded evidence - a column holding what the machine thought before it was overruled is
    debt when its only consumer is explanatory text, and an asset when it is the dataset.
  - **Nobody has asked for this.** It is recorded so the reasoning is not lost, and explicitly
    **not** as licence to add the column now. If it is ever built, the column is justified by
    *this*, and `(aaj)` stays closed on its own merits.

- **(m) Duplicate-cleanup staging UX.** ⚠ **Overlaps `(aag)`** - the visual side-by-side compare
  described below *is* `(aag)`'s subject. Scope them together or the same review surface gets
  designed twice; `(aag)` also records why it is deferrable (truestill already keeps and flags
  near-duplicates, so it is a review surface over correct behaviour, not a correctness gap).
  A **preview → confirm → trash (with restore)** flow for
  removing duplicates - the validated safe-delete pattern (same spirit as `reclaim`'s dry-run +
  typed confirm, but for dedup). Note the real gap PixSort never closed: truestill's near-duplicate
  review still needs a **visual side-by-side compare** (show the two look-alikes at actual pixels
  so a human decides which to keep) - PixSort had no such compare, and a trash-with-restore is
  only trustworthy once the human can actually *see* what they're removing.

  **Binding design constraints, from reviewing PixSort's live duplicate screen:**

  1. **Never auto-select keep/remove by filesystem timestamp.** Observed on real data: PixSort's
     "keep oldest" chose a `(Copy).jpg` to **keep** and the original to **remove**, because the
     mtimes lied - a copy operation had rewritten them. This is the **same lie truestill already
     refuses for dating** (`IMPLEMENTATION_STANDARDS.md` §1: "Dating uses an evidence chain, never
     filesystem mtime"). That invariant currently governs *placement* only; item (m) extends the
     identical distrust to **keep/remove selection**, where being wrong is irreversible rather
     than merely untidy. The corpus already contains this exact shape (`scan-a.jpg` + its
     `(Copy)`), so it is testable on day one.
  2. **Rank by evidence, in this order:** embedded capture date → resolution / bitrate →
     original filename pattern (a `(Copy)`/`(1)`/`-kopie` suffix is evidence *against* being the
     original) → catalog provenance (what truestill already recorded about where each copy came
     from). Every one of these is a property of the *file*, not of the filesystem around it.
  3. **Default to NO pre-selection when the evidence is ambiguous.** A pre-ticked checkbox is a
     recommendation the user will accept without reading; if truestill cannot prove which copy is
     the original, it must say so and select nothing. **A reviewed decision, not a trusted
     heuristic** - and never a heuristic wearing a decision's clothes.
  4. **Staged trash-with-restore, never a permanent delete**, with the two actions labelled by
     consequence - **"Recommended"** vs **"Irreversible"** - so the dangerous one is never the
     path of least resistance. Same spirit as `reclaim`'s typed `delete` confirmation.
  5. **Adopt the honest capability notice pattern**: state plainly what the screen can and cannot
     determine, in place, rather than implying more certainty than the evidence supports. This is
     the never-silent rule applied to a UI surface - the existing precedents are the HEIC
     perceptual-skip notice and the Tier A / Tier B date-quality lines.

  **Quality ranking - the layer that makes the review worth doing (research-grounded).**
  Within each near-duplicate group, rank the candidates by objective quality signals and use
  that ranking to power the side-by-side review's **default suggestion**.

  - **Never auto-action.** Constraint 3 above stands unchanged: a ranking produces a
    *suggestion*, and where the evidence is weak it must still suggest nothing. Ranking makes
    the human's decision cheaper; it does not make it for them.
  - **Why this is the value, from the literature.** Representative-photo-selection and
    burst-quality-assessment work (the PhotoCluster lineage through current blur/quality
    assessment research) consistently finds that in de-duplication and burst review the
    bottleneck is **review effort, not judgement**: people know which photo they want once
    they see the pair, and give up long before they finish looking. A good ranked default is
    therefore the feature -- it turns "review 400 pairs" into "confirm 400 defaults, correct
    a few". Presenting an unranked pile is what makes duplicate review get abandoned.
  - **Signals, cheapest first:** sharpness (Laplacian variance and similar classical focus
    measures), exposure sanity, and resolution -- plus the evidence truestill already has from
    constraint 2: original-vs-recompressed, and the copy-suffix filename pattern as *negative*
    evidence.
  - **Classical metrics first, zero ML dependencies.** They are cheap, explainable in one
    sentence to a user, and defensible in a UI that promises honesty about what it can
    determine. A learned model is only ever a justified later step, against measured
    inadequacy of the simple metrics -- and it would have to earn its dependency against the
    same policy every other dependency does (`IMPLEMENTATION_STANDARDS.md` §7).
  - **Positioning:** this is what makes (m) the **Pro-tier crown feature alongside (p)**. The
    safe-delete flow is the table stakes; knowing which copy to keep is the part worth paying
    for.
- **(p) "Share safely" - metadata-stripping export. PRO TIER (behind the capability seam).**
  A dedicated **export** action that writes cleaned copies for sharing, so a user can post a photo
  without leaking where they live or what device they use. Market demand is documented (a whole app
  category - CleanShots, ExifStrip, etc.; dating / kids / marketplace / forum use cases; email /
  Slack / Telegram-file preserve EXIF). **Design decisions, recorded now:**
  1. **Export-only, never a library operation.** The user selects files; truestill writes cleaned
     copies to a dedicated **share-export folder**. The organized library and the originals keep
     their full metadata, untouched. A strip control anywhere near the library would contradict
     truestill's metadata-preservation identity and invite accidents - it lives only in this export.
  2. **Complete removal, verified.** `exiftool -all=` on the copy (clears EXIF + XMP + IPTC +
     MakerNotes + embedded thumbnails - the thumbnail is the classic leak); for video, an exiftool
     pass **plus** an ffmpeg container rewrite (`-map_metadata -1`, no re-encode) for the
     `uuid`/`udta` boxes; handle **Live Photo** JPEG+MOV pairs together. Then **re-scan each output**
     and produce a verification report ("0 metadata fields remain") - the never-silent rule applied
     to removal. UI states honestly that cleaning affects the *copies*; the originals still exist
     with their metadata (that is the point).
  3. **Folder protection + lineage.** The share-export folder gets a `.truestill-shared.json` marker;
     the scanner **refuses a marked folder as an organize source** with a clear explanation (so
     dateless cleaned copies are never re-swept into `Undated/`). The catalog records lineage
     (cleaned copy ↔ source hash) so dedup never mistakes a stripped copy for a lost original.
  4. **Modes:** **strip-all** (default) and **GPS-only** - the two the market ships.

  Post-launch build; Pro-tier candidate. Research refs to carry in: the embedded-thumbnail trap,
  the XMP/IPTC/MakerNotes layers, MP4 container metadata boxes, and Live Photo pairing.

- **(x) XMP sidecar export for user-generated context.** Post-launch, demand-driven. Trip and
  event names are the one thing in a truestill library the *user* created rather than the files
  carrying it - so they are the one thing that is currently lost if someone stops using
  truestill. Writing them to standard XMP sidecars makes them portable to Lightroom, digiKam,
  Immich and anything else that reads XMP.
  - **Why it fits the identity rather than diluting it.** The promise is a library you can
    still read without the tool. That already holds for *files* (ordinary folders, ordinary
    names, full metadata). It does **not** yet hold for the context the user added on top.
    This closes that gap, and it is the no-lock-in argument taken to its own conclusion: the
    exit path should be complete, not partial.
  - **Sidecars, never in-place edits, by default.** Writing into originals contradicts §1;
    a sidecar sits beside the file and can be deleted with no trace. The scoped Takeout bake
    stays the only path that modifies content, and it stays scoped.
  - **Open questions for the research pass**, none of them blocking today: which XMP fields
    carry an "event" honestly across readers, whether sidecars belong beside the organized copy
    or the source, and what happens on re-export when a user has renamed an event.
  - **This is export, not a second source of truth.** The catalog stays authoritative;
    re-importing user context from sidecars is a separate question and is *not* part of this
    item.
  - **Virtual views, albums-as-first-class-objects and faces remain out of scope**, unchanged -
    see "Consciously out of scope" below and the composition stance recorded there. Portable
    *context* is not the same request as a gallery.
- **(hh) `truestill adopt` - bring stray media in an organized drive into the catalog.** Ruled
  by the maintainer. A drive can hold media truestill does not know about: files copied in by hand, a
  restore from elsewhere, or anything added after the last run. Today they are invisible to
  `verify`, to the custody count, and to `clean-empty`'s classification.
  - **Scan an organized drive for media files not in the catalog, report them named**, and on
    confirm run them **through the full normal organize pipeline** - EXIF, category rules, dating,
    dedup all decide placement.
  - ⚠ **Never the folder they were found in.** A file sitting in `Camera/2019/` is not evidence
    that it is a 2019 camera photo; someone may have dropped it anywhere. Placement is derived
    from the file's own metadata like every other file, or truestill would be laundering a
    guess as a decision - the same mistake the `(m)` selection rules forbid.
  - **Never automatic, never silent.** Offered after `verify` or `migrate-layout` when unknowns
    are found, and available standalone. Preview names every file; a typed confirm adopts.
  - **Precedent:** Lightroom's *Synchronize Folder*, which is the same operation for the same
    reason and is well understood by the audience.
  - **Shares the walk-and-classify machinery with `clean-empty`** - both answer "what is on this
    drive that the catalog does not account for", from opposite ends.
  - **(abe) needs this too, recorded 2026-08-05.** Files organized by the CLI before it
    registered its destination are in `files` with no `file_copies` row - the same
    "content is on the drive, the catalog does not know" shape from the other side. If
    this is built, it is the repair path for those rows, and `(abe)` argues no separate
    mechanism should be written for them.

- **(aao) Asset pairing: several files that are one photo.** Recorded 2026-08-02. **Post-launch,
  record only - needs a design pass before any build.** Names the concept that `(y)`, `(p)` and
  `(aag)` have each been circling without one.
  - **The gap.** Truestill treats every file as an independent asset, and several ordinary cases
    are one capture stored as several files: an Apple Live Photo (`.HEIC` + `_HEVC.MOV`), a
    camera shooting RAW+JPEG (`ABC001.ARW` + `ABC001.JPEG`), exported edits (`ABC001-1.JPEG`),
    and bursts. **Neither dedup tier pairs them** - SHA-256 sees different bytes, and RAW or HEIC
    may yield no perceptual hash at all. Verified 2026-08-02: no pairing logic exists anywhere in
    `src`. A Live Photo pair currently survives organize only by the coincidence of a shared
    capture time.
  - **The field has proofs, not just heuristics, and that shapes the tiers.** Both halves of a
    Live Photo carry the same `ContentIdentifier` UUID, and iPhone bursts share a `BurstUUID`;
    those are identifiers, not guesses. RAW+JPEG has no such identifier and is matched on
    basename - PhotoPrism requires *same folder plus same basename* explicitly to avoid scanning
    the library for a partner per RAW, with the counter-proposal being one pass building
    `basename -> paths`. Filename matching alone is unreliable, since differing basenames cannot
    be grouped that way at all. Capture time **corroborates but cannot prove**: Lightroom is
    criticised for ignoring it, and some cameras record *different* times for the two halves of
    one RAW+JPEG pair. The framing worth keeping is that the goal is to find duplicate **images**,
    not duplicate **files**.
  - **Proposed tiers, mirroring the date-provenance design. A proposal, not a decision.**
    (1) *Exact* - shared `ContentIdentifier` / `BurstUUID`. (2) *Strong* - same folder, same
    basename, different extension, corroborated by capture time. (3) *Weak* - export-suffix
    patterns (`-1`, `~edit`). **Tier 1 has a stated cost:** neither tag is in `REQUESTED_TAGS`,
    so adopting it changes `tags_fingerprint` and forces one cold exiftool pass over the library -
    the same cost profile recorded against `GPSAltitude` in `(kk)`. Recorded, not ruled on.
  - **What matters here is custody, not display, and that is where truestill differs from the
    galleries.** Stacking as a *view* is largely irrelevant to a tool that is not a gallery. What
    matters is that an asset survives organize intact. **All three of these need verification
    before building - they are the questions, not findings:** whether both halves land in the
    same folder (the risk `(y)` warns of for a future photo/video split); whether date-based
    renaming severs the basename link when one half gets a collision suffix and the other does
    not; and whether `reclaim` can delete one half of a pair, which is the safety question,
    given `plan_reclaim` checks only that the source *exists*.
  - **Cross-references.** `(y)` calls pairing "the real work" and warns *"do not build the split
    first and pair later"*; `(p)` needs it for share-export; `(aag)` is burst review, which tier 1
    would answer with `BurstUUID` rather than a heuristic.

- **(aaq) `rule_software` reads a tag that is never requested, so it cannot fire.** Recorded
  2026-08-02. **REDUCED 2026-08-12** (`SHIPPED.md`): the `SamsungModel` half is closed - deleted,
  not enabled - and the class now has a detector, `test_categorizer_tags_are_requested.py`, which
  fails if any tag `categorize.py` reads is absent from `REQUESTED_TAGS`. `Software` is its one
  documented exemption, and this entry is what the exemption names.
  **What remains is a product decision and needs the maintainer**, per the three ways out below.
  - ✅ **The `SamsungModel` fallback: CLOSED, deleted.** See `SHIPPED.md`. No evidence anywhere
    available justified requesting the tag, and requesting it invalidates every cached metadata
    row in every library.
  - **`rule_software`, the whole rule.** It reads `Software`, which is **not in `REQUESTED_TAGS`**
    either. Measured 2026-08-02: a JPEG stamped `Software=Adobe Photoshop 24.0 (Windows)` comes
    back from `read_metadata` with keys `DateTimeOriginal`, `FileType`, `ImageHeight`,
    `ImageWidth`, `MIMEType`, `SourceFile` - no `Software` - and categorises as `Saved` through
    `RuleName.FALLBACK`. Its own docstring calls it *"the main open-ended path: any application
    that stamps `Software` gets its own folder"*, and that path is unreachable. `_software_family`
    and `_GENERIC_SOFTWARE` exist only to serve it, and `layout.py`'s `RuleName.SOFTWARE` side-bin
    branch is only reachable through it. The module docstring's rule 3 describes behaviour the
    product does not have.
  - **THE DECISION, restated 2026-08-12 once the cost below was measured. It is three ways out,
    not two, and the middle one is new:**
    1. ***Request the tag as it stands.*** Now measurable and now clearly bad: 159 files with a
       working camera `Model` leave the timeline, and 3 folder labels become 97. Not a repair.
    2. ***Reorder `rule_software` below the device rule and constrain the label set, then request
       the tag.*** This is the option the entry did not have. It keeps the case the rule was
       written for - "everything I edited in Lightroom" - while a camera `Model`, which is real
       evidence of origin, outranks "was opened once in an editor". `_GENERIC_SOFTWARE`'s
       five-value exclusion list is the wrong shape for `Version` and `Binary data`; an allow-list
       or a plausibility test is.
    3. ***Delete the dead path*** and record why - costs nothing, discards whatever case it was
       written for.
    - Requesting the tag in options 1 and 2 also changes `tags_fingerprint`, invalidating every
      cached metadata row and forcing a cold exiftool pass, so it needs a reason beyond tidiness.
    - **This is now decidable in one sitting, which it was not before**: the cost of option 1 is
      a number, option 2 names what would have to change, and option 3 is unchanged.
  - **What "request the tag" would actually cost, measured 2026-08-12 rather than argued.** The
    entry called it a product decision without a number; here is the number. 1,258 media files
    across 78 camera makes (`metadata-extractor-images` + `exif-samples`), graded through the real
    `categorize`, production tag set versus the same set plus `Software`:

    | | production today | if `Software` were requested |
    |---|---|---|
    | filed as `Camera` (rule 4) | **461** | 302 |
    | filed by `rule_software` | - | **313** |
    | `Saved` (fallback) | 791 | 637 |
    | files carrying a real camera `Model` **not** filed as `Camera` | **0** | **159** |
    | distinct folder labels created | **3** | **97** |

    So requesting the tag takes **159 files that carry a working camera `Model` out of the
    timeline** and into an editor's folder - a Nikon D200 photo that was once opened in Photoshop
    files under `Adobe Photoshop/`, and `Pentax QS1.dng` (`Model: PENTAX Q-S1`) files under
    `PENTAX/` rather than `Camera/`. **Rule 3 sits above rule 4, so on any file carrying both it
    wins**, and "edited once" is not evidence of origin the way a camera model is.
    - **And the folder count is the sharper half: 3 labels become 97.** `_GENERIC_SOFTWARE`
      excludes five values, which is not the shape of the problem - the labels this produced
      include `Version`, `Binary data`, `Digital Camera`, `GLDPNG ver`, `Nikon Transfer` and
      `ImageMagick`. An open-ended folder-per-application rule inherits whatever junk vendors
      write into a free-text field.
    - Neither number argues for deletion by itself - a real "everything I edited in Lightroom"
      folder is a defensible product. They do say that requesting the tag **as it stands** would
      be a visible regression on ordinary camera libraries, so the decision is not "request or
      delete" but "reorder below rule 4 and constrain the label set, or delete".
  - **Worth checking first for `SamsungModel`: it may have been meant to come from
    `SamsungCaptureInfo`**, which **is** requested and is already used by the screenshot rule. If
    the Samsung model is derivable from that tag, the fix is a parse rather than a new request -
    and free.
  - **A dead rule still occupies a position in the chain.** `rule_software` sits between the
    filename conventions and the device rule, so anyone reasoning about `build_rules` is reading
    six rules when only five can fire - and any change to that ordering has to say what would
    happen the day `Software` is requested, not only what happens today. `(aar)`
    (`SHIPPED.md`) is the case that ran into it: it deferred within rule 2 rather than moving
    rule 2 below rule 4, **because a reordering would also hand messenger files to this rule**
    the day its tag is requested. So the dead rule already constrained a real design choice
    once, without ever executing.

- **(y) Optional photo / video split - default TOGETHER, and pair-aware or not at all.**
  Post-layout-correction. An opt-in that separates standalone videos into their own top-level
  branch, leaving photos on the timeline.
  - **The default stays together**, because a chronological timeline is the thing the layout
    correction exists to produce and splitting media types cuts across it. This is a preference,
    not an improvement.
  - ⚠ **The constraint that makes or breaks it: a naive split destroys Live / Motion Photos.**
    An iPhone Live Photo is a **pair** - a `.HEIC`/`.JPG` still plus a `.MOV` sharing a content
    identifier - and a Samsung Motion Photo is the same idea. A split that routes by extension
    sends the still to `Photos/` and its motion half to `Videos/`, silently dismembering an asset
    the user thinks of as one thing. This failure is documented in Apple's own asset model and
    has been reported repeatedly against Immich; it is not hypothetical.
  - **Therefore: the pair moves together, and only a STANDALONE video goes to `Videos/`.** A
    `.MOV` that is the motion half of a Live Photo is not a video for this purpose.
  - **Depends on asset pairing**, which truestill does not have yet - matching a still to its
    motion half (content identifier where present, else name + timestamp + duration heuristics).
    That dependency is the real work; the split itself is a routing branch once pairing exists.
    **Do not build the split first and pair later** - shipping it in that order is shipping the
    dismemberment.
  - Fits the existing router as a third axis (`LayoutScheme` already routes on rule, then on
    evented), so the mechanism is understood; it is blocked on evidence, not on design.

- **(z) Optional source / device manifest - catalog-first, hash-keyed.**
  Post-layout-correction, opt-in, **local-only** (no network; the no-library-data rule of D5
  applies). Answers "what
  device and which app did this file come from?" across a library.
  - **Catalog-first, keyed by content hash.** The catalog already keys everything on `sha256`,
    which is what makes the record survive a rename, a move, a re-layout and an in-place
    organize. A path-keyed record would be wrong the first time `migrate-layout` ran.
  - ⚠ **The JSON is a GENERATED EXPORT, never a loose per-file sidecar.** Per-file sidecars
    orphan the moment a file is renamed or moved - the exact failure the hash key exists to
    avoid - and they would also scatter truestill-named artifacts across a user's drive, which
    §3.1 keeps to a single marker file. Export on demand; regenerate rather than maintain.
  - **The data is largely already known:** device from EXIF `Make`/`Model` (the `device` rule
    already reads them), platform/app from the derived category, and both are already recorded
    per file. This is mostly a query and a serializer, not new extraction.
  - **Opt-in** because it is a reporting feature, not part of custody; nothing about placement
    or verification should depend on it.
  - Open question for the research pass: whether it persists a `device` column (a schema
    version) or derives on demand from stored metadata - decide on measured query cost, not
    taste.

- **(s) Source-folder names as event evidence.** Generalize the Takeout **album → event**
  mapping to plain sources: a meaningful source folder name becomes a **pre-named event
  proposal** in the existing review flow.
  - **The problem, concretely:** an `Olympics/` input folder scatters by capture date today
    and its name -- the single best piece of evidence about what those photos *are* -- is
    discarded. Dates say when; the folder said what.
  - **Filtered against noise:** `DCIM`, `Camera`, `Pictures`, date-pattern directories
    (`2024-06-15`, `20240615`) and similar carry no meaning and must not become event names.
  - **Never auto-applied.** It produces *proposals*; the user confirms, renames or skips, in
    the review flow that already exists. A folder name is evidence, not a decision -- the
    same posture as every other derived label.
  - Reuses `events` + `event_review` machinery; the new part is the evidence source and its
    noise filter.
- **(t) Reflink / copy-on-write fast path.** On filesystems that support it (APFS, btrfs, XFS,
  ReFS) a clone (`FICLONE` / `clonefile`) makes a copy effectively instant and free.
  **Optimization, not correctness** -- `shutil.copy2` already uses `sendfile`/`fcopyfile` fast
  paths today, so this is a further step rather than a missing one, and newer Python is
  growing stdlib support worth waiting for.
  - ⚠ **Recorded caution, to design against before building:** a clone initially **shares
    blocks with the source**. That interacts directly with the independent-verified-copy story
    -- `copy_sha256` would still verify, because the bytes are identical, but "a second copy"
    that shares extents with the first is not the same thing as an independent one for the
    purposes truestill's custody model claims. Two files on one drive sharing blocks survive
    a `verify` and do **not** survive the block going bad. Decide explicitly what a cloned
    copy means for `file_copies`, for the custody count, and for the at-risk banner **before**
    any of it ships; the honest answer may be that clones are fine within a drive but must
    never count toward 3-2-1 redundancy.

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
    fix is **`(vv)`'s on-disk lock, not weakening the comparison**; the residual and its cost
    are recorded on `(vv)`.

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
