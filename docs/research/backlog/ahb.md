# (ahb) THE UNDATED REPORT NAMES THE PROBLEM AND LINKS TO NOTHING.

*Body of entry `(ahb)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ahb) THE UNDATED REPORT NAMES THE PROBLEM AND LINKS TO NOTHING.** Filed 2026-08-24 (P53).
  **Ranked ABOVE `(aha)`**: that one records a defect, this one is a **route**, and the route is
  what keeps a user out of the defect.

## The gap, in one line

The Organize result names the undated pile - *"No reliable date could be found, so these are kept
together, not guessed"* (`static/app.js`, the `Undated` entry in `CAT_INFO`) - and lists up to
eight sample paths (`app.js`, `undated_samples`). **It links to nothing.** Checked: no nav action,
no *"set dates"*, no mention of the Dates screen anywhere in that block.

**The screen built to fix exactly this exists and is reachable by another door**: the honesty
view's drill-down → `POST /api/dates/confirm` → `Catalog.confirm_date`. A user who never opens the
Dates screen never learns it is there.

🔑 **That is the `(afu)` shape - a thing that exists and cannot be reached one level up** - and here
it has a **measured population**: the golden corpus snapshot records **1,262 undated of 7,790
files, 16%** (`tests/golden/input-dates.tsv` header, recorded 2026-08-23).

⚠ **And it is the exact moment a user reaches for an external tool.** `(ii)` warns that a hand-fix
*"is actively reverted, which is worse than not supporting it"*, and `(aha)` traces what actually
happens when they try. **A link here is the cheapest thing that keeps them on the supported path.**

## What the signpost may honestly say - and the self-drain decides it

⚠ **The list SELF-DRAINS, which changes the wording rather than the plumbing.**
`Catalog.files_in_date_tier` filters `WHERE date_source IS NULL` / `= ?`, and `confirm_date` does
`UPDATE files SET captured_at = ?, date_source = ?` - so a confirmed file **leaves the tier**.
Re-opening the drill-down shows the next page.

So:
- ✅ *"Set dates for these"* is honest - the work drains as it is done.
- ❌ *"Review 1,262 files"* is **not** - a user sees **50 at a time** (`stats.DATE_TIER_PAGE`) and
  the count shrinks as they work. A number that large also reads as a wall rather than a task.

**1,262 files is roughly 26 open-confirm-reopen rounds**: tedious, disclosed, and **completable**.

## ⚠ `DATE_TIER_PAGE = 50` WAS CHECKED AND IS NOT THE DEFECT - do not spend a turn on it

There is **no next-page control**: the handler fetches `/api/dates/files` once, with no offset
parameter. But the cap is a **pacing limit, not a ceiling**, for two reasons already in the code:

1. **The truncation is disclosed** - `hidden = page.total - page.files.length` renders
   *"…and N more"*, and the handler's own comment says *"Truncation is disclosed the same way every
   other list does it."* **The pile never looks finished**, which is the failure that would have
   mattered.
2. **The list self-drains**, so the next 50 arrive on the next open.

And its provenance is **reasoned rather than round**, stated where it is defined: *"Same order of
magnitude as the search page size: enough to judge a tier, short enough to read. **The total always
travels with it.**"* A judgement that carries its own reasoning and its own mitigation is not the
unmeasured-number-become-rule shape this repo has filed before. **Recorded here so the next reader
does not re-derive it.**

## Q297 - the browser lane can stay off, and the precedent is this entry's own defect

**A text-only link is pinnable in `pytest`**, and the repo already does it:
`test_the_rearrange_card_name.py` reads `app.js` as text and asserts one name appears in every
place a person reads it. ⚠ **Its docstring is this entry's defect, already solved once for a
different feature:**

> *"the old name was the reason the feature was invisible. 'Move existing files to match' does not
> say what it matches, so nobody looking for 'rearrange my library into dated folders' found it -
> while the seven-step manual procedure they were offered elsewhere is exactly what this
> replaces."*

**A user offered a manual procedure because the built feature was unfindable** is precisely what is
happening to the Dates screen. So: **what it touches** is the undated block in
`static/app.js` and, if the wording is shared, `service/organize.py`'s payload; **how it is
pinned** is a pytest test over `app.js`'s text, the way the rearrange name and the folder wording
already are. **The lane stays off** unless the change grows beyond a string and a target.

> ## ✅ THE APP HALF SHIPPED 2026-08-24 (P54). The CLI half is still open, below.
>
> ⚠ **AND THE GAP WAS NOT WHAT THIS ENTRY SAID.** It read *"links to nothing"*. **It linked to
> Find** - `data-stats-action="undated"` → `showScreen("find")` + a search for `Undated`. Find
> locates files by path and **cannot set a date**, so the route existed and pointed away from the
> fix, while the rescue sat **two cards above on the same screen**. Corrected here rather than in
> a note, because this is an open entry.
>
> 🔑 **And the sentence beside it was worse than the missing link:** *"Opens Find with 'Undated' so
> you can locate and fix dating gaps."* **Find fixes nothing** - that is
> `IMPLEMENTATION_STANDARDS.md` §9, a screen claiming an action does something it cannot. Removed.
>
> **What shipped:** the undated actions are now gated on `completeness.undated_files` (Q303 -
> they rendered unconditionally, so a library with every date known was offered a route to an
> empty search); **Set dates for these** opens the existing `data-date-tier="none"` drill-down
> rather than a second path to the same list; and Find keeps its place, worded as what it does.
> Pinned by `test_the_undated_report_offers_the_rescue.py` - seven assertions, three mutations,
> all caught, **browser lane not run**.
>
> ## Q304 - `(afe)` is NOT broken, and the reason is worth stating
>
> The app now names a remedy the CLI cannot. **That is outside `(afe)`, not a violation of it.**
> `(afe)`'s rule is that the two surfaces must not describe **the same fact** differently - and
> they do not: both name the undated pile, and neither claims the other's capability. The app
> names an action **it has**; the CLI stays silent about an action **it does not have**, which is
> accurate on both surfaces.
>
> ⚠ **What WOULD break `(afe)` is the tempting next step**: giving the CLI the same sentence. A CLI
> that says *"set dates for these"* would describe a capability that surface lacks - the drift
> `(afe)` exists to catch, arriving through an attempt to satisfy it. **The honest CLI sentence
> points at the app**, and that is the ruling below, still unmade.

## Q298 - the CLI has the same gap AND a harder fix. It is not pure wording.

⚠ **The premise that this half is cheap is FALSE, checked rather than assumed: there is no CLI
rescue command to point at.** `grep -c 'add_parser("dates"'` returns **0**, and
[`BACKLOG.md`](../../BACKLOG.md)'s *App-surface deferrals* records why: *"The date rescue
(`confirm_file_date`) is APP-ONLY, recorded 2026-07-31 when step 5 made it reachable."*

So the honest CLI sentence would have to point **at the app** - a cross-surface pointer, which is a
product decision rather than a wording fix, and a larger claim than `(afe)`'s one-sentence rule
anticipates. ⚠ **`(afe)` still applies to the half that is shared**: whatever the app says about
the undated pile, the CLI must not say something different about the same files. **Rule the
cross-surface pointer before writing either sentence.**

Separately, and stated so nobody widens this entry onto it: the CLI's `_print_skipped_undated`
(`cli.py:2268`) covers only the `--skip-undated` case - files *not copied at all* - which is a
different report from *"these were copied to `Undated/`"*. Both surfaces name the pile; only the
app has somewhere to send the user.
