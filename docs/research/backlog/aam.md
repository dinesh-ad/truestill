# (aam) Sidebar reference: profile header, section labels, submenus.

*Body of backlog entry `(aam)`, under **Blocked - do not build yet**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(aam) Sidebar reference: profile header, section labels, submenus.** Ruled by the
  maintainer, 2026-08-01.
  ⚠ **CORRECTED 2026-09-02 (P186) - four of the six items are built and the blocking question is
  answered.** Section labels, the pill active state, the collapsed rail with hover and focus
  tooltips, and the wordmark ship in `index.html` and `app.css`; `index.html`'s own comment reads
  *"`(aam)` closed as NO nested submenus"*, which retires the flyout and its keyboard cost below.
  **What remains is the profile/licence header alone, and it waits on `DECISIONS.md` D5's
  activation** - the account slot in `index.html` is reserved and empty. The rest is kept beneath as
  the design record.
  - **Why the profile header applies at all, corrected.** It was first set aside on the
    assumption that truestill has no accounts. `DECISIONS.md` **D5** supersedes D1: truestill
    **requires a user account**, created at activation against a self-hosted licensing server.
    So an identity in the UI is not scaffolding for a feature that will never exist - it is the
    surface D5 needs. **Cursor is the model:** sign in once, work offline afterwards, identity
    visible in the interface rather than hidden in a settings page.
  - **Profile header:** avatar, name, and **licence state** (Pro / free - **not** trial; see
    `DECISIONS.md` D6 §4, which abolished the trial after this entry was written) in the position
    the reference gives a role line. This is also **where the account surface lands when D5's
    licensing server ships**, so it is built once rather than added beside something later.
  - **Wordmark** from [`brand.md`](../../brand.md), above or beside the profile header. Which of the
    two is a decision for the build, not now.
  - **Section labels** (`MAIN` / `SETTINGS`), **pill active state**, and a **collapsed icon rail
    with tooltips** - the rail is already built in `(fff)`, so this reference confirms it rather
    than adding it. **Flyout submenu on hover when collapsed** is the new part.
  - **The bottom action is not "Logout".** A one-click logout next to Help treats activation as
    a session, and it is not one: activation happens **once**, and a perpetual licence
    (`DECISIONS.md` D6) is not a login. The bottom item is **account or licence details**, with
    sign-out available *inside* it. Recorded with the reasoning because the failure mode is
    specific and severe: **a casual logout button can strand a user from software they have paid
    for**, on a machine that may be offline, for a product whose whole proposition is custody.
  - **BLOCKING QUESTION (answered: NO nested submenus - `index.html`, see the correction above): do any screens get NESTED SUBMENUS?**
    truestill's screens are flat today. Adopting the reference's hierarchy means deciding which
    screens have children and which do not, and that is **information architecture, not
    styling** - it changes what the product says its parts are. Needs a ruling before any of
    this is built; the flyout behaviour above is meaningless until it has one.
  - **The cost, recorded so it is priced rather than discovered.** A hover flyout **needs a
    keyboard equivalent**. `(fff)` already established this exact rule for the collapsed rail -
    tooltips on hover **and focus**, recorded there as "not optional polish" - and a submenu
    reachable only by hover is **unreachable by keyboard**, which is worse than a tooltip that
    is merely invisible: the navigation itself becomes unusable. Whatever the answer to the
    nested-submenu question, the flyout is two implementations, not one.
