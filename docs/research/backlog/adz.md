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
  - **What to do before the first tag**, and it is the actionable part: **audit every
    compatibility path for a stated condition** and give each one either a real condition or a
    removal. Known candidates, not a complete list: `LEGACY_MARKER_NAMES` (`.vaeon-drive.json`,
    read for ever with no horizon), and whatever `--db`, layout templates and the settings keys
    tolerate from older shapes.
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
