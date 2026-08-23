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
