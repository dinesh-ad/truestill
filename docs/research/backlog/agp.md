# (agp) THE BUSY MESSAGE NAMES A SECOND WINDOW THAT DOES NOT EXIST, AT THE USER'S FIRST CLICK.

*Body of entry `(agp)`. **OPEN.** The index is [`BACKLOG.md`](../../BACKLOG.md); the provenance index is [`SHIPPED.md`](../../SHIPPED.md). Split out of `(adt)` when it closed, 2026-08-23, and **ranked above `(agq)` by the maintainer.***

## The defect, and it is not a performance problem

`CATALOG_BUSY_MESSAGE` (`catalog_busy.py:70-76`) tells the user to *"close the other Truestill
window, or stop the other command in your terminal."* The `(adt)` investigation established that
the most likely way to meet it is a **first-run schema build** - one window, one user, their
**first ever click** on a fresh catalog - where **both clauses name things that do not exist**.

> *"That is the product telling a user something false at the exact moment it is failing them, on
> their FIRST EVER click on a fresh catalog. That is the worst possible first impression and it is
> a wording-and-detection defect, not a lock defect."* - the ruling that filed this.

## Prior art, recorded so it is not re-derived

**Zotero** refuses concurrent access outright and says plainly that another instance has the
database open - and it **earns** that sentence, because `locking_mode=EXCLUSIVE` makes it true.

**This product cannot claim it, for two recorded reasons**: `(adn)` establishes that two apps
really can run at once, and the common cause here is a first-run schema build with **no second
window at all**. A sentence Zotero can prove would be a guess here, and `catalog_busy.py`'s own
comment already refuses guessing: *"a guess here is worse than the gap."*

## The shape the message must take (ruled, not designed here)

Say **what is actually known**:

1. the catalog is busy;
2. this is **usually the first run preparing the library**;
3. it should clear on retry;
4. name a second window **only if one was actually detected**.

Detection is the open design half: in-process the app can know whether it is racing itself;
cross-process, `(aaw)`'s lock file records a holder for *drive* operations, and whether anything
analogous can honestly answer for the catalog is the question - the answer may be "nothing can",
in which case the message never names one.

## Constraints inherited from the file it changes

`catalog_busy.py`'s wording carries recorded reasoning that must survive any rewrite: it
deliberately does **not** claim nothing changed (a busy catalog is hit mid-run as often as at the
start), and the CLI and app must keep answering the same condition with the same sentence
(`(afe)`'s rule). `(agq)` - the boot-time build - disarms the commonest instance of this message
for most users; **this entry is what the message says whenever it still fires.**

---

## ✅ Part 1 shipped, 2026-08-23 - S4, the unhandled surface

The census found **seven** direct-write service calls across four files with no busy handling at
all (`set_organize_mode`, `set_sidebar_collapsed`, `set_text_size`, `set_library_root`,
`set_layout`, `confirm_file_date`, the events family) - a class, not a route. So the fix is one
**app-level exception handler** (`server.py`), mirroring the CLI's top-level catch
(`cli.py:4346`): busy answers **503** + `Retry-After: 5` with `CATALOG_BUSY_REQUEST_MESSAGE`
(`catalog_busy.py`), which asserts **no second window**; anything else re-raises and keeps its
500. A new route cannot be added outside it.

Settings writes retry via `REQUEST_BUSY_ATTEMPTS = 2`: each attempt already waits the driver's
5 s `busy_timeout` and the only measured multi-second holder is the <= 5.1 s first build, so the
second attempt lands after it - and sustained contention still surfaces at ~10 s rather than
hiding behind a minute. The user sees nothing during the retry (decided: an idempotent one-row
save, worst ~10 s). `app.js` shows a server-worded refusal as its own sentence; unworded failures
keep the path/status prefix. The refusal still lands in the fatal-banner surface - the calm
surface waits for the ladder.

**Found while building**: `create_app` opens an *existing* catalog at construction
(`server.py:153`, `prepare_catalog`) - so `(agq)`'s in-request first build is the
**fresh-create case only**, which narrows it.

**What remains here**: the detection ladder and S1/S2/S3 wording.

## ⚠ Tier 1 is DEAD - ruled 2026-08-23, so nobody rebuilds it from the old reasoning

The ladder was designed as three tiers, and tier 1 - an in-process registry of builds in flight,
so a busy refusal could say *"preparing the library"* exactly - **detects a case that cannot
happen**. The app has created and migrated the catalog at boot, before serving, since `b0a5d7e`
(2026-08-14, `catalog_startup.py:332`); an in-process, in-request schema build therefore does not
exist for a request to race. The only reachable "first run preparing" case is **cross-process** -
a CLI building while the app asks - which an in-process registry can never see. That case lands
in tier 3's wording (a possibility, softly) or tier 2's flock probe if the builder holds a drive
lock.

**The ladder is two tiers: the `(aaw)` flock probe, and the wording.** `(agq)`'s closure carries
the full trail, including why the entry that would have sequenced this was itself filed against
already-shipped code.
