# (adz) A COMPATIBILITY PATH STATES ITS REMOVAL CONDITION WHEN IT IS WRITTEN.

*Body of backlog entry `(adz)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adz) A COMPATIBILITY PATH STATES ITS REMOVAL CONDITION WHEN IT IS WRITTEN.** Recorded
  2026-08-19, prompted by `(aae)` and closed out of `(adw)`. **A policy, not a defect** - what it
  fixes is the shape of a decision rather than a line of code.
  - **What `(aae)` did, and it is not a criticism of it.** It made the legacy
    `reports/catalog.sqlite` win when present, so an upgrade would not silently start writing to
    an empty catalog. That was right. What it never wrote down was **when it would stop**: no end
    date, no version, no condition. **The promise was open-ended by omission**, which is a
    different thing from a promise anyone decided to make for ever.
  - 🔑 **THE RULE.** Any compatibility path - a legacy location, a legacy filename, a tolerated
    old format - **names its removal condition in the same commit that introduces it.** Not a
    warning, not a schedule: a *condition*, in the code beside the thing it keeps alive.

  ## 🔑 STANDING RULE UNTIL THE FIRST RELEASE TAG: THERE ARE NO USERS

  Ruled by the maintainer 2026-08-19, and it **sharpens the condition below rather than adding to
  it**. Every existing catalog, drive and install is the maintainer's own - `release.yml` fires on
  `tags: ["v*"]`, no such tag exists, and its runs were dispatches with `dry_run` defaulting to
  true. So a compatibility path, a legacy fallback, or a migration for an old layout is **cost with
  no beneficiary**.

  **Before the first tag the removal condition is "delete it now"** - not *"when the maintainer
  decides"*, which is what this entry said yesterday and which was already too soft. **After the
  tag the release-anchored rules below apply**, and the window closes for good.

  ⚠ **This is a rule about WHO, not about whether the code works.** Every path in the list is
  correct, tested and well-reasoned; that is exactly why they survive review. The question this
  rule asks is different: *who is on the other end of it* - and until a tag exists the answer is
  nobody, so the answer to *"should it stay"* is no.

  **Two things it does not license**, because both were checked before the rule was written:
  - **Deleting a compatibility path is not deleting the data it reaches.** `(adw)` retired the
    legacy catalog lookup only **after** migrating the maintainer's live 6.37 MB catalog and
    verifying the copy byte-identical. The rule removes support, never files.
  - **Not every legacy-looking thing is a compatibility path.** A migration chain also serves
    *future* upgrades, and a deprecated column kept as a fallback is a design choice about
    today's data. The audit below separates them rather than counting keywords.
  - ⚠ **THE CONDITION'S PERMITTED FORM CHANGES AT THE FIRST TAG, AND THAT IS THE POINT.**
    - **Before the first `v*` tag**: *"when the maintainer decides"* is a legitimate condition.
      Nothing has been published, so the population who can depend on it is enumerable, and
      `(adw)` is the worked example - a path retired outright because its population was one.
    - **After the first `v*` tag**: it must be a **version**. Once something is published the
      population stops being knowable, and every deprecation policy in the industry becomes
      release-anchored because that is the only anchor left - Kubernetes on an API version
      increment, GitLab three milestones before a major, OpenSSL five years in an LTS, Docker
      warn-then-remove across releases.
    - **So the window for free removal closes at the first tag.** Anything still carrying
      *"when the maintainer decides"* on that day has silently become a permanent promise, which
      is exactly `(aae)`'s failure repeated with more users.
  ## THE AUDIT, 2026-08-19 - what exists only for backward compatibility

  Swept for compatibility vocabulary across `packages/*/src` and then checked **concretely**, not
  by keyword. **Reported, not removed** - the maintainer asked to see the list first.

  | # | what | verdict |
  |---|---|---|
  | 1 | **`LEGACY_MARKER_NAMES = (".vaeon-drive.json",)`** (`drive.py:LEGACY_MARKER_NAMES`) - pre-rename drive markers, read for ever, never written | ⚠ **The clearest candidate.** No horizon was ever stated. `/home/dinesh/TruestillLibrary/Output` carries `.truestill-drive.json` only. ⚠ **NOT FULLY CHECKABLE**: one registered drive lives under a **fenced** mount and cannot be stat'd, so *"no `.vaeon` marker exists"* is **unverified** - the check would have to be run by the maintainer, or the drive re-registered. |
  | 2 | **`CatalogChoiceReason = Literal["override", "legacy", "default"]`** (`app_paths.py:CatalogChoiceReason`) | ✅ **Already dead and I left it.** `grep 'reason="legacy"'` finds **no producer** since `(adw)`. A member no branch can return. Pure removal, zero risk. |
  | 3 | **`LEGACY_CATALOG_PATH`** (`app_paths.py:LEGACY_CATALOG_PATH`) - now `catalog --move`'s source alone | ⚠ **Live for exactly one file**: the maintainer's `reports/catalog.sqlite`, already migrated and byte-identical at the standard location. Once that file is deleted, this and the `--move` flag lose their only subject. **A decision about the file, not about the code.** |
  | 4 | **`_MIGRATIONS`, 18 steps, v2 -> v19** | ❌ **NOT a compatibility path in the sense of this rule, and counting it as one would be the mistake.** Both catalogs in existence are **v19**, so steps 2-19 serve nobody *today* - but the chain is also the mechanism by which a **v20** will reach a v19 catalog. What is dead is the *history*, not the machinery. Collapsing v1->v19 into a single baseline is a real option and a separate piece of work with real risk. |
  | 5 | **`downgrade_v12_to_v11`** (`catalog.py`) | ➖ Not compatibility - it exists to *prove* v12 is reversible, has no production caller, and is named as testing-only in its own docstring. Keep. |
  | 6 | **`files.relative`, deprecated** | ➖ Not a compatibility path. Kept as a **name fallback** where `original_name` is NULL, feeding the custody strip's counts. That is a statement about today's rows. Keep. |
  | 7 | **`files.copy_sha256`** | ➖ Was deprecated, **un-deprecated 2026-07-31** with the reasoning written in place. Not a candidate; the entry explicitly warns against re-deprecating it from the old argument. |

  **So the removable set is small and unglamorous: (2) outright, (1) once the fenced drive can be
  checked, (3) once the maintainer deletes a file they have already copied.** Nothing else in the
  tree is cost with no beneficiary - which is worth recording, because the rule reads as though it
  should find a lot and it does not.

  - **What to do before the first tag**, and it is the actionable part: **audit every
    compatibility path for a stated condition** and give each one either a real condition or a
    removal. The table above is that audit as of 2026-08-19; anything added after it inherits the
    rule at the moment it is written.
  - 🔑 **AND RECORD WHAT WAS CONSIDERED AND REJECTED**, which is Git's other habit worth stealing:
    its `BreakingChanges` document lists deprecations it decided **not** to make, with the reason,
    so they are not re-litigated. A retirement that was weighed and declined is as much a decision
    as one that shipped, and it is the half that gets argued twice. **First entry for that list:
    ccache's legacy `$HOME/.ccache`, kept permanently and deliberately** - the reason being that
    it cannot enumerate who holds one, which is the condition that will one day be true here too.
  ## THE REJECTED LIST - deprecations and tools weighed and declined, so they are not re-argued

  Git's `BreakingChanges` keeps one of these and it is the half that saves the most time: a
  decision **not** to change something is a decision, and it is the one that gets argued twice
  because nothing records it.

  - ❌ **ccache's legacy `$HOME/.ccache`, kept permanently and deliberately.** The first entry, and
    the reason is the condition that will one day be true here: it cannot enumerate who holds one.
    See `(adw)`.
  - ❌ **`pytest-durations` / `pytest-extra-durations` (2026-08-19).** They are real and they do
    more than the built-in - fixture time separated from test time, xdist-aware. Declined against
    `ENGINEERING_STANDARD.md` §4's dependency bar: `pytest --durations=N` is built in, needs no
    dependency, and answers the question that was actually asked (*"which tests are slow"*). The
    plugins answer a question nobody has yet (*"is the cost in the fixture or the test"*), and the
    day someone does ask it, this entry is where to find that it was considered.
  - ❌ **A per-line timing display beside each test name (2026-08-19).** Asked for directly, and
    declined on a measurement rather than a preference: the suite runs under **`-n auto`**, so
    sixteen workers interleave and **wall clock beside a name is not that test's cost**. A number
    that looks like a duration and is not one is worse than no number - it would be read, trusted,
    and wrong. The slow *tail* is the answerable question, and `--durations` plus
    `scripts/flake_report.py --slowest` answers it.

  - **Not proposed here:** where the list lives (a document, a module docstring, a test that reads
    both), or whether a guard can enforce "every compatibility path names a condition". A guard
    would need a way to recognise one, and inventing that classification is a bigger question than
    the rule itself.
  - **Cross-references.** `(aae)` - the open-ended promise this generalises from, amended rather
    than rewritten. `(adw)` - the worked example, and the record of why free removal was available
    exactly once.
