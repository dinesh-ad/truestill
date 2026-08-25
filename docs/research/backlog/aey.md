# (aey) ON PYTHON 3.14 AN UNREADABLE FOLDER WOULD BE REPORTED AS MISSING AND CREATABLE.

*Body of backlog entry `(aey)`, **CLOSED 2026-08-21**. The closure is in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

- **(aey) `pathlib` STOPS RAISING ON `EACCES` IN 3.14, AND `path_probe` IS BUILT ON IT RAISING.**
  Found 2026-08-21 while researching the 3.14 upgrade. **Not live** - this project runs 3.13 - and
  it is the concrete reason the move was deferred rather than a reason to hurry it.

  > ⚠ **Dated correction, 2026-08-22:** *"this project runs 3.13"* was true when written and is
  > not now - the move happened the next day (`DECISIONS.md` D13), and closing this entry is what
  > unblocked it. Left in place: a record edited to stay correct stops being one. **Nothing here
  > became live**, because the fix shipped before the interpreter did.

  ## MEASURED, on the 3.14.4 interpreter present on this machine

  ```
  chmod 000 on the parent, then:
                     3.13.13              3.14.4
  Path.is_dir()      PermissionError      False
  Path.exists()      PermissionError      False
  os.stat()          PermissionError      PermissionError
  ```

  Upstream: [cpython#144525](https://github.com/python/cpython/issues/144525),
  *"`pathlib.Path.is_file` no longer throws an exception on Python 3.14"*.

  ## WHY IT IS A DEFECT AND NOT A CURIOSITY

  `service/path_probe.py` exists **specifically** to preserve this distinction. Its own docstring:
  *"`Path.exists` and `Path.is_dir` look total and are not… they re-raise everything else,
  `EACCES` included… **absent and refused are different answers.**"* Three app surfaces once
  returned 500 on a permission-denied folder (audit F21) and this module was the fix.

  On 3.14, `probe_dir` (`path_probe.py:55-66`) reads:

  1. `path.is_dir()` → **`False`** instead of raising, so the `except OSError` never fires;
  2. `path.exists()` → **`False`**, so it returns **`PathReach.MISSING`**.

  A folder the user cannot read is reported as **absent and creatable**. Offering to create it
  sends them round a loop the module was written to prevent - and it is the same family as
  `(aac)`/`(aer)`: a place Truestill could not look into, described as one with nothing in it.
  `nearest_device` (`path_probe.py:79`) has the identical shape.

  ## ⚠ THE GUARD THAT SHOULD HAVE CAUGHT IT SKIPS INSTEAD OF FAILING

  `test_unreadable_paths.py:85` says in its own docstring: *"If `Path.is_dir` ever starts
  swallowing `EACCES`, this fails - which is exactly when someone should be made to re-read this
  module's rationale."*

  It does not fail. `_really_locked` (`:62-78`) decides whether the condition reproduced by
  calling **the same swallowing method**, so on 3.14 it concludes *"chmod 000 did not deny this
  process"* and the test **skips**. Measured: 3 runs each, deterministic - 1 skip on 3.14, 0 on
  3.13. §4's fifty-second member from the inside: the precondition check and the subject share a
  mechanism, so the subject cannot be observed failing.

  **The consequence for the new 3.14 CI leg**: it reports **2,664 passed, 2 skipped - green** - while this defect is live. The leg is evidence, not a gate, and this is why it cannot be
  promoted to one until the probe is rewritten.

  ## THE SITES - grepped, not assumed. FOUR, and three carry a comment stating the rule 3.14 breaks

  ⚠ **`path_probe` is the one DESIGNED for the distinction; it is not the only one that relies
  on it.** Searched for the pattern - a `Path.is_dir()`/`exists()`/`is_file()` call whose
  `except OSError` branch means something different from its `False` branch.

  | site | what the code says about it | on 3.14 |
  |---|---|---|
  | `path_probe.py:55-66` `probe_dir` | the module exists for *"absent and refused are different answers"* | returns **`MISSING`** - absent and **creatable** |
  | `path_probe.py:79` `nearest_device` | *"stops rather than walking past a directory that refused"* | walks past it |
  | `destinations/local.py:113-118` | **deliberately raises** `DestinationError` on a refused probe | `except` never fires; reports **not there** |
  | `date_rescue.py:280-283` | `# unreadable mount: cannot look, which is not "nothing there"` | falls through to `{"status": "none"}` - **"nothing there"** |
  | `drive_adoption.py:167-171` | `# unreadable or dead mount: not evidence either way` | counted as **absent evidence**, and can flip `PRESENCE_THRESHOLD` to `NO_MATCH` |

  **Checked and NOT affected** - reported because a null result is a finding:

  - `drive.py:719-729` `path_is_usable_dir` - collapses refused to `False` **by design**
    (*"False means do not trust this path"*). Same answer on both versions.
  - `reclaim.py:80-84` and `:103-111` - `False` is the conservative answer at both sites, so a
    refused path still means *do not delete*. **The deletion path fails safe on both versions.**
  - `left_behind.py:88-92` - both branches `continue`.
  - `fs_browse.py:95` and `:127` - **measured, not reasoned**: `stat()` needs permission on the
    *parent*, so `is_dir()` on a `chmod 000` **child** returns `True` on both versions. The
    unreadable-parent case raises from `iterdir()` first and is already caught.
  - `drive.py:742-745` `locate_drive` - a refused path returns an empty location on 3.13 and
    walks its parents on 3.14. Different, arguably harmless, listed rather than hidden.

  ## THE 3.14-SAFE PRIMITIVE - measured on both interpreters

  | call | 3.13 | 3.14 |
  |---|---|---|
  | `Path.stat()` / `os.stat()` / `Path.lstat()` | raises `EACCES` | **raises `EACCES`** |
  | `Path.is_dir()` / `.exists()` / `.is_file()` | raises `EACCES` | **`False`** |
  | `os.path.isdir()` | **`False`** | `False` |

  ⚠ **3.14 did not invent this behaviour; it removed pathlib's exception to it.** 3.13's
  `is_dir()` calls `self.stat()` and re-raises unless `_ignore_error(e)` (ENOENT, ENOTDIR, EBADF,
  ELOOP). 3.14's is one line - **`return os.path.isdir(self)`** - and `os.path` has swallowed
  every `OSError` for as long as it has existed. Our code depended on pathlib being the outlier.

  **There is no opt-in.** `is_dir(follow_symlinks=False)` and `exists(follow_symlinks=False)` were
  checked and swallow too. The remedy is `Path.stat()` plus `stat.S_ISDIR(st.st_mode)`, switching
  on `exc.errno`: `ENOENT`/`ENOTDIR`/`EBADF`/`ELOOP` are *absent*, everything else is *refused*.
  ⚠ That is also **cheaper than today's code**, which spends two stats on the missing path
  (`is_dir()` then `exists()`); one `stat()` answers all four `PathReach` values and keeps the
  module's stated **O(1), one stat** budget honestly.

  ## ⚠ THE GUARD THAT SHOULD HAVE CAUGHT IT SKIPS INSTEAD OF FAILING

  `test_unreadable_paths.py:85` says in its own docstring: *"If `Path.is_dir` ever starts
  swallowing `EACCES`, this fails - which is exactly when someone should be made to re-read this
  module's rationale."*

  It does not fail. `_really_locked` (`:62-78`) decides whether the condition reproduced by
  calling **`is_dir()` - the subject itself** - so on 3.14 it concludes *"chmod 000 did not deny
  this process"* and the test **skips**. Measured, three runs each, deterministic: 1 skip on 3.14,
  0 on 3.13. This is now `ENGINEERING_STANDARD.md` §4's **fifty-seventh member**.

  **The consequence for the 3.14 CI leg**: it reports **2,664 passed, 2 skipped - green** - while
  this defect is live. That is why the leg is evidence and cannot be promoted to a gate.

  ## THE TEST SHAPE THAT WOULD HAVE CAUGHT IT - verified on both interpreters

  Two changes, and the second is the one worth keeping.

  **1. Establish the precondition through a call the subject does not share.** `os.stat()` raises
  on both versions, so it answers the question the test is actually asking - *did the OS deny?* -
  rather than *does `is_dir` still report denial?*

  ```
                                                3.13      3.14
    precondition via os.stat  (independent)     denied    denied     <- test RUNS on both
    precondition via is_dir   (same call)       denied    NOT denied <- test SKIPS on 3.14
  ```

  With the independent precondition the existing assertion
  (`pytest.raises(PermissionError): (locked / "inner").is_dir()`) **fails on 3.14 and passes on
  3.13**, which is exactly what it was written to do.

  **2. Better: assert the PRODUCT'S contract, naming no stdlib call at all.**

  ```
    probe_dir(refused folder)  ->  3.13: unreadable  PASS
                                   3.14: missing     *** FAIL
  ```

  Measured by importing the real `probe_dir` under each interpreter. This states what Truestill
  promises rather than what CPython happens to do, it discriminates today, and - unlike the
  premise test - **it stays correct after the fix** instead of needing to be inverted.

  ## ⚠ THE SWEEP THE PIN PROVOKED, AND ITS ANSWER

  `(aez)` was two bare probes in one module with the guarded helper three functions away. That is
  evidence nobody had swept the area, not evidence those were the only two - so every destructive
  call in `packages/*/src` was read, and every predicate gating one.

  **There was a third**: `cleanup.plan_cleanup`, which gated on a bare `folder.is_dir()` and
  **raised on 3.13** when the folder's parent refused - inside a function whose docstring promises
  *"Pure: reads, never writes"*. Filed and closed as `(afb)`. **3.14 masked that one too**, which
  is the second time the version treated as the threat turned out to be hiding a live defect on
  the version we ship.

  **`organizer._move_source` was clean and is the shape the others should have had**: it verifies
  by checksum rather than by a predicate, and catches around both the verify and the `unlink`, so
  every failure keeps the source. The rest of the `unlink`/`replace` calls in the tree operate on
  Truestill's own temp files and journals, each inside its own `try`.

  Two of the three delete-adjacent modules carried the defect. That ratio is why the rule went
  into `IMPLEMENTATION_STANDARDS.md` rather than into three more comments.

  ## NOT DECIDED

  - **How wide the sweep goes.** Five sites are named above; the pattern is *"an `except OSError`
    that means something different from the `False` branch"*, and the guard against reintroducing
    it may be worth more than the five fixes.
  - **Whether `probe_dir`'s errno split belongs in core.** Four of the five sites are outside
    `truestill-app`, and `path_probe` currently lives in the app service layer.
  - **Whether the premise test survives at all.** Once `probe_dir` no longer calls `is_dir()`,
    a test asserting `is_dir()` raises is asserting something the product no longer relies on.

## ⚠ A SIXTH SITE, found 2026-08-24 by an outside audit - the census pattern could not have seen it

`verify.py:90` (`_partition`) used a bare `is_file()`: on 3.14 a stat-REFUSED copy read as
`CopyStatus.MISSING`, and the app recorded `mark_copy_missing` on the strength of it - a loss
claim about a file the OS never let verify examine, in the one feature whose value is being
believed. Fixed with `path_reach.reach` (P35); regression pinned by a real mode-000 parent in
`test_verify_unreadable.py`, whose earlier tests patched `sha256_file` - a stage that runs only
AFTER `is_file()` succeeded, so the file's own subject was invisible to it.

**Why the census missed it, knowably**: the pattern above was *"a probe whose `except OSError`
branch means something different from its `False` branch"* - it matched only code that already
HAD an except clause. `verify._partition` had none (on 3.13 a refused stat simply raised out of
it), so there was no branch pair to match. The census found code that knew the distinction and
lost it; it could not find code that had never handled the exception at all. The NOT-DECIDED
above already said the reintroduction guard "may be worth more than the five fixes" - this is
that sentence proven.

**The re-census, 2026-08-24, ALL 66 bare boolean probes across core, cli and app classified by
failure direction** rather than by except-shape. Two sites recorded a false fact or offered a
wrong action: `verify.py:90` (fixed here) and `undo.py:291-301` (a refused origin reads as
free, then a replace-capable rename aims at it - **in flight in a peer session with its
fail-first test already written; deliberately not touched by this commit**). Everything else:
guarded (`drive.py:99/728/745`, `cleanup.py:185` via `(afb)`), deliberate (`reclaim.py:97`,
recorded above), conservative (cleanup tiers, `hash_cache.py:374`), or fails loud immediately
behind the probe (`catalog_move.py:103/125`, `local.py:219/262`, `backup.py:157/162/625`, the
CLI arg checks). A residue of **wording/under-count** sites where refused reads as absent in a
message or report - `catalog_startup.py:246` and `cli.py:893/1276` (a refused catalog briefly
banners as creatable before the open fails loudly), `bake.py:378`, `drives.py:219`,
`left_behind.py:89`, `source_repoint.py:129`, `organizer.py:365` (reachable only via ACLs on a
listable parent) - none records a fact or moves a byte; named here so the next audit inherits
the list instead of re-deriving it.

## The SEVENTH site closes the class - undo, 2026-08-24, and the split was not optional there

`undo._why_not` (`undo.py:291-301`) probed with bare `is_file()`/`exists()`: a refused origin
read as FREE, and a replace-capable rename then aimed at a path the OS would not describe - the
`(agk)` shape one layer up. Its fail-first test was written in ANOTHER session (the machine's
parallel one, orphaned when that session ended) and adopted rather than rewritten: it asserted
the right property - `UndoSkip.UNREADABLE` in the plan AND the placed file still in place -
for the right reason. Undo is the site where the verify/reclaim split question answers itself:
reclaim could conflate because both failures mean *do not delete*, but undo's two failure
meanings demand DIFFERENT actions - an ABSENT origin is the happy path (the slot is free), only
REFUSED means stop. `run_undo` re-checks through the same `_why_not` predicate (its own comment:
*"THE SAME PREDICATE AS THE PLAN"*), so plan and re-check were one fix site, not two.

One adaptation, recorded: `test_a_file_that_vanishes_mid_check_is_refused` patched `Path.stat`
to raise ENOENT for the whole plan; with `reach()` in front, an all-calls ENOENT now honestly
reads MOVED_AWAY (the file IS gone). The test's subject was always the identity check's own
stat guard, so the vanish is now scheduled on the SECOND stat.

**The completeness bar, re-stated after two censuses**: not "no bare probes" - reclaim keeps
its two deliberately - but "no site where refused-as-False records a false fact or aims an
action". Seven sites met that bar; all seven are fixed. **How this is known rather than
believed**: every one of the 66 bare boolean probes across core, cli and app has a written
verdict (the P35 list above), the two audits arrived by different methods (except-shape, then
failure-direction), and the wording residue now has its own letter - `(agt)` - so the next
sweep starts from the list instead of the grep.
