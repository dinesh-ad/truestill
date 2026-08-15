# (adt) TWO CATALOG WRITERS RACE INSIDE ONE PROCESS, ON AN ORDINARY USER PATH.

*Body of backlog entry `(adt)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adt) TWO CATALOG WRITERS RACE INSIDE ONE PROCESS, ON AN ORDINARY USER PATH.** Recorded
  2026-08-15 from CI run **`31895987230`**, which was red on a **docs-only** commit (`82831e8`;
  `git diff --name-only 5d3d647..82831e8` is Markdown only). `(adn)` is the two-process version
  of this. **This one needs no second process.**
  - **The user path, and it is three ordinary clicks:** choose *move*, *Look inside*, *Check for
    duplicates*. Nothing unusual, nothing concurrent that a user would recognise as concurrent.
  - **The mechanism, from the trace** (`e2e-failure-artifacts`, that run):

    | t | request | wait |
    |---|---|---:|
    | 2.01 s | **POST** `/api/organize/settings` | **6558.61 ms** |
    | 2.15 s | POST `/api/organize/inventory` | 3.17 ms |
    | 2.35 s | POST `/api/organize/preview` | 2.25 ms |
    | 2.39 s | GET `/api/jobs/<id>/events` | 5.36 ms |

    Picking the radio fires `app.js:2689-2695`, which calls `saveOrganizeMode`
    (`app.js:2000-2002`) - the 6.5 s POST. While it is in flight the dedup click
    (`app.js:2580-2600`) starts the preview job. The job meets the held catalog, waits out the
    **5 s `busy_timeout`** (`catalog_busy.py:7`), raises, and `jobs.py:211-214` converts it to
    `CATALOG_BUSY_MESSAGE`. `#org-confirm` is filled **only** on job success
    (`renderOrganizeRunConfirm`, `app.js:2004`), so it stayed empty and the assertion waited out
    its full 30 s budget against `<div id="org-confirm"></div>`.
  - **The browser was never slow, which is what rules out the tail.** Page load 347 ms, `check`
    167 ms, clicks 129 ms and 215 ms, every request HTTP 200. The failure is server-side
    contention wearing a front-end symptom.
  - **What a user sees is not a crash - it is a refusal that is true.** The busy message is
    accurate and the run stopped cleanly. What is wrong is that **one person, one window, one
    sequence of their own clicks** produced it. The message tells them to *"close the other
    Truestill window, or stop the other command in your terminal"*, and there is no other window
    and no other command.
  - **Cross-references.** `(adn)` - the same collision between two processes.
    `(ads)` - the mode that makes it possible: under `journal_mode=delete` a writer excludes
    everyone, so a settings write and a job cannot overlap; under WAL readers proceed alongside
    one writer. **A decision on `(ads)` changes what this entry needs**, which is why neither
    should be designed alone. `(ado)` - where this failure was nearly misfiled as the WebKit tail,
    and the amendment about why its zero-locks check could not see it.

  ## ⚠ THE OPEN QUESTION, AND IT IS THE ONE TO ANSWER FIRST

  **Why did a one-row settings write take 6.5 seconds?** Every other call in that trace was
  single-digit milliseconds. Contention explains the **job's failure**; it does not explain the
  **writer's duration**, and nobody has asked this before. If a single-row write can take 6.5 s,
  contention is the symptom and something else is the cause.

  What is established, with citations, and it is a lead rather than an answer: the settings POST
  is not one row. `server.py:235-241` hands it to `run_in_threadpool`; `set_organize_mode`
  (`organize.py:560-564`) **opens a Catalog** and then writes; and `Catalog.__init__` calls
  `_migrate` (`catalog.py:781`), which takes **`BEGIN IMMEDIATE`** (`catalog.py:830`) before it
  can decide the schema is already current. So **every catalog open acquires the write lock**,
  including one that will change nothing. The lock arc bought that deliberately - it is what made
  check-then-act atomic across processes (`PERFORMANCE.md` §5.4) - and its per-open cost has not
  been measured since.

  **Not established, and not to be assumed:** which holder the settings write was waiting on. The
  preview job started *after* it (2.35 s against 2.01 s), so the job is not the explanation. The
  artifact does not say, and no server-side timing was captured. **Answer this before designing
  anything** - a fix aimed at the race will not touch a 6.5 s single-row write.

  ⚠ **MEASURED 2026-08-15, AND THE LEAD ABOVE IS DEAD.** The per-open lock price is in
  `PERFORMANCE.md` §5.5 (CI run `31904426333`, three repeats per OS). On the ubuntu runner - the
  platform this happened on - acquisition is **0.004 ms**, an uncontended open is **0.096-0.133 ms**,
  and twelve concurrent openers reach a **107 ms** worst case with **zero busy refusals in 2,160
  opens**. The observed 6558 ms is **68,000x** the open and **61x** the worst contention measured.
  Windows, six times more expensive throughout, still tops out at 875 ms.

  **So `BEGIN IMMEDIATE` is not the answer, and the question is not narrowed - it is widened.**
  Nothing structural measured so far gets within 60x. Recorded as a **negative result** rather
  than left as a lead somebody re-derives: the shape here is §5.4's, where three structural
  hypotheses each fitted and were each 40-300x short, and only instrumenting the real lane closed
  it. **Server-side timing around `set_organize_mode` is the only instrument left** - env-gated,
  and removed a commit after it answers. Not built; nothing should be designed before it runs.

  ## Unverified corroboration, recorded as unverified

  The same run's other outlier is `test_a_radio_set_is_a_named_group[chromium-settings-Theme-theme]`
  at **30.21 s, passed**, against its five sibling parametrisations at **0.51-1.11 s**. That test
  drives the **Theme radio, which also writes a setting**. Both outliers in the run involve a
  settings write, in **different browsers**.

  **This is a hypothesis and must not be cited as evidence.** No trace exists for it - the lane
  keeps traces on failure only (`IMPLEMENTATION_STANDARDS.md` §6) - so there is no way to tell a
  settings-write stall from an unrelated 30 s pause. It is written down so the next red run knows
  to look, not so the count reads as two.
