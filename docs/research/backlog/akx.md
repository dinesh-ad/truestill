# (akx) THREE THINGS A PERSON MEETS, NONE OF WHICH A TEST COULD HAVE CAUGHT.

*Body of backlog entry `(akx)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

Three findings from **using** the product. They share one shape: each is a sentence or a number on
a screen that no assertion was ever pointed at, because each sits in the gap between a test's
setup and what a person actually does next.

---

## 1. THE RAIL LIED ABOUT THE ALLOWANCE

`loadAccount` had **exactly one call site**, in the boot list. It repainted on activation and on
sign-out and **not after an organize run**. Measured: organize 100 files through the app, and the
rail still read *"700 of 1,000 left"* while the server said 600.

⚠ **This is the one number `DECISIONS.md` D16 §5 permits to exist**, and it justified the
Apply-time refusal precisely on the grounds that *"the number was never hidden, it was simply
never pushed"*. **A number that is wrong immediately after the only action that changes it is
worse than one that is absent** - it is not a stale reading, it is a contradiction of the sentence
the user is about to be refused with.

**The fix**: `loadAccount()` at the end of each run, in `after`, where the outcome card is already
on screen. Not on a timer, not live - D6 §3 forbids a countdown and a rail that ticks during a run
is one.

**Unconditional within those two commands rather than gated on "did it write anything".** The gate
would need a second definition of what the cap charges for, and there already is one:
`allowance.FILES_WRITTEN_STATUSES`, which differs **deliberately** from both
`_ORGANIZED_STATUSES` (the `organized` count the browser can see) and
`organizer._BYTES_WRITTEN_STATUSES`. Re-deriving it in JavaScript is how the two drift. A run that
wrote nothing repaints the same number: one GET, no lie.

### ⚠ WHY NO EXISTING TEST COULD SEE IT, AND WHAT THE GUARD DOES DIFFERENTLY

**Every browser test in this project opens the app and then asserts.** Each one therefore reads
the rail exactly once, at boot, when it is correct by construction. A rail that never repainted at
all passed the entire lane, because the lane never asked it to.

`tests/e2e/test_the_rail_repaints_after_a_run_that_spent_allowance.py` differs in one word:
**afterwards**. The page is opened once, the allowance read, a real organize driven through the
real UI, and the allowance read **again from the same document** - `_reload` is deliberately not
imported, because reloading is what hides the defect. The precedent is the sign-out test in
`test_the_account_slot_draws_every_licence_state.py`, whose own comment says why: *"a version that
signed out correctly and left the rail describing a signed-in user would pass every other test in
this file."*

Three assertions, separable on purpose:

* the number **moved** - the defect;
* it moved **to what the server says**, built from `licence_notice` the way
  `service/account._summary` builds it, so a reworded allowance line moves the test with it;
* it did **not** move *during* the run - which is what refuses a countdown, and what a test of the
  first two alone would let through.

The second door, `/api/ingest/run`, is guarded in `make check` instead
(`test_every_run_that_spends_allowance_repaints_the_rail.py`) - a minute of browser time for the
same assertion is not worth it. ⚠ **That guard does not list the doors: it parses
`service/organize.py` for what calls `record_files_written`, follows one hop, and maps the result
through `server.py`'s route table.** A third spending door fails it rather than shipping a stale
rail.

---

## 2. THE FIRST THING A PERSON TYPED WAS AN ERROR

Bare `truestill` reached argparse:

```
usage: truestill [-h] [--version]
                 {organize,ingest,drives,repoint-sources,undo-organize,restore,where,analyze,...}
truestill: error: the following arguments are required: command
```

Twenty-three subcommands wrapped onto one line, in declaration order, with no suggestion of where
to start. `README.md` has always said *"Start with `analyze`"*. The product said nothing.

**The shape is clig.dev's "concise help text"** - *"when `myapp` requires arguments to function,
and is run with no arguments, display concise help text"*, whose four named parts are: what the
program does, one or two example invocations, the flags unless there are many, and how to reach
the full help. The flags are the part deliberately dropped: 23 commands carry their own, and
repeating any here is a second place to keep them correct.

**The count is asked of the parser**, never written into the string - a literal would be wrong the
first time anybody added a subcommand, and wrong quietly.

### THE EXIT CODE AND THE STREAM, MEASURED RATHER THAN PREFERRED

There is no convention. Measured 2026-09-16 on this machine: bare `git` exits **1**, `npm` **1**,
`uv` **2**, `docker` **0**, `gh` **0**. `git` and `npm` both print to **stdout**.

So: **stdout**, because it is what the person asked to see rather than a complaint about what they
typed - and **exit 2, unchanged**, because there is no different action for a caller to take. `2`
is already this CLI's *"usage or validation error"*, a bare invocation is the plainest one there
is, and `0` would make `truestill && echo done` print `done` after doing nothing. Not a tenth exit
family; argparse's own value, kept.

**Ahead of `parse_args`**, because the subparsers are `required=True` and nothing downstream runs.
Gating on the empty list alone leaves every other argparse path exactly as it was, which is the
point: a first screen built by making the subparsers *optional* would swallow a **mistyped**
command into the same friendly page, turning a typo into silence.

### THE GUARD RUNS THE SCREEN RATHER THAN READING IT

A first screen is a promise made in prose, and prose is where this repo's defects live. A screen
recommending a command that had been renamed, or describing one that does something else now,
would read perfectly and be a lie. So
`test_the_first_screen_only_promises_what_the_product_does.py` takes every invocation apart:

* the verb is checked against the **parser**, not a list;
* `truestill-app` is checked against the `[project.scripts]` entry that actually installs it;
* `analyze FOLDER` is **run**, and the folder is byte-compared before and after - *"reads your
  files and changes none of them"*;
* `organize FOLDER DESTINATION` is **run**, and the destination must not exist afterwards - the
  assertion is the destination, not the exit code, because a run that wrote the library and exited
  0 would satisfy a code check while making the promise false;
* `organize ... --apply` is **run**, and the originals are byte-compared - `--apply --move` would
  also fill the destination, and *"copies by default"* over a command that moved would be the
  worst sentence in the product.

⚠ **One guard was widened to make this possible, and the principle was already written down.**
`scripts/check_product_name.py` rule 3 says *"a subcommand after the name makes it an
invocation"*; its implementation knew about subcommands and not about flags, so
`truestill --help lists all 23 commands` read as lowercase prose. `truestill --version` was
already carried as an allow-list literal for the same reason, one shape narrower. The pattern now
accepts `truestill --<flag>`, with a test that a sentence with a dash in it is still flagged.

---

## 3. A PHOTO DATED 1899 WAS REFUSED IN SILENCE

```
  date sources (organized files):
      rejected_early               1
      rejected_future              1
      rejected_sentinel            1
  1 file(s) carried only a placeholder date (1904/1970 epoch zero); ...
  1 file(s) claimed a capture date in the future; ...
