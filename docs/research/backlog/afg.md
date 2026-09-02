# (afg) THE DOWNLOAD PAGE HAS NO HOME IN THIS REPOSITORY, AND `truestill.app` EXISTS ONLY IN CONVERSATION.

*Body of backlog entry `(afg)`, under **Build next**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(afg)** Filed 2026-08-22 by the release-readiness stock-take
  ([`PROJECT_STATUS.md`](../../PROJECT_STATUS.md) §2b), which went looking for the download page
  and found that the thing it would live on is not written down anywhere.

  ## WHAT IS ACTUALLY KNOWN

  1. **The domain `truestill.app` is bought.** Stated by the maintainer, 2026-08-22.
  2. ⚠ **CORRECTED 2026-09-02 (P190): it IS in this repository, four times, two of them before this was
     filed** - `DECISIONS.md` (analytics on `truestill.app`, *"domain not yet registered"*), `brand.md`
     (*"The landing page (`truestill.app`) - all of it"*), `brand/README.md`, and `(aad)`. And
     `DECISIONS.md`'s *"not yet registered"* contradicts claim 1 today; which is current is the
     maintainer's to say. The original claim follows.
     **Nothing about it is in this repository.** `grep -ri truestill.app` matches only
     `packages/truestill-app/`, `truestill_app/` and the `truestill-app` package name - the
     *identifiers*, never the domain. No entry, no decision, no note, no link.
  3. **D9 requires a download page, and its requirement is binding**, quoted rather than
     paraphrased: *"Windows users must be told what SmartScreen will show, and why, BEFORE they
     download. Plain language, on the download page, above the button - not in a FAQ and not after
     the fact."* D9 gives the reason as well: truestill is sold on trust with someone's
     irreplaceable photos, and *"a user who meets an unexplained 'unrecognized app' warning on
     that product draws exactly the wrong conclusion, and they draw it at the moment they were
     about to install."*
  4. ⚠ **CORRECTED 2026-09-02 (P190): `(aad)` closed on 2026-09-01 and its table delegates the page to
     `(afg)`**, so this pointer is circular; nothing outside this entry carries the page now.
     **`(aad)` carries it as item 5** of what remains, marked *"Still mandatory"* - re-confirmed
     2026-08-21 against winget, where an unsigned installer still shows the warning, so there is
     no second path that avoids the page.

  ## ⚠ WHY THIS IS AN ENTRY AND NOT A NOTE

  **This is `ENGINEERING_STANDARD.md` §4's fifty-eighth member exactly**: *a written claim can be
  falsified; an unwritten one cannot, and only one of them shows up in an audit.* The domain has
  been a live assumption in planning conversations while being invisible to every review, every
  grep and every stock-take - which is how it reached a release-readiness audit as a surprise.
  The audit that filed this found `(aad)`'s winget heading **wrong** and the Aceternity refusal
  **right**, and the only difference was that one of them existed on disk.

  Filing it makes it checkable. Nothing here asserts it is a good domain, a needed one, or a
  blocking one.

  ## ⚠ WHETHER IT BLOCKS A FIRST TAG IS **NOT DECIDED**, AND THIS ENTRY DOES NOT ASSUME

  Stated plainly because the stock-take that filed this had to guess once already, and guessing is
  what `(aef)` exists to stop. **The maintainer has not ruled.** The arguments the ruling would
  weigh, recorded so the ruling is made against them rather than from scratch:

  - **For blocking.** D9's requirement attaches to *"the download page"*, and a release with no
    page has nowhere to put the warning D9 calls mandatory. A `gh release create` page is not a
    download page in D9's sense - it has no room above the button for plain language, and the
    user arrives at it from a link rather than from a place that framed the product.
  - **Against blocking.** A first tag could be a **GitHub release only**, unannounced, with no
    page and no audience - which is what a first tag is *for* when the publish job has never run
    (`PROJECT_STATUS.md` §2b). ⚠ **That premise expired 2026-08-30**: the publish job ran on a
    throwaway tag (`release-rehearsal-record.md`), so the argument now rests on *unannounced*, not on
    *never run*. D9's requirement would then attach to the first *announced*
    release rather than the first tag. ⚠ But note `(adz)` **expires at the first tag** regardless,
    so "just a quiet tag" is not free.
  - **The middle.** The requirement is about what a *Windows user downloading an installer* is
    told. A tag that publishes archives and installers to a GitHub release page **is** that, for
    anyone who finds it.

  ## NOT DECIDED, beyond the above

  - **Where the page lives and what builds it.** Nothing is decided: not a static site, not a
    repository, not whether it is in this repository at all. ⚠ If it lives elsewhere, that
    decision should be recorded *here*, or the next audit re-discovers the same silence.
  - **What else the page owes**, beyond D9's warning: checksums and the sigstore verification
    line (`(aad)` records that the README carries verification instructions today), and what a
    macOS visitor is told, given that **nothing builds a macOS artefact anywhere in this
    repository**.
  - **Which component library the page uses is open, and D12 does not close it.** D12's scope was
    stated 2026-09-02 (P192): it refuses Aceternity for `truestill-app`, and a landing page is the
    category a Motion-based library is built for. The 21st.dev catalog (`agent-tooling.md`) carries
    such components; whatever is chosen is recorded here.
  - **Whether the brand assets are cleared for a public page.** `brand/PROVENANCE.md` records the
    artwork's licence; the trademark residual is a live pre-monetization obligation
    (`PROJECT_STATUS.md` §1) and a public page is closer to that line than a repository is.
