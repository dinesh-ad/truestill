# (alf) THE NIGHTLY LANE REPORTS TO NOBODY, AND A LANE THAT STOPS RUNNING REPORTS EVEN LESS.

*Body of backlog entry `(alf)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

**Filed 2026-09-18 (P252).** The browser lane was red on **2026-09-16, 09-17 and 09-18** with the
same single test, and nobody knew until the runs were looked at by hand. It had also been red on
09-08, 09-09 and 09-12. `make check` was green throughout and said nothing, because `testpaths`
keeps `tests/e2e` out of it.

## 1. THE MECHANISM EXISTS AND IS ALREADY ADDRESSED TO THE MAINTAINER

GitHub routes a scheduled run's failure notification to **whoever created the workflow or last
edited the cron syntax** - the maintainer, in `9c30767`, 2026-08-09. So this is not a missing
feature.

**Checked, not assumed** (2026-09-18): `gh api "/notifications?all=true&per_page=30"` returned
**20 notifications and zero with `reason: ci_activity`** - every one a `subscribed` PullRequest
from another repository. Nothing about this repo's failures reached the inbox.

⚠ **What that check does NOT settle**: whether the setting is off, or on-and-email-only-and-unread.
Reading it needs a scope the local token lacks - `gh auth refresh -h github.com -s notifications`,
then `gh api /repos/<owner>/<repo>/subscription`, which returned **404 / "needs the
notifications scope"** on the day of filing. **Run that before building anything.**

## 2. ⚠ THE SECOND EXPOSURE, WHICH NO FAILURE NOTIFICATION CAN COVER

The repository is **public** (`gh repo view --json visibility` → `PUBLIC`, 2026-09-18), so
GitHub's **60-day inactivity auto-disable** applies: a scheduled workflow is switched off after 60
days with no repository activity, and the warning email goes to whoever last enabled it.

**A disabled lane produces no run, so it produces no failure, so every option in §3 that watches
for red is blind to it.** Silence and success look identical. The project is not near that window
today - `pushedAt` was the same day - but a quiet stretch after launch is exactly when it would
happen and exactly when nobody is watching.

## 3. THE OPTIONS, COSTED. THE ENTRY DOES NOT CHOOSE.

| option | needs | cost | sees a red night | sees a STOPPED night |
|---|---|---|---|---|
| **A.** turn on the notification that already exists | the §1 check, then a settings toggle | free, ~2 min | yes | **no** |
| **B.** issue-on-failure step in `ci.yml` | ~10 lines, `permissions: issues: write` (no `permissions:` block exists today), third-party action pinned to a full SHA | free, ~30 min | yes | **no** |
| **C.** Slack or Discord webhook | a webhook URL in repo secrets, and a workspace | free, ~30 min | yes | **no** |
| **D.** email through ZeptoMail | the licensing server, which is unbuilt (D5 §5) | blocked | yes | **no** |
| **E.** dead-man's switch - the run pings a watchdog on success, the watchdog alerts on silence | an external account (healthchecks.io, cronitor) | free tier, ~30 min | yes | **yes** |

**The recommendation, and it is deliberately the unambitious one: do A first and alone.** The
mechanism is built, addressed to the right person, and most likely unticked. B through E all
construct a second notification path to replace one that may simply be switched off - and an
unwatched mechanism built to fix an unwatched mechanism is this entry's own subject.

**Only if A proves unreliable, reach for E rather than B** - E is the only row that sees §2, and §2
is the failure mode that cannot be noticed by looking.

## WHAT IS NOT PROPOSED

- **Putting the browser lane back on every push.** `(ajx)` measured that and refused it; the two
  stages are binding in `IMPLEMENTATION_STANDARDS.md`. This entry is about **reporting**, not
  about when the lane runs.
- **A guard.** Nothing in the tree can assert that a person received an email.