```

A token for the 1899 file and **no sentence**, beside two siblings that each have one.

⚠ **AND IT WAS WORSE IN THE IMPORT REPORT.** `TAKEOUT RESCUE REPORT`'s date rows are
unconditional and `still undated` counts `DateSource.NONE` alone, so a pre-1900 refusal appeared
in `kept` and in **no date row at all** - absent rather than merely unexplained. Found by the
census, not by the finding as handed over.

### THE DEFERRAL THIS OVERTURNS, AND WHY ITS OWN TRIGGER IS NOT THE REASON

`models.py` recorded the refusal to build this: *"a run-summary counter would touch both
front-ends and `app.js` for a class measured at **0 of 895** real tag readings"*, with the trigger
*"one line to add the day a real library shows one."*

⚠ **THAT TRIGGER HAS STILL NOT FIRED.** Re-measured over `tests/golden/input-dates.tsv`, 7,790
files off one real machine:

```
  6488  exif        20  inferred_local       3  rejected_future
  1262  none        17  filename             0  rejected_early
                                             0  rejected_sentinel
```

The 1899 file that produced this finding was **manufactured**, in a hostile corpus.

**But the rarity argument was never sound, and the same census shows why**: `REJECTED_SENTINEL`
measures zero on that library too, and it has a counter and a sentence. Applied evenly, the
argument would have taken the placeholder disclosure away.

**What decided it is not frequency.** The run summary prints one line per stored `date_source`, so
the moment one of these exists the user already reads `rejected_early 1`. Rarity is an argument
about how often a person meets that word - never about whether the sentence is owed when they do.

### THE CENSUS, DERIVED RATHER THAN LISTED

The class is *every `DateSource` that means a date was found and refused* - `REJECTED_*` - read
off the enum, because a hand-written list is a list nobody prunes and the next refusal added is
exactly the one that would be left off it.

What the census found besides the 1899 case:

* `date_explain._EXPLANATIONS` covers all ten `DateSource` members **and nothing pinned that**.
  `REJECTED_FUTURE` sat in that hole once and fell back to *"Not recorded"* - telling a user their
  date was never noted, about a date the product had refused. Pinned now, in both directions: every
  member has its own entry, and an unknown string from a newer build still falls back rather than
  raising.
* `drive_unwritable._DRIVE_WORDS` and `_FOLDER_WORDS` cover **five of six** `Unwritable` members.
  `OTHER` is absent **deliberately**: both readers are `.get(...) or error.strerror`, so an
  unclassified errno falls through to the operating system's own message, which says more than a
  generic sentence could. Named in the test so nobody "fixes" it.
* Every other enum-to-prose table in core is complete - `_STATUS_LABELS` 10/10,
  `_UNREADABLE_LABELS` and `_UNREADABLE_REMEDIES` 5/5, `_FOLDER_SKIP_*` 2/2, `_UNCOMPARED_*` 2/2,
  `selfcheck._SEVERITY` and `_MARKS` 5/5.

### BOTH SURFACES, ONE COMMIT

`(aku)`'s precedent. A refusal disclosed in the terminal and silent in the browser is a catalog
that means different things depending on which window the user had open - so `DateQuality` gained
the counter, both CLI reports gained a row, both app payloads gained the field, and
`preview.tsx` gained the fourth note. `openapi.json` and `api.d.ts` were regenerated from the
TypedDicts; the frozen contract oracle is untouched.

⚠ **The app half is asserted from SOURCE and that is stated as a limit**: nothing in `make check`
type-checks the island, and no browser test renders a 1899 file. The pairing is derived from
`DateQuality`'s own fields, so the next refusal fails the assertion until the island learns to say
it - and the assertion is on the **branch**, `if (s.<field>) {`, not on a mention of the field,
because a mutation that changed the guard to `if (false)` survived the first draft.

---

## WHAT THE VACUITY CHECK FOUND

19 mutations, 19 caught - **three only after a survivor exposed a real gap**:

| survivor | why it survived |
|---|---|
| the rail repainted on a `setInterval` | the timer test matched `setInterval\([^)]*\)`, which stops at the arrow function's own `()` and never reaches the call. Fixed to a fixed-width window |
| the island's fourth note behind `if (false)` | the count was still interpolated inside a block that no longer ran, so a search for the field name passed |
| the payload dropping `early_rejected` | **the whole `truestill-app` suite passes with it gone.** Not a gap in this work - the finding is that the app's own tests never asserted the payload's keys, and the census test is now what does |
