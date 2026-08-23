# (agf) A FENCED `python` BLOCK IN A DOCUMENT IS A QUOTATION TO A READER AND AN INPUT TO A FORMATTER.

*Body of entry `(agf)`. **SHIPPED 2026-08-23.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(agf)** Shipped 2026-08-23. ⚠ **This entry was written after three files already cited the
  letter** - `pyproject.toml`, `test_the_formatter_is_pinned_behind_the_target.py` and `age.md` -
  and before it existed those citations resolved to nothing. `BACKLOG.md`'s *Item letters* section
  warns about exactly that: *"nothing recorded which letters were spoken for."* Recorded here
  rather than quietly fixed, because a letter cited by working code and filed nowhere is the
  drift, not the untidiness.

  ## What happened

  `(age)` quoted one line of `filesystem.py`:

  ```
  free_bytes=need if free is None else free,
  ```

  a keyword argument inside a call. **ruff 0.16 formats Python inside Markdown.** It read the
  fenced block as standalone code and rewrote it to:

  ```
  free_bytes = (need if free is None else free,)
  ```

  a **tuple assignment that appears nowhere in the file**. `make check` did it, between writing
  the entry and committing it - in the entry whose entire subject is a value being silently
  transformed one line after it was got right.

  ## 🔑 THERE IS NO TELL

  A misquotation produced by a formatter is syntactically perfect, stylistically consistent with
  every other block in the file, and passes every gate - **because the gate is what produced it.**
  Nothing goes red. Nothing appears in a diff anyone reviews, because the diff *is* the change.

  ## IT IS NOT ONLY FRAGMENTS, WHICH IS WHAT DECIDED THE REMEDY

  A whole valid statement is normalised too: `{'a': 1}` becomes `{"a": 1}`, doubled spaces
  collapse. So **any** block quoting source written in a style other than the formatter's is
  misquoted, less visibly. A rule about *what may be quoted* would therefore have been the wrong
  shape - the exposed set is every block, not the ones that look risky.

  ## THE REMEDY, MEASURED BEFORE IT WAS CHOSEN

  `[tool.ruff.format] exclude = ["*.md"]`. A config line rather than a practice, per §4's
  twenty-seventh member. Three things were measured first:

  | question | answer |
  |---|---|
  | which fence languages does ruff own? | `python`, `py`, `python3` - **yes**; `text`, `sh`, `console`, bare - **no** |
  | does excluding cost diagnostics? | **No.** An *unparseable* fragment is silently skipped, not reported - so ruff offers no signal over a document and rewrites only what parses, which is exactly the set where the rewrite is wrong |
  | is a per-file `exclude` enough? | Yes, under path discovery. An explicitly-passed file bypasses excludes, which is why the first test of this looked like a failure |

  ⚠ **A `text` fence is the answer where a block must stay in a document a formatter does own** -
  worth knowing, since the config here solves it repo-wide but the next project may not have one.

  ## ⚠ THE RECORDS ARE THE REAL EXPOSURE

  `docs/*research*.md` are never rewritten - this repo states it twice and calls a rewritten record
  *"not a record"*. A formatter reaching inside one breaks that rule **through a tool nobody would
  think to check**, and `trip-grouping-research.md` carries six such blocks.

  ## THE SWEEP, COUNTED MECHANICALLY

  Every fenced `python` block in every tracked document was extracted, dedented and run through
  the formatter in isolation. **The measure is "would the formatter change it", not "is it a
  fragment"** - a fragment that happens to match ruff's output is safe, and a whole statement that
  does not is exposed, so the operative question is the diff.

  | where | fences | formatter would rewrite |
  |---|---:|---:|
  | backlog bodies | 5 | **1** (`age.md:23` - the one found) |
  | records (`docs/*research*.md`) | 6 | 0 |
  | canon and other docs | 2 | 0 |

  **Thirteen blocks, one exposed, and it is the one already repaired.** No evidence any other was
  ever silently rewritten: no formatting commit in recent history touched a `.md`. The exposure
  was caught on its first occurrence.

  ## GUARDS

  Two, because asserting the config key alone would keep passing if ruff stopped formatting
  Markdown and the line would become cargo:

  - `test_the_formatter_does_not_own_fenced_blocks_in_documents` reads the setting.
  - `test_the_exclusion_is_load_bearing_rather_than_decorative` runs the formatter over a
    throwaway document **without** it and requires it to bite - so the day the behaviour goes
    away, that test fails and the line is retired on evidence rather than kept forever.

  ⚠ **And the existing `test_no_invocation_escapes_the_pin` caught the new test's own
  `["ruff", "format", "."]` argv for not pinning `--target-version`** - a guard written for this
  file finding a violation introduced into this file, on the same commit.

  ## §4

  The **sixty-fifth member**. Every other member is about a claim that was wrong when written, or
  that expired. This is about one that was **correct when written and was then altered by a
  tool**, with no diff to review and nothing to go red.
