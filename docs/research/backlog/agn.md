# (agn) THE PUSH GATE JUDGED A COMMIT THE REMOTE MAY NOT HAVE HAD.

*Body of entry `(agn)`. **SHIPPED 2026-08-23.** The index is now [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

> ## ✅ SHIPPED 2026-08-23
>
> The two obligations `ENGINEERING_STANDARD.md` §2 carries are now keyed the way they actually
> work: **contention** by branch, **outcome** by the remote tip git hands over on stdin.

## ⚠ FIRST, A CORRECTION TO MY OWN REPORT

I told the maintainer the gate *"printed 'the last push's run is finished and green' while
origin/main was the RED 4051914 - it was reading f992053's run"*, and offered it as evidence the
override may have been inert. **That was wrong, and the maintainer restated it as a hypothesis to
be verified, which is what caught it.**

What actually happened: `TRUESTILL_PUSH_ANYWAY=1` **fired**, short-circuiting at the top of
`main()` before any lookup. Its message went to stderr, and **pre-commit suppresses a passing
hook's output**, so the only thing on screen was the hook's *name* - `the last push's run is
finished and green` - followed by `Passed`. The gate judged nothing and appeared to certify
everything.

🔑 **The name was a claim, and pre-commit renders any passing hook as `<name> ... Passed`.** So an
overridden gate, a gate that failed open, and a gate that genuinely verified a green tip all
printed the same sentence. The name is now a subject - `push gate (the tip you are pushing onto)` -
and the override says what it bypassed.

## The real defect: two obligations, one key

`ENGINEERING_STANDARD.md` §2's *"a pending result outranks a ready batch"* carries **contention**
(do not cancel a run in flight) and **outcome** (do not build on a red tip). The module separated
them **in prose** and answered both from one sha derived by `git rev-parse @{upstream}`, then
scanned the fifteen most recent runs and sieved them locally.

| | the question | the right key | what it did |
|---|---|---|---|
| contention | is a run in flight on this **branch**? | branch + `--event push` | asked about one sha |
| outcome | is **this commit** red? | the remote tip, from stdin | a recency window, locally sieved |

**Three consequences, each reachable:**

* `@{upstream}` is the **local remote-tracking cache**. Somebody else's push, or simply not having
  fetched, made it ask about a commit the remote no longer had.
* A red tip whose run had aged out of a fifteen-run window read as *no evidence of a failure*.
* A run in flight for a **different** sha on the branch was invisible, and the push cancelled it.

## Q71 - it never read stdin

`githooks(5)` specifies that `pre-push` receives `<local ref> SP <local sha1> SP <remote ref> SP
<remote sha1> LF` per ref on **stdin**. The remote tip is handed over; nothing needs inferring.
`scripts/check_push_gate.py` contained **no reference to `stdin` at all** - it used
`_upstream_sha()` (`git rev-parse @{upstream}`) at `:66-82`, called from `main()` at `:115`.

**Null result, reported:** `gh run list` has had `--commit SHA` all along, so the keyed query was
available and unused. This was not a missing capability.

## Q72 - a tip with no run is REFUSED

**Checked rather than assumed:** `ci.yml` has no `paths` filter on `push: branches: [main]`, so
every push to main creates a run. A tip with no run is therefore not the ordinary absence it was
treated as; it is a question the gate could not answer, and **unknown is not green** - `(afl)`'s
shape.

⚠ **This is deliberately distinct from failing open.** *Cannot ask* (no `gh`, no auth, API
unreachable) still passes with a warning, because a gate that blocks every push on a plane or a
fresh clone gets uninstalled and takes its real coverage with it. *Asked, and the answer is
nothing* refuses. `_gh` returns `None` for the first and `[]` for the second, and collapsing them
is how a gate starts reading absence as success.

## Q73 - the all-zeroes sha is handled

`githooks(5)` gives an all-zero sha for a ref that does not exist on that side: as the **remote**
sha it is a brand-new branch, as the **local** sha it is a deletion. Both skip. Without that,
Q72's fail-closed rule would refuse every first push forever - a trap built out of two correct
rules meeting.

## Q74 - the override was reachable, fired, and was silent

It short-circuits before any lookup, so it bypasses **both** halves. It was not inert; it was
invisible. It now names the tips it skipped the check on and says *"Nothing was verified"* -
because an escape hatch nobody can tell fired is worse than none.

## Q75 - every verdict names its subject

Refusals now carry the sha, the run id and the run URL. The person reading the line can check it,
which is the only reason this defect was caught at all: the message looked odd.

## Proof

⚠ **FIRST, THE HARNESS THIS ENTRY NEARLY SHIPPED, because the repo's own record stopped it.**
`test_push_gate_refuses_a_red_predecessor.py` already existed and its docstring records a measured
lesson: *"THE DECISION IS TESTED AT THE MODULE THAT MAKES IT, NOT THROUGH PATH STUBS ... Windows
does not honour a shebang, so `gh` was simply not found, the gate correctly failed open, and six
tests went red on a lane where the product was behaving exactly as designed."* **`(agn)`'s first
draft rebuilt exactly that** - a `#!/usr/bin/env python3` file named `gh` on `PATH` - and would
have gone red on the Windows lane for the recorded reason. The lesson held because it was written
down rather than remembered, and the new cases were merged into that file instead of shipping a
second one beside it.

**Two existing assertions changed, and both are named rather than buried**: a commit with no run
*"is not treated as a failure"* became a refusal (Q72's measurement), and the branch-with-no-
upstream case became the all-zeroes remote sha, which is what git actually hands over.

Seventeen tests. Seven mutations, all caught, three cry-wolf:

| # | mutation | direction |
|---|---|---|
| 1 | a recency window sieved locally, instead of a keyed query | defect |
| 2 | a missing run reads as green | ⚠ cry-wolf |
| 3 | contention stops being branch-keyed | defect |
| 4 | the gate refuses everything | ⚠ cry-wolf |
| 5 | the all-zeroes guard removed, so a first push refuses forever | defect |
| 6 | the override stops naming its subject | defect |
| 7 | contention drops `--event push`, so the nightly blocks a push | ⚠ cry-wolf |

⚠ **Mutation 1 survived TWICE, and the two reasons were different** - which is
`ENGINEERING_STANDARD.md` §4's sixty-sixth member paying for the fourth time.

1. **The test was too weak.** With two runs in the table a window and a keyed query agree; the
   defect only appears when the tip's run is *outside* the window. Fixed by a table of twenty-one.
2. **Then the mutant became invalid.** With the window, the tip's run is not found - and Q72's new
   fail-closed rule refuses on that, so *both* implementations refuse. **The keyed query is not
   load-bearing for the refusal; it is load-bearing for the refusal being TRUE.** The window
   version says *"NO CI run exists"* about a commit whose run exists and is red, sending the
   reader to look for the wrong thing. The assertion is now on the stated reason.

**And a defect in the test harness itself, worth recording**: the fake `gh` interpolated
`json.dumps(runs)` into Python source, so `"conclusion": null` became a `SyntaxError`, the stub
exited non-zero, and the gate's **fail-open path swallowed it**. A stub whose breakage is
indistinguishable from the condition under test is the worst kind, and a fail-open gate is exactly
where it hides.
