# (ace) THE MUTATION RESTORE RULE EXISTS, IS CORRECT, AND WAS VIOLATED TWICE IN ONE DAY - MAKE IT EXECUTABLE.

*Body of backlog entry `(ace)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

> ⚠ **PROVENANCE QUESTION, FILED 2026-08-15 AND NOT ANSWERED HERE.** The proposal below asks for
> `scripts/mutate.py`. **`scripts/mutate_once.py` exists and matches the description clause for
> clause** - it takes `(file, anchor, replacement, pytest args)`, asserts the anchor appears
> exactly once, holds the original bytes in memory, restores in a `finally`, and re-hashes
> afterwards. It is cited as built in `CLAUDE.md` and in `ENGINEERING_STANDARD.md` §4's fiftieth
> member. **So this entry may already be shipped under a different filename, and nothing says so.**
>
> The proposal's own wording is deliberately left as written - renaming a file inside a past
> proposal would misrepresent what was proposed. **Whether `(ace)` is closed is a provenance call
> for the maintainer**, and closing it means a `Closes (ace).` commit that moves it to
> `SHIPPED.md`, which is exactly what the hook and `test_closed_entries_leave_the_backlog` exist
> to require. Recorded here rather than acted on.

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
