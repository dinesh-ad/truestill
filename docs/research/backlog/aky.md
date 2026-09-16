# (aky) FOUR PAYLOAD FIELDS NOTHING PROTECTS, AND ALL FOUR ARE DRAWN ON A SCREEN.

*Body of backlog entry `(aky)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

**Recorded 2026-09-16 with no work attached**, so the next person does not rediscover them.
Nothing here is fixed.

## HOW THEY WERE FOUND, AND WHY THE NUMBER IS FOUR RATHER THAN NINETY-SIX

A mutation deleted `"early_rejected": quality.early_rejected,` from the dict literal that builds
the organize payload. **The whole `packages/truestill-app` pytest suite stayed green.** That was
reported as *"the app suite asserts nothing about what the wire carries"*, and the census that
followed corrected it in both directions.

⚠ **THE PREMISE WAS TWO MUTATIONS, NOT ONE, AND THEY HAVE OPPOSITE OUTCOMES.**

| mutation | what catches it |
|---|---|
| delete the key from the **TypedDict** | **788 of 788.** `test_the_committed_spec_is_current.py:test_the_committed_spec_equals_what_the_tree_emits` regenerates `openapi.json` from the TypedDicts and refuses any difference |
| delete the line from the **dict literal** | **752 of 788 by mypy**, which `make check` runs. Nothing by pytest |

So the exposure is not 788 fields and not the 96 that no assertion reads. It is the intersection
of **`NotRequired`** - where mypy is blind, because an absent optional key is legal - with **never
read inside an assert anywhere in the repo**. Derived, not sampled:

```sh
# 140 schemas, 788 (schema, field) pairs, 36 of them NotRequired
python3 -c "import json;d=json.load(open('packages/truestill-app/openapi.json'))['components']['schemas'];\
print(sum(1 for s in d.values() for f in (s.get('properties') or {}) if f not in set(s.get('required') or [])))"
```

Of those 36, **four names are read by no assertion in any test tree** - `packages/*/tests` and
`tests/e2e` alike. ⚠ `tests/e2e` adds **zero** coverage here on every metric: Playwright asserts
rendered text, and cannot tell a missing key from a zero value.

## THE FOUR, AND THE MUTATION THAT PROVES EACH

Each mutation is the deletion of one line. `scripts/mutate_once.py` exits **1** when the mutation
survives, which is the expected result for all four today; a fix is proved when it exits **0**.

| field | written at | drawn at | what a user stops seeing |
|---|---|---|---|
| `leftover_empty_folders` | `service/organize.py:_done_summary`, `service/migrate.py:migration_apply.target` | `app.js:startOrganizeRun`, `completion.tsx:288` | **the offer to tidy up the empty folders a move left behind.** The card simply stops appearing |
| `second_location` | `service/verify.py:verify_run.target` | `app.js:verifyJob` | **the "This drive answers in two places" warning** - the banner that says one drive id is mounted twice |
| `heic_perceptual_skipped` | `service/organize.py:_summarize` | `preview.tsx:367` | *"N HEIC files will be backed up, but near-duplicate detection was skipped for them"* |
| `groups` | `service/migrate.py:migration_apply.target` | `app.js:reviewResultCards`, `preview.tsx:433` | **the per-group breakdown of an applied migration** |

```sh
# one example; the other three are the same shape against their own line
printf '%s' '        done["leftover_empty_folders"] = leftover
' > /tmp/old.txt
printf '' > /tmp/new.txt
uv run python scripts/mutate_once.py \
  --file packages/truestill-app/src/truestill_app/service/organize.py \
  --old-file /tmp/old.txt --new-file /tmp/new.txt \
  --label "the cleanup offer stops being sent" \
  -- uv run pytest packages/truestill-app tests/e2e -q
```

⚠ **`second_location` already has the hook for its own test and nobody wrote the test.**
`app.js:verifyJob` renders `data-testid="verify-second-location"`, and that string appears in **no test
file**. It is one of **15 of the 63** static `data-testid` values in the UI that nothing asserts -
a testid exists for exactly one reason, so an orphan is an assertion somebody intended and did not
write.

## ⚠ THE ROOT CAUSE IS A GUARD THAT PROVES THE WRONG HALF

This repository already has a sophisticated dead-field guard:
`packages/truestill-app/tests/test_no_thirty_fifth_dead_payload_key.py` asserts that **every
declared key is read by a surface**, with 34 `DEAD` entries maintained by hand.

`early_rejected` **passes it**, because `preview.tsx:80` reads it.

**Both ends are read statically and never connected through a running payload.** The guard proves
a surface would render the field if it arrived; nothing proves the server still sends it.
`test_job_summaries_are_read_where_they_are_delivered.py` has the same shape and is scoped to
`runJob` blocks in `app.js` only - its `UNBOUND` list at `:72-91` excludes the organize and ingest
routes, which is exactly where the mutation landed.

**The React migration widened it.** 14 fields now have their only reader in a `.tsx` file, which
no Python test imports and which the browser lane exercises only as rendered text.

## WHAT IS NOT PROPOSED HERE

- **Whether the fix is four tests or one mechanism.** Four assertions close these four and leave
  the class open; a guard that compares a *produced* payload's key set against its TypedDict would
  close the class and is a new artifact that has to earn itself under `(ago)`'s bar. Not decided.
- **Whether `NotRequired` is right for all 36.** `leftover_empty_folders` is optional because it
  appears only for move and in-place runs, which is a real reason. Some of the other 35 may be
  optional by habit, and a field that is always sent should be `Required` - where mypy already
  guards it for free. Unaudited.
- ⚠ **The four are a floor, not a ceiling.** The scan is name-level: a name read in an assert for
  schema X counts as protected for schema Y sharing it, which is the same limitation
  `test_job_summaries_are_read_where_they_are_delivered.py:3-7` records about the repo's own guard.
  And it is static - none of the four has been confirmed by an actual mutation run.
