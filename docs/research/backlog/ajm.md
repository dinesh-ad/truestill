# (ajm) A BROWSER TEST MEASURES THE MACHINE'S TEMP PATH, NOT THE PRODUCT

*Body of backlog entry `(ajm)`, under **Internal / tooling**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

⚠ **AND IT IS NOW A GATE, NOT ONLY AN INSTRUMENT DEFECT (2026-09-03, P207, from `(ajx)`).**
It failed in **both** `-n auto` dispatches of the webkit half - `33802113061` and `33803207647` -
on a path the worker layout made longer:

```
AssertionError: the path is still being ellipsised with room to spare:
'/tmp/pytest-of-runner/pytest-0/popen-gw2/test_the_catalog_path_fit…catalog.sqlite'
```

`pytest-xdist` inserts a `popen-gwN` component into `tmp_path`, which is a **second trigger for
the same root cause** this entry already names: the test asserts a path shows whole and does not
control the path's length. The first trigger was a machine with a `/data` volume (95 chars against
CI's 77); this one is the runner's own parallelism.

🔑 **So any future attempt to parallelise the browser lane has to fix this first**, whatever the
reason for trying it - a lane that goes red on its own worker layout cannot measure anything, and
`(ait)`/`(aiu)`'s ruling that instrument defects outrank product findings is exactly why. This
does not change the diagnosis below or the fix; it changes what depends on it.

Filed 2026-09-01 (P173). **An instrument defect, and it is diagnosed rather than merely
observed** - it was reported as "undiagnosed, costs 26 minutes to learn nothing" and one run
settled it.

## MEASURED

`tests/e2e/test_narrow_top_bar.py::test_the_catalog_path_fits_rather_than_truncating_to_nothing`
fails locally on **both** browsers and passes in CI. Reproduced at `2ba5cdb` - the commit CI's
nightly passed the same morning - with all working changes stashed, so it is not any of P169-P172.

```
AssertionError: the path is still being ellipsised with room to spare:
'/data/tmp/truestill/pytest-of-<user>/pytest-1118/test_the_catalog_pat…catalog.sqlite'
```

## 🔑 THE MECHANISM, AND THE REPO DOCUMENTS IT ITSELF

The test asserts a catalog path is shown whole in a 720px top bar. **Its own docstring says
*"With room to spare it must show the path whole"* - and it does not control how much room there
is**, because it does not control the path's length.

`suite_scratch.scratch_root()` decides that, and its docstring states the split outright:

> ``None`` is the CI answer and is not a failure: no runner has a ``/data``, and an absolute path
> that could not be declined would fail all three ``check`` lanes.

So `pytest`'s `tmp_path` is:

| | root | example | length |
|---|---|---|---|
| this machine (`/data` exists) | `/data/tmp/truestill` | `/data/tmp/truestill/pytest-of-<user>/pytest-1118/test_the_catalog_path_fits_rat0/catalog.sqlite` | **95** (counted before redaction) |
| CI (no `/data`) | OS default | `/tmp/pytest-of-runner/pytest-0/test_the_catalog_path_fits_rat0/catalog.sqlite` | **77** |

**Eighteen characters, and that is the entire difference.** ⚠ **It is NOT flakiness** - it is a
deterministic dependency on whether the machine has a `/data` volume, which is exactly the
condition `suite_scratch` exists to branch on.

## WHY IT RANKS WHERE IT DOES

`(ait)`/`(aiu)` ruled that **instrument defects outrank product findings, because a wrong answer
key corrupts every measurement taken against it** - and they lead their group for that reason.
This is the same class one level out: not a wrong answer *about* the product, but a lane that
reports red on a machine where the product is fine.

🔑 **The cost is that the lane stops being run.** `make e2e` is ~26 minutes serial across two
browsers. A lane that always ends in two known-irrelevant failures is a lane whose next *real*
failure is indistinguishable from its background noise - `ENGINEERING_STANDARD.md` §4's
cry-wolf argument, applied to a test rather than to a guard.

⚠ **Two instruments accumulating unowned was the worry; ONE is real.** The other -
`cli._print_capped`'s distinct-reason count - **was investigated and is CORRECT**; see the null in
`(ajk)`. **The pattern was the accumulation, and half of it dissolved on inspection**, which is
itself the argument for diagnosing rather than filing.

## ⚠ ONE MEASURED ANSWER ON WHETHER THE LANE EARNS ITS 26 MINUTES - `d7ba4d8`, 2026-09-01

**Recorded here rather than in the commit, because the commit is pushed and this is the entry
that owns the lane's cost.** It is one data point, not a ruling.

`d7ba4d8` changed four screen surfaces and the lane was dispatched on it:

```
983 passed, 3 skipped in 1280.82s (0:21:20)
```

**It found nothing, and four mutants had already been caught by `pytest` in seconds** - including
both surface-level ones (the unconditional literal returning, and the strip ignoring the verdict),
which is precisely the proof `e6ef82c`'s two survivors demanded. 🔑 **So the lane confirmed a
renderer that is being deleted.** `app.js` goes with the React migration; what survives that
commit is `independence_note` and `independence` **on the payload**, and those are pinned by an
HTTP test inside `make check`.

**The honest verdict: not warranted, and the maintainer said so unprompted after asking for it.**
The rule in `CLAUDE.md` - *"the test of 'reaches a screen' is whether the change could make a
screen STOP SHOWING SOMETHING"* - is satisfied by this diff and still points the wrong way here,
because the thing at risk was reachable from pytest. ⚠ **The sharper question is not "does it
reach a screen" but "can pytest see the thing that could break?"** For a renderer reading a payload
field, it can - `test_the_rearrange_card_name.py`'s precedent is exactly that, and this commit used
it. For layout, focus, or anything the browser computes, it cannot.

⚠ **THIS IS ONE RUN AND IT MUST NOT BE READ AS "SKIP THE LANE".** `(aer)` is the counter-example
in the same file's history: one 28-minute run returned 6 red on a wording collision. **The
distinguisher this data point offers is what KIND of screen change it was** - a field rendered as
text, versus wording or layout the browser decides. Two points do not make a rule; the next
person weighing it now has one measured on each side.

## THE FIX SHAPE, NOT RULED

1. **Make the test control its own input** - render a fixed-length path, or assert on a path the
   test constructs, so the subject is the fit logic rather than the runner's filesystem. This is
   the root cause: the test asserts about width and takes its width from the environment.
2. **Pin `basetemp`** for the browser lane so both environments agree. Cheaper, and it makes the
   lane agree by making the machine agree - which leaves the test still measuring the environment,
   just a fixed one.

⚠ **(1) is the root cause and (2) is a workaround that would pass.** The test's docstring already
names its real subject - *"the fit logic measures and middle-ellipsises"* - and a fit test whose
input length is incidental is not testing fit.

## WHAT IS NOT ESTABLISHED

- **Whether any other `tests/e2e/` test has the same dependency.** One was found because it
  failed; nothing has swept the lane for tests whose assertions vary with path length.
- **Whether CI would fail if a runner ever had `/data`.** The branch is untested in that
  direction.

## RELATED

`(ait)`, `(aiu)` (the instrument-defects-rank-first ruling), `(ajk)` (the null on the other
instrument), `suite_scratch.py` (the split, documented in its own docstring).
