# (adx) A LIBRARY THAT MOVES IS HANDLED. WHAT IS MISSING IS THE DISCLOSURE.

*Body of backlog entry `(adx)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adx) A LIBRARY THAT MOVES IS HANDLED. WHAT IS MISSING IS THE DISCLOSURE.** Recorded
  2026-08-18 from a traced walkthrough of the ordinary journey: organize locally because working
  directly on an external or cloud drive is slow, then move the finished library onto it. **Three
  gaps, one user journey**, filed together because a user meets them in sequence and fixing one
  alone leaves the sequence broken. **None of them is a broken path** - the paths work. All three
  are things the product knows and does not say.

  ## ✅ FIRST, WHAT IS PROVEN GOOD - because it is load-bearing and was nowhere written down

  Traced 2026-08-18 against a real 25-photo library built from the corpus, organized to `A`,
  moved wholesale to `B`, then cloned to `C`. Not reasoned from the code; run.

  - **Organized content stores NO absolute path.** `file_copies` is keyed `(sha256, drive_uuid)`
    with a `relative` column (`catalog.py` `_SCHEMA`); `drives` carries `uuid` and `label` and
    **has no path column at all**. Absolute paths exist in exactly two places, and neither locates
    organized content: `files.source_path` (where a file *came from*) and the `path_hint.*` /
    `library.root` settings (conveniences).
  - **Identity is a truestill-minted `uuid4` in `.truestill-drive.json` at the tree root**
    (`drive.py:47`, `:471`), so it **travels with the data** rather than describing the volume
    under it.
  - **A wholesale move self-heals with one command.** After `A -> B`: `truestill verify B` reported
    **25 verified, 0 missing**, and rewrote the remembered path (`cli.py:1289` (`remember_drive_root`)) - after which
    `truestill drives` read `connected` again. **No repair step, no reconnect flow, no data
    surgery.** `source_repoint.py:3-8` asserts exactly this; it is now measured rather than
    claimed.
  - 🔑 **digiKam's documented failure is STRUCTURALLY IMPOSSIBLE here, not merely avoided.**
    digiKam stores a volume UUID plus `specificPath` in `AlbumRoots` and calls the collection
    missing when no volume carries that UUID - the remedy being a refresh button or editing
    database rows. That failure needs identity to live **outside** the data. Ours lives **inside**
    it. There is no event - clone, reformat, remount, new machine - that changes a file's contents
    and therefore no event that can orphan a library this way.
  - **Worth a guard eventually, and deliberately not built here.** The property *"no absolute path
    ever locates organized content"* is an architectural invariant that currently holds by
    everybody's care. A test asserting it over the schema and the write paths would keep it true;
    that is a separate, small piece of work and this entry does not do it.

  ## The gaps, ranked

  ### (1) `verify` ACCEPTS A CLONE SILENTLY, AND CUSTODY THEN UNDER-REPORTS

  **The worst of the three, because it is wrong in the dangerous direction for a custody product:
  it tells a user they have FEWER copies than they do.** A person who then deletes one, believing
  it unprotected, is acting on our arithmetic.

  - **Traced.** `cp -a B C` copies the marker, so both trees carry uuid
    `e9a4ec3c-…`. `truestill verify C` reported **25 verified, 0 missing**, silently rewrote the
    remembered path from `B` to `C`, and left **one** `drives` row. `truestill status` continued
    to say *"25 file(s) exist on only ONE drive"* while **two** complete copies existed on disk.
  - ⚠ **THE RULING IS NOT IN QUESTION AND MUST NOT BE WITHDRAWN.**
    `drive-identity-research.md:82-85` decided that *"clones are identical at clone time, so
    sharing identity is correct until they diverge"*, and that is right - auto-disambiguating
    would mint a second identity for one library and count one copy as two, which is the same
    error in the other direction. **The ruling is sound; the disclosure it specified is missing.**
  - 🔑 **The specific missing half.** That same proposal has three parts: treat same-uuid as one
    logical drive (**built**), `drives init --relabel` for a diverged clone (**built**, as
    `--force-new-identity`), and **"warn when one uuid is seen at two distinct mount paths in a
    single run"** - which exists **only on the registration path**. `_print_adoption_refusal`
    (`cli.py:1159` (`_init_drive`)) refuses and explains both ways forward when someone registers a folder that
    already holds a recorded library. **`verify` has no equivalent check**: it proves the content,
    moves the hint, and says nothing about the path it just stopped pointing at.
  - **What a user could do before this shipped:** nothing they would find. The remedy existed
    (`--force-new-identity`) and nothing on the path they were walking named it.
  - ✅ **BUILT 2026-08-18 - the disclosure, not a decision.** `second_location_note` /
    `second_location_for` (`truestill_core/drive.py`) report a second **live** path for one uuid.
    `truestill verify` on a clone now names both places, dates the other sighting, and prints the
    `--force-new-identity` command; a plain move stays silent. The app's Check screen carries it
    as `VerifyJobSummary.second_location`. **The ruling is untouched**: nothing disambiguates,
    nothing refuses, no second identity is minted.
    - **Only the case that cannot be wrong is reported** - the remembered path still answering
      with the same uuid. Gone, different drive, same path, or no answer in time: silent, because
      a move and a clone-with-the-original-unplugged are the same observation.
    - **The FUSE decision, since it had no prior ruling.** The probe is bounded at **1.0 s** on a
      daemon thread. A blocked `stat` on a hard mount is uninterruptible - `SIGALRM` does not
      reach it - so the thread can only be *abandoned*, and abandoning is safe here: bpo-32186
      (`fstat` holding the GIL inside `fileio_init`) was fixed in 2017 and this project requires
      3.13. A path that times out is remembered for the process so the same wedged mount cannot
      park a second thread. ⚠ **The 1.0 is a judgement, not a measurement** - `run_health` prices
      `read_marker` at 21.18 us local and a FUSE `stat` at ~600 us, which bounds the *fast* case;
      no wedged mount could be staged. A live-but-slow mount over the budget produces a **missed**
      disclosure, never a false one.
    - **The gating fix.** `_adoption_block` was gated on `marker is None`, which dropped the free
      **path** comparison along with the expensive **content** inspection (up to 40 stats + 3
      full-file hashes per known drive). The content reasoning stands and is unchanged; the two
      are now separate.
    - ⚠ **TWO SITES STILL DISCLOSE NOTHING**, named in the guard with what a user loses rather
      than only why it is hard: `attach_drive` (`DriveAttachment` is never serialised and the
      write path's return value is discarded, so there is no carrier) and the app's organize run
      (`CompletionBase` was described here as *"a 17-key payload pinned by two e2e tests"* -
      ⚠ **CORRECTED 2026-08-20: THAT OBSTACLE WAS FOLKLORE.** It has **19** keys, not 17; the
      Python guard is `set(summary) >= {...}`, a **superset** check that had already absorbed
      three additions; and the e2e files that touch it **author their own partial summaries** and
      assert on rendered text - none reads the payload's key set. The cancel path already ships a
      20th key through the same renderer. Priced properly it costs nothing, and `(aem)` confirmed
      it by adding no key at all. **The number was wrong in four places and no test asserted it**,
      which is how a constraint recorded once became a fact that scoped this entry's own work -
      `ENGINEERING_STANDARD.md` §4's fifty-sixth member). **An organize against a
      cloned destination, and an attach of a drive that already answers elsewhere, are both still
      silent.**
    - **Guarded** by `test_every_hint_write_checks_for_a_second_place.py`, which enumerates all
      six sites that bind a uuid to a path and requires **both** lists to be exhaustive - a site
      in neither fails, so a seventh cannot appear without a decision.

  ### (2) `offline -> verify -> connected` IS UNDISCOVERABLE

  - **Traced.** Immediately after `A -> B` and before any verify: `truestill drives` read
    **`offline`**, and `truestill status` listed all 25 files with **no error and no mention that
    anything had moved**. The catalog was completely intact; the only thing wrong was a stale
    hint.
  - **Why it stays stuck.** `drive_reach` (`drive.py:200-215`) reads the marker **at the remembered
    path and nowhere else** - by design, since searching for a drive is not something a custody
    tool should do speculatively. So the state persists until someone happens to run
    `truestill verify <new path>`, **and nothing anywhere names that command.** A user is told
    their drive is offline while it is plugged in and one command from being recognised.
  - ⚠ **The label compounds it.** `drives.label` is captured at registration and never follows the
    path, so after `A -> B` every surface still says drive `'A'`. Correct - a label is a name, not
    a location - and it means the one string on screen is the one that has not changed.

  ### (3) `library.root` PREFILLS A DESTINATION THAT NO LONGER EXISTS

  **The mildest, and the closest to Lightroom's documented worst case** - a preference naming a
  drive that is gone. Milder here: it produces no error, and the non-clearing is deliberate.

  - **Measured** with both keys pointed at the vanished `A`: `library_path` cleared **itself** to
    `None` (`take_live_path_hint`, `drive_support.py:122-137`), while `library_root` kept the dead
    path and `needs_library_root` stayed `False`.
  - The browser prefills the organize destination with `library_path || library_root`
    (`app.js:1700`), so the field offers **the path that no longer exists**.
  - ⚠ **The non-clearing is correct and must not be "fixed" by clearing it.** `drives.py:47-60`
    records why: `library.root` is *declared*, not observed, and auto-clearing it would make first
    run re-arm every time an external drive was unplugged. **The bug is in what is offered, not in
    what is stored.**

  ## Scope

  - **These are three symptoms of one thing:** the product has the right answer and does not say
    it. Every gap is a sentence or a check, not a mechanism.
  - **Not covered by `(yy)`/`repoint-sources`**, which repairs `files.source_path` - the *sources*,
    not the library, and its own docstring says organized trees need no repair (now verified).
  - **Not `(aba)`**, which is a file hand-moved *within* a drive making `verify` report MISSING.
    The trace here kept the tree intact, so `(aba)` never fires. Different failure, different fix.
  - **No design here. No fix here.**
