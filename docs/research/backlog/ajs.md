# (ajs) AT NO LAYER OF THIS TOOLING DOES "THE CHECK DID NOT RUN" LOOK DIFFERENT FROM "THE CHECK PASSED".

*Body of backlog entry `(ajs)`, under **Internal / tooling**. The index is
[`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with
[`SHIPPED.md`](../../SHIPPED.md).*

- **(ajs) AT NO LAYER OF THIS TOOLING DOES "THE CHECK DID NOT RUN" LOOK DIFFERENT FROM "THE CHECK PASSED".**
  Filed 2026-09-02 (P189) from P188's census of the pipe-exit-code class.

## THE FINDING

`ENGINEERING_STANDARD.md` names both halves - the forty-third member, *a step that succeeded
while producing nothing*, and the forty-fourth, *a step that failed and had the failure thrown
away* - and says neither covers the other. The rule existed. What the tooling lacked was a
mechanism that applies it without an author remembering to. Every fix before this entry was a
hand-written floor after an instance: the push gate (`cb84aee`), the retention policy
(`57d1652`), the census guard (`2341b2c`), seven `ls-files` guards in one day (`e29c50e`), the
serving proof (`0193975`), the tsc gate (`be6415d`), and the chain that committed on red twice
(2026-08-13, recorded in the standard; 2026-09-02, `3a769b4`).

## THE LAYERS, AS MEASURED

| layer | what it reports | tells "did not run" from "passed"? |
|---|---|---|
| a shell pipeline | the last command's status | no - `make check \| tail` committed on red, twice |
| a command substitution | its output | no - `touched=$(git diff ...)` read "could not read" as "nothing changed" |
| PowerShell | the last native command's `$LASTEXITCODE`, and a native command piped to a cmdlet may set none | no, unless each call is checked |
| pre-commit | `Passed`, swallowing what a passing hook printed | no - `check_push_gate.py:main` had to ride a non-zero exit to be heard |
| the push gate | `return 0` when `gh` cannot answer at preflight; before P189, `None` on a later failure meant *no refusal* | at the preflight, by design; after it, now refuses |
| pytest | exit 5 for a run that collected nothing, **exit 0 for a file that collected nothing**; no collection hook, no `minversion` | whole-run granularity only |
| a guard's own scope | whatever its author asserted | 36 of 42 yes, 6 no - measured 2026-09-02 |
| CI | junit uploads warned on absence; nothing read the file for a count | no, until P189 |
| the commit body | a recorded local test count, when written | the only cross-layer tell, and it lapsed before `5a17b7c` |

## WHAT SHIPPED, EACH WITH A MUTATION PROOF

P188 (`40c4f86`, `b06584f`, `31d77ed`): floors on three unfloored guards; `mutation_matrix.py`
stops calling a broken run inert; two piped steps get `shell: bash`; the Windows self-check
compare can fail; a guard over both workflows. P189: the installer, uninstaller and ISCC calls
read their exit (`f5bd967`); "could not read" stops reading as "nothing there" in `make gate`,
`check_entry_closure.py`, `normalize_dashes.py` and the `.deb` check (`95fac8c`); the push gate
retries a blip and refuses an outage after the preflight (`68981e7`); `scripts/check_junit_floor.py`
reads both junit files for a count and both uploads error on absence.

## WHAT IS LEFT

- The six unfloored guards are three now (`test_every_entry_point_refuses_an_unusable_catalog.py`,
  `test_the_screens_do_not_call_one_device_redundant.py`,
  `test_every_command_declares_whether_it_locks_a_drive.py`); each is protected by a positive
  assertion beside the scan, not by a declared floor.
- No fixture or plugin makes a scope floor the default. Whether one is worth its ceremony is
  `(ago)`'s question and is not ruled here.
- `Makefile` has no `SHELL`/`.SHELLFLAGS` prologue; nothing on a gating path pipes today.
- The commit-body test count is a practice, not a guard (`(ajk)`'s precedent).

## ONE DECISION FOR THE MAINTAINER - THE DEPTH-1 CHECKOUT

`actions/checkout` defaults to depth 1, so `test_closed_entries_leave_the_backlog.py` read one
commit of history in CI and passed over an empty set for as long as it ran there. It now skips
in CI with that reason. A full checkout (`fetch-depth: 0`) makes it real at **about 170 MB per
lane per push** - the pack is 169 MiB - on three lanes. The comment above the checkout step in
`ci.yml` says the same. Recorded, not taken.
