# truestill - Product Decisions (binding, with rationale)

Durable product decisions and the reasoning that produced them. Unlike `BACKLOG.md` (approved
but *unbuilt* work), entries here are **settled stances** that govern what truestill is - kept so the
rationale outlives chat history. Where a decision is also a binding engineering invariant, the
short form lives in `IMPLEMENTATION_STANDARDS.md` and this file holds the full "why".

---

## D1. No accounts, no required telemetry - permanently

> ## ⚠ SUPERSEDED (2026-07-28) by **D5**, on the maintainer's ruling
>
> truestill **will require a user account**, created at activation against a self-hosted
> licensing server. The reasoning below is preserved unedited because it is the record of why
> the original stance was taken and what it was weighed against - not because it still governs.
> **D5 is what governs.** The parts of D1 that survive are narrower and are restated there:
> photo data still never leaves the machine, and there is still no per-launch phone-home.
>
> The engineering recommendation was **against** this change; it is recorded in D5 §4 at
> the maintainer's instruction rather than dropped.


**Decision.** truestill collects **no user accounts** and **no required telemetry**, permanently.
There is no login, no sign-up, no device identifier, no phone-home, and no usage beacon compiled
into the product. This is not a launch-phase posture that relaxes later; it is a permanent
property of what truestill is.

**Scope - what this forbids inside the product:**

- No account creation or authentication of any kind to use truestill (free **or** Pro).
- No required telemetry, analytics SDK, crash reporter, or usage ping embedded in the CLI, the
  core library, or the local web app.
- No unique identifier assigned to an install or a user.
- No network call the product makes on the user's behalf that transmits their activity. The
  product's core promise - **"your files never leave your machine"** - must hold *inside* the
  product itself, not just as marketing copy.

### How usage is measured instead (all external to the product, all aggregate)

Measurement happens **outside** the running product, from data the distribution and payment
channels already produce. None of it requires instrumenting the software:

1. **PyPI download statistics** - aggregate install counts for the published packages.
2. **GitHub signals** - stars, clones, and per-release download counts.
3. **Privacy-friendly site analytics on `truestill.app`** *(domain not yet registered)* - a Plausible-class analytics tool: **no
   cookies, no personal data, no cross-site tracking**. Page-level aggregates only.
4. **Purchase records for Pro customers** - name / email / country, held by the **payment
   provider** as the record of a transaction. This is a payment record, not product telemetry:
   the software never sees or sends it, and it exists only because someone chose to buy.

These four give a truthful picture of adoption and revenue without a single byte of behavioral
telemetry leaving a user's machine.

### Rationale - the Audacity 2021 precedent

In 2021 Audacity's new steward proposed **opt-in** telemetry. The reaction from exactly the kind
of privacy-conscious, self-hosting audience truestill serves was decisive: roughly **3,500 downvotes**
on the proposal, **50+ forks** within days, and a permanent hostile fork (**Tenacity**) that
persists. The lesson is not "telemetry is unpopular" - it is that **for this audience, an
identity or telemetry demand converts trust directly into forks.** A tool whose entire value
proposition is "your irreplaceable files never leave your machine" cannot ask those same users to
send it their behavior; the contradiction is fatal to the trust the product runs on.

So the stance is a *product* decision, not merely a privacy nicety: it protects the single asset -
user trust - that makes a local-first media tool worth adopting.

### Future crash reporting - conditions, if ever

Should crash reporting ever be introduced, it must be **all** of:

- **Opt-in and off by default** - never enabled without an explicit, informed choice.
- **Self-hosted** - reports go to infrastructure truestill controls, never a third-party SaaS.
- **Transparent** - the exact payload is documented and inspectable before a user opts in.
- **Introduced only after community trust exists** - a post-launch, trust-has-been-earned move,
  **never shipped at launch**.

Absent all four, it does not ship.

### Pro tier without login

Pro features are gated by **offline-verified license keys** (the capability seam in
`IMPLEMENTATION_STANDARDS.md §2`), **not** a login or an account. A key is verified locally; using
Pro requires no server round-trip, no sign-in, and no online activation that would leak usage.
This keeps the no-accounts invariant intact while still supporting a paid tier. (Purchase records
per item 4 live with the payment provider and are a billing artifact, not an in-product identity.)

**Status:** **Superseded by D5 (2026-07-28).** Retained as the record of the original stance.

---

## D2. Browser end-to-end tests run on the host, not in Docker

**Decision.** The E2E layer is **Playwright driven by `pytest-playwright`**, running against an
**in-process** app server on the developer's own machine and on a plain GitHub runner. **Docker
is rejected as the test substrate.**

**Why Playwright rather than Selenium or Cypress.** Auto-waiting is the deciding property:
every assertion retries until it passes or times out, which removes the `sleep` calls that are
the dominant flake source in browser suites. It drives real Chromium (not a shimmed DOM), ships
first-party trace/video capture that makes a red CI run arrive with a replay rather than a
guess, and its `pytest` plugin means the browser lane uses the same runner, fixtures and
conventions as the rest of the suite instead of introducing a second test language and a Node
toolchain. Cypress would have imported an npm build step into a project whose entire UI
architecture is *no build step* (D-adjacent: see `BACKLOG.md` (o) and the no-bundler rule).

**Why not Docker.** It was considered for hermeticity and rejected on cost/benefit:

- The thing being tested is a **local-first desktop-ish tool**. A container is a *less*
  faithful environment than the developer's own machine, not a more faithful one - it hides
  exactly the host-filesystem, mount-point and permission behaviour the product exists to
  handle.
- The real portability risk is **OS differences**, and that is already owned by the
  {ubuntu, macos, windows} Python matrix. A single Linux container would have covered less.
- Playwright's browser binaries are already version-pinned and cached in CI, which is the
  reproducibility Docker was being considered for.
- It would add a build-and-image-maintenance burden to a repo whose stated principle is to
  justify every layer with a measured need (`ENGINEERING_STANDARD.md` §1).

**Status:** Settled. Mechanics and the binding lane rules in `IMPLEMENTATION_STANDARDS.md` §6.

---

## D3. What the browser lane covers - and what it deliberately does not

**Decision.** Four scope rulings, made when the lane was built, recorded so they are not
quietly relitigated as "more coverage is better".

1. **~~Chromium on ubuntu only - no browser × OS grid.~~ REVERSED IN PART, 2026-08-14.** The
   original ruling read: *"this lane owns client-side truth, which for a vanilla-JS app with no
   build step and no framework runtime is browser-uniform enough that a grid would buy coverage
   there is no evidence we need. Revisit on evidence - a real cross-browser bug - and not
   before."*

   **The evidence it asked for arrived, and so did the reason its premise expired.** `(9cdd85d)`
   added WebKit because **WebKit is the engine the Tauri shell renders in on Linux and macOS** -
   a chromium-only lane was silent about the browser that ships, which is a stronger argument
   than any single cross-browser bug. And the premise itself is now false twice over: the app is
   not no-build (`make e2e` depends on `make frontend`, which runs `tsc --noEmit && vite build`)
   and not framework-free (a React island owns `#org-result`).

   **What stands:** one operating system in this lane. The OS axis is still the Python matrix's
   job, and widening it still waits on a real cross-OS browser bug.
2. **Fixtures are generated, never committed.** Media files do not belong in git whatever their
   provenance; a committed generator (`tests/e2e/conftest.py`) builds exactly the corpus each
   test needs. This also keeps the personal corpus out of the repo permanently.
3. **No in-place-organize E2E.** The feature is CLI-only by decision
   (`BACKLOG.md`, app-surface deferrals), so there is no UI to drive; asserting it through a
   browser would test a surface that does not exist.

   > **⚠ PREMISE SUPERSEDED (2026-07-30) by `(eee)`, now in `SHIPPED.md`.** The ruling above is kept
   > unedited because it was **correct when it was made**: the app had no in-place surface, and
   > an e2e for it would have asserted against nothing. `(eee)` then shipped Copy / Move /
   > Reorganize-in-place as radio options (`templates/index.html`), which removed the premise
   > rather than reversing the reasoning. `tests/e2e/test_ui_regressions.py` now drives that
   > surface, correctly.
   >
   > **What survives is the rule, not the verdict:** the browser lane covers a surface that
   > exists and does not invent coverage for one that does not. Applied to today's app, that
   > same rule produces the opposite answer. Note the deferral this ruling cites has moved on
   > too - `reclaim` is now the only thing still CLI-only, so a `reclaim` e2e would be the
   > current instance of the mistake this ruling was written to prevent.
4. **One golden path as a single long journey, not six tests.** The value is in the *handoffs* -
   state carried from organize to Backups, a library the app registered being accepted by the
   copy flow. Split into six set-up tests, the defect that actually shipped (organize never
   registering its own destination) would have passed all six.

**Status:** Settled. Rules in `IMPLEMENTATION_STANDARDS.md` §6; the journey itself is
`tests/e2e/test_golden_path.py`.

---

## D4. Batched exiftool writes use an argfile, not a persistent process

**Decision.** The Takeout metadata bake batches through an **argfile with `-execute`
separators** (`exif.write_metadata_batch`). exiftool's `-stay_open True -@ -` persistent-process
mode was measured, compared, and **not adopted**.

**The measurement** (300 files, then confirmed at 1,203):

| approach | per file | vs today |
|---|---|---|
| one process per file (what shipped before) | 225–255 ms |- |
| argfile batch | 5.2 ms | ~43× |
| `-stay_open` persistent process | 4.6 ms | ~48× |

**The rationale is the TCO rule, applied literally.** `-stay_open` is **1.12× on top of a 27×
win** end to end. What that 1.12× costs is a persistent child process, a reader thread, timeout
handling and a lifecycle state machine with a mid-batch-death mode - on **the one code path in
the product that modifies bytes the user keeps**. A component earns its place by solving a
problem you can point at (`ENGINEERING_STANDARD.md` §1); 12% on a stage that is no longer the
bottleneck is not that problem.

This decision was flagged to the user as a deviation from a stated preference *before* it
shipped, and **ratified** on the measurement.

**The known next rung, if the batch ever proves insufficient:** `-stay_open` remains the
correct escalation and is recorded as such in `PERFORMANCE.md`. It gets built when evidence
says the argfile batch is the bottleneck - decided by measurement then, not by machinery now.

**Status:** Settled. Performance contract and failure-mode rules in
`IMPLEMENTATION_STANDARDS.md` §8; the numbers in `PERFORMANCE.md` §1.

---

## D5. Accounts, activation, and the licensing server

**Decision (the maintainer, 2026-07-28).** truestill **requires a user account**. It supersedes D1.
Nothing is built yet: this is post-launch work, and the licensing server is new infrastructure
that gets its own research and design pass before any of it is written.

### 1. How it works

- **An account is created at activation**, against a **self-hosted licensing server** (Hetzner).
  Email is verified at signup.
- The app receives a **signed local token** and **runs fully offline thereafter**. Activation is
  **one-time**; there is no per-launch phone-home and no periodic revalidation.
- **Photo data never leaves the machine.** Nothing about a user's library - not filenames, not
  counts, not hashes - is transmitted at activation or afterwards.
- The public framing is **"an account for the software, never for your data."** That sentence is
  only honest while the previous bullet is true, so it is a constraint on the build, not copy.

**The account provides:** license and key management, update entitlement, and the upgrade path.

**Marketing:** periodic email to all registered users, free and paid, carrying upgrade offers.
Unsubscribe is honoured. **EU consent is captured at signup**, and GDPR obligations attach to
the account data from day one - it is personal data held on infrastructure truestill controls.

**Key-sharing control:** activation counts per account are monitored server-side.

### 2. Monetization

Recorded in full as **D6**; the shape is a perpetual licence plus paid annual updates.

### 3. What this changes in the product

The no-accounts invariant in `IMPLEMENTATION_STANDARDS.md` §1 is rewritten to match, and the
offline-verified-key mechanism described there becomes *token-after-activation* rather than
*key-with-no-server*. The capability seam (§2) is unaffected - it was always the right shape for
gating, whatever verifies the entitlement.

### 4. The engineering recommendation, recorded at the maintainer's instruction

**The recommendation was against requiring an account**, and it is recorded here rather than
dropped, because a decision is easier to revisit when the case against it is written down next
to it.

The argument: D1's rationale was not privacy sentiment, it was the **Audacity 2021 precedent** -
for this specific audience, self-hosting and data-hoarding users, an identity requirement
converts trust into forks. That audience is also the one most likely to notice that a local-first
photo tool now has a signup screen, and least likely to accept "the account is only for the
software" without checking. The reputational cost lands hardest at exactly the launch moment
when there is no track record to weigh against it.

There are also two concrete costs the design has to carry: **truestill now holds personal data**
(emails, activation records) with the GDPR duties, breach exposure and deletion obligations that
follow, and **the licensing server becomes a single point of failure for activation** - if it is
down, unreachable, or eventually shut down, new installs cannot activate. An offline key scheme
had neither property.

**The counter-arguments, stated fairly:** a perpetual-licence-plus-updates business genuinely
needs an entitlement record and a way to reach customers about renewals, and offline keys make
both awkward; one-time activation is a far smaller ask than a login-per-launch and is
commonplace in paid desktop software; and self-hosting the server keeps the data under
truestill's control rather than a third party's.

**Ruling: accounts are required.** The mitigations that make it defensible are already in the
design above and are binding, not optional: one-time activation, no per-launch phone-home,
**no photo data transmitted ever**, self-hosted infrastructure, honoured unsubscribe, and
explicit EU consent.

### 5. Before any of it is built

The licensing server is new infrastructure and gets its **own research and design pass**:
authentication, the **user database**, GDPR data handling (lawful basis, retention, export,
deletion), **backups**, and **uptime** - an activation endpoint that is down is a storefront
that cannot sell, so its availability target is a product decision rather than an ops detail. **Deliverable: an offline-activation fallback story**, decided in that pass - what a
user does when the server is unreachable, and what happens to activated installs if it is ever
retired. That question is the one most likely to be regretted if it is left until after launch.

**Status:** Settled as a decision, unbuilt. Supersedes D1.

---

## D6. Monetization: perpetual licence, paid annual updates

**Decision (the maintainer, 2026-07-28).** Supersedes the earlier "one-time Pro licence" sketch.
Post-launch; nothing built.

### 1. The model (Sublime Text / JetBrains shape)

- **Pay once, own that version forever.** A licence never expires and never stops working.
- **One year of updates included** from purchase.
- **Renewal at roughly 40-50% of full price** continues updates for another year.
- **Pricing figures are deliberately TBD post-launch** - set them against real adoption rather
  than a guess made before anyone has used the thing.

The property that makes this the right shape for truestill: **a lapsed licence still works.** A
tool that holds someone's photo library must never become a hostage to a missed renewal, and a
subscription that stops opening a library would contradict the custody promise the whole product
rests on. What lapses is *new versions*, not access to your own files.

### 2. Keys are signed, not generated

Licence keys are **Ed25519-signed**, with the **buyer's name and email embedded** in the payload.

Two properties follow, and both matter more than obfuscation would:

- **Keygen-proof.** A signature cannot be forged without the private key, so there is no
  algorithm to reverse-engineer. This is why signing beats any scheme built on a secret format.
- **Share-deterrent by identity, not by lockout.** A shared key carries the sharer's own name and
  email. That is a social deterrent rather than a technical restriction, which is deliberate:
  it costs an honest user nothing, and it never risks locking out someone who has paid.

Verification is local against the embedded public key. Combined with D5's activation-count
monitoring, this gives two independent signals about sharing without either one gating a
legitimate user mid-session.

### 3. Asking for money: visible, never gates

**The rule: truestill asks visibly and often enough to be heard, and never withholds function to
force the question.**

This comes from the maintainer's own twenty years as a free user of other people's software - *"no one
ever asked me to pay"*. The failure mode being designed against is not piracy; it is the honest
user who would happily have paid and was simply never asked.

The asks, all non-blocking:

- a note on the **about screen**;
- a **post-completion line** mentioning Pro after a run finishes - the moment the tool has just
  demonstrably helped;
- a **voluntary newsletter** signup on the site;
- **release notes that name** which additions are Pro.

**What is never done:** a nag on launch, a countdown, a modal that must be dismissed, a
degraded free experience, or any feature that stops working to make a point. A gate would
contradict D5's framing of an account "for the software, never for your data" - the same
instinct applies to function.

### 4. No trial. Free tier forever. (2026-08-01, revises the framing above)

**Decision.** truestill has **no time-limited trial**. There is a **free tier that does not
expire**.

The reasoning is specific to this product rather than borrowed from SaaS practice: **truestill
is a job, not a habit.** The user's real task - organise a lifetime of photos - is a *one-time
event*. A 14-day or 30-day trial is therefore not a taste of the product; it is **exactly long
enough to finish the job and leave**. The trial would hand over the entire value and then ask
for money for something the user no longer needs. A free tier that never expires at least keeps
the relationship alive for the part that recurs.

That sharpens the Pro question rather than answering it, so it is recorded as the open question
it is.

**OPEN: what does someone buy AFTER the big job is done?** Three candidate answers, none chosen:

1. **Sell what RECURS.** Free organises the library once; Pro keeps it safe over years - ongoing
   intake of new photos, backup verification, drive health. This is the answer that fits
   "one-time job" most directly: the job ends, the custody does not.
2. **Sell CONFIDENCE at the irreversible moment.** Both existing Pro candidates already have
   this shape - `BACKLOG.md` **(p)** "share safely" (metadata-stripping export, already marked
   PRO TIER) and **(m)** duplicate review with quality ranking. Each is *"I am about to do
   something I cannot undo"*, which is when people pay.
3. **Sell SCALE.** Free handles a normal library; Pro handles the hoarder's.

A fourth candidate shape, from market observation rather than principle: **meter by RATE, not by
feature.** FocusClean allows "100 photos free each month" - the core works *completely* and only
volume is limited. Recorded because it is **compatible with the boundary below in a way
feature-gating is not**: nothing is withheld, nothing is crippled, and the user can always
finish what they started at a slower pace.

**THE BOUNDARY, which does not move: do not cripple the core organiser.** If free cannot be
trusted with a user's photos, **Pro cannot either** - trust is the product, and a hobbled free
tier sells against the thing being sold. This also restates §3 above from the other side: §3
forbids withholding function to force the question; this forbids designing the free tier as the
withholding.

**The anti-pattern that defines the boundary more sharply than the boundary does.**
Photobucket locked users out of **their own photos** and then charged to retrieve them one at a
time. The "mass exodus of 2017" is still cited in reviews years later - the reputational damage
outlived the revenue by a decade. So the line is not merely *"do not cripple free"*:

> **Nothing behind the paywall may ever stand between a user and their own files.**
> Export, retrieval, and reading the catalog stay free **permanently**, whatever else Pro
> becomes.

**Price anchors - anchors, not conclusions.** Comparable shipping products, gathered 2026-08-01:

| Product | Model | Price |
|---|---|---|
| ImageSlip (sorts photos into folders) | pay-once | $5 |
| Gallery Sort | freemium, pay-once | $18 |
| ACDSee | licence | $60-150 |
| FotoStation | licence | $159-459 |

The previously recorded **$29-39** sits between the swipe-sorters and the professional DAMs,
which is the right neighbourhood for a custody tool. These are **anchors for judgement, not a
derivation of the price.**

**The research gap, recorded honestly.** Two searches for *users saying why they paid* returned
**vendor directories, not user voices**. So the price anchors above are real and the
**motivation evidence is not yet gathered** - what exists is inference from product listings,
which is not the same thing and must not be cited as if it were.

**The soak is the better instrument.** Real users asking real questions will show what they
would pay for far more reliably than inference from a listing. **The free/Pro split should not
be decided before then**, and pricing and the final split stay post-launch regardless.

**Status:** Settled as a decision, unbuilt. Supersedes the one-time Pro-licence sketch;
the capability seam (`IMPLEMENTATION_STANDARDS.md` §2) is where Pro features attach.
§4 revises the framing: no trial, free tier forever, and the free/Pro split deliberately open.

---

## D7. Source licence: Apache-2.0, open-core

**Decision.** The truestill source published in this repository is **Apache License 2.0**.
The commercial shape is **open-core**: the open tree is the product; paid Pro capabilities
(D6) attach through the capability seam (`IMPLEMENTATION_STANDARDS.md` §2) rather than a
separate closed codebase.

**What this binds:**

- Root `LICENSE` is the Apache-2.0 text; package metadata (`license = "Apache-2.0"`) matches.
- Copyright line: `Copyright 2026 Dinesh A`.
- No copyleft (GPL-family) dependency may be introduced into the published packages without an
  explicit superseding decision - Apache-2.0 + open-core is incompatible with that surprise.
- Open-core does **not** mean a free/crippled build and a proprietary build of the same tree.
  Pro is entitlement and gating (D5/D6), not a second source licence.

**Status:** Settled and current. Recorded here because the packages already shipped
`Apache-2.0` and the root `LICENSE` existed; the stance itself had not been written into this
file.

---

## D8. Content hash is SHA-256 - BLAKE3 is deliberately absent

**Decision.** The sole content hash is **SHA-256** (`hashlib`). There is no BLAKE3 dependency,
no dual-hash catalog column, and no user-facing algorithm toggle.

**Corrected rationale (2026-07-29).** An earlier recorded reason claimed BLAKE3 was rejected
because it is a compiled dependency that must build across platforms. That is **overstated**:
the `blake3` PyPI package ships prebuilt wheels for most environments and needs no Rust
toolchain for typical users. That argument is withdrawn.

**The measured reason, which is stronger** (`docs/preview-performance-profile.md`, historical
Wayanad '14 on `Photos/Archive` - now OFF LIMITS to re-run; 2,064 files, cold cloud-mount preview):

- SHA-256 ran on **22 of 2,064 files** (~1% after the size pre-filter) and offers about
  **1.03×** headroom if it went to zero.
- **exiftool is 74%** of that wall; unconditional perceptual hashing is most of the rest.
- A faster hash therefore optimizes the **1%**. It is the wrong axis.

Also: BLAKE3's headline speedup comes from **multithreading within a single file**, and it can
be slower than SHA-256 on inputs below ~1 MB. truestill already parallelizes **across files**
(`scan.compute_hashes`), which is the correct axis for this library-sized workload.

**Reasons that remain valid:**

- **One hash type in the catalog** - `files.sha256` / `file_copies` are keyed on a single
  algorithm. Introducing BLAKE3 would mean a dual-hash migration or a rewrite of identity.
- **No user-facing algorithm toggle** - one catalog column, one verification identity, no
  setting that splits a library's custody record.

**Status:** Settled. Short form in `IMPLEMENTATION_STANDARDS.md` § dependency inventory.

---

## D9. Launch on Windows and Linux. macOS builds but is not published.

**Decision (2026-08-01, maintainer's ruling).** truestill launches on **Windows and Linux only**,
with **no code-signing certificate purchased - zero spend now**. macOS **continues to build in
CI**: the lane stays, the tests stay, and nothing about macOS support is removed from the code.
It is simply not published.

**Why macOS is built but not shipped.** Gatekeeper blocks unsigned applications outright - not a
warning with a way through, a refusal - and the only way around it is the **$99/yr Apple
Developer account**. Shipping an unsigned `.dmg` would mean shipping something most users
physically cannot open. Dropping the lane instead would be worse: macOS support would rot
silently, and the cost of noticing would land on whoever eventually pays the $99 and finds the
platform has been broken for months. Building without publishing keeps it honest and cheap.

### What "unsigned" actually costs, per platform

Recorded because it is the whole basis of the ruling, and because "unsigned" is usually treated
as one condition when it is three different ones:

- **Linux: no gate at all.** Nothing to sign, nothing to warn about. AppImage and `.deb` install
  and run. This platform costs nothing and is not affected by any of the below.
- **Windows: SmartScreen shows "Windows protected your PC" / unrecognized app**, with a **hidden
  "Run anyway"** behind *More info*. It is **reputation-based per file**, and it **clears** once
  enough people download and run that file - one maintainer reports the threshold falling
  somewhere between a few dozen and a few hundred downloads. It is a **friction that expires**,
  not a block and not a permanent state.
- **Signing does not fully remove it either.** A standard (non-EV) certificate still warns until
  reputation accrues; it only accrues *faster*. Only an **EV certificate** or **Microsoft Store**
  distribution removes the warning immediately. So the honest comparison is not
  "warning vs no warning" - it is "warning for a while vs warning for a shorter while, for
  money".
- **This is a normal position, not a corner.** Inkscape and many established open-source projects
  ship unsigned. The precedent is broad enough that it carries no signal about product quality.

### The cheap paths back, so they are not re-researched

Recorded with what is **verified** separated from what is **reported**, because the point of
writing them down is that the next person does not repeat the search:

- **Azure Artifact Signing** - Microsoft's own service, and **the one to evaluate first** if
  signing is ever bought. **Note the rename:** it was called *Azure Trusted Signing* and is now
  **Azure Artifact Signing**; searching the old name in future will find stale pages. Verified
  2026-08-01: **$9.99/month** for the Basic tier (5,000 signatures/month, one certificate
  profile), **$99.99/month** for Premium - so **~$120/yr**, which confirms the figure this
  ruling was made on. Reported, not verified here: **no hardware token**, and direct **GitHub
  Actions** integration. Cheaper than the $300-700/yr commonly quoted for EV certificates.
  Caveat for whoever evaluates it: Microsoft's own pricing page rendered its tiers as
  placeholders when fetched directly, so confirm against the Azure portal for the actual region.
- **Microsoft Store with an MSIX** - **Microsoft re-signs automatically**, so users never see
  SmartScreen at all, and the certificate costs nothing. Worth evaluating **on its own terms
  rather than as a signing workaround**, because it also changes distribution: discovery,
  updates, and the payment path all move, and `D6`'s perpetual-licence model would have to be
  reconciled with Store policy before this is a real option.

### Requirement carried to the launch page

**Windows users must be told what SmartScreen will show, and why, BEFORE they download.** Plain
language, on the download page, above the button - not in a FAQ and not after the fact.

The reason this is a requirement rather than a nicety: truestill is sold on **trust with
someone's irreplaceable photos**. A user who meets an unexplained "unrecognized app" warning on
*that* product draws exactly the wrong conclusion, and they draw it at the moment they were about
to install. Telling them first converts the same warning from **alarming to expected** - and a
warning the page predicted accurately is evidence the product is what it says it is.

**Status:** Settled. **This unblocks `(aad)`**: the bundler decision can be made for Windows and
Linux alone, with no signing step in the pipeline.

---

## D10. Python 3.14 is deferred, and the CI leg is evidence rather than a target

> ## ⚠ REVERSED 2026-08-22. THE DEFERRAL RESTED ON A NUMBER NOBODY CHECKED.
>
> **The wrong number:** *"3.13 is in full bugfix support for four more years"* / *"October 2029"*.
> **The right one:** October 2029 is 3.13's **security** EOL. The devguide's *"end of life"*
> column is *"five years after a release"*, and its status key reads: **"Security: After two
> years… only security fixes are accepted and no more binaries are released."** 3.13 was released
> 2024-10-07, so **bugfix support ends around October 2026 - about six weeks from this
> correction**, not four years.
>
> ⚠ **The reasoning below was sound; its premise was false.** Every other clause holds - the
> alternatives were correctly judged, `context_aware_warnings` really is `0`, `(aey)` really was
> the blocker. What failed is that *"no support pressure"* was derived from a figure read off the
> wrong column. **That is the fifty-eighth member from the other direction**: the claim was
> written down, which is why it could be checked and found wrong. A deferral held in someone's
> head would have survived.
>
> **What made the reversal a bump rather than a gamble** is that the evidence had been
> accumulating since D10 itself ordered it: cp314 wheels on all three platforms for every pin,
> `uv.lock` unchanged and already admitting 3.14, and **the 3.14 legs green on every run since
> they were added**. The condition every 2026 source names for an existing project - *upgrade when
> your dependencies are ready* - was measured met before it was acted on.
>
> **Superseded by D13.** The text below is left exactly as written.


**Decided 2026-08-21**, after research rather than preference. The upgrade was raised as the first
non-defect change in weeks; it is not blocked by anything, and nothing argues for it.

### Nothing breaks - that is not the same as a reason to move

Every runtime and dev dependency resolves on 3.14 and ships **cp314 wheels on all three lanes**
(numpy, pillow, pillow-heif, scipy, pywavelets); the rest are pure-python or `py3-none-<platform>`.
PyInstaller has supported 3.14 since **6.15.0 (2025-08-03)** and declares `<3.16,>=3.8`. The whole
suite passes locally on 3.14.4 (2,664 passed). `uv.lock` already admits 3.14 unchanged.

### Why we are not moving

- **No support pressure.** 3.13 is in *bugfix* status until **October 2029**
  ([devguide](https://devguide.python.org/versions/)).
- **3.15 lands 2026-10-01**, so moving now buys about six weeks of being *n-1*.
- **Nothing in 3.14 is wanted.** Free-threading is unused; `pathlib.Path.copy/move` would mean
  rewriting safety-critical `safe_copy.py`; the hot path is C (`hashlib`, Pillow decode).
- ⚠ **`sys.flags.context_aware_warnings` is `0`** on non-free-threaded 3.14 - measured. The
  contextvar `catch_warnings` does **not** arrive by upgrading, so `(aev)`'s `decode_noise` is
  necessary on both versions. **The upgrade fixes nothing we have fixed**, and must never be
  justified by it.
- §13 prefers boring technology when it is sufficient. 3.13 is sufficient.

### Two things 3.14 would change, and one of them is a defect

- **`multiprocessing` defaults to `forkserver` on Linux** (was `fork`) - measured on both
  interpreters here. `--pool process` is a user-facing flag, so its Linux behaviour changes.
  `scan.py` already passes `initializer=`, so it is correct **by design, not by luck** - it was
  written for spawn. `verify.py`'s pool hashes only and needs nothing.
- ⚠ **`(aey)`**: `Path.is_dir()`/`exists()`/`is_file()` stop raising on `EACCES`, so
  `path_probe.probe_dir` would report an unreadable folder as **missing and creatable** - the
  module's whole purpose inverted - and its guard **skips rather than fails**. The concrete
  blocker. ⚠ **Corrected 2026-08-21 after grepping rather than assuming: it is FIVE sites, not
  one.** `destinations/local.py:113-118` deliberately raises and would stop; `date_rescue.py:280`
  and `drive_adoption.py:167` each carry a comment stating the rule 3.14 breaks (*"cannot look,
  which is not 'nothing there'"*, *"not evidence either way"*). The deletion path (`reclaim.py`)
  was checked and **fails safe on both versions**. 3.14 did not invent this: its `is_dir()` is
  `return os.path.isdir(self)`, and `os.path` has always swallowed `OSError` - pathlib was the
  outlier we relied on. `Path.stat()` still raises on both and is the remedy.

### What moves the decision

Any one of: **3.15 ships and settles** (3.13 becomes *n-2*); a dependency drops 3.13; or a defect
we cannot fix on 3.13 is fixed upstream. `(aey)` must be closed first regardless.

### The CI leg

3.14 is a `continue-on-error` matrix dimension of the **one** check job - never a second lane.
⚠ **It reports green through `(aey)` today**, which is exactly why it is evidence and cannot be
promoted to a gate until that entry closes.

**Status:** Settled until one of the conditions above fires. **No tag was cut**: the release lane
is exercised with `workflow_dispatch` + `dry_run=true`, and a `v*` tag is the *publish* trigger,
not a dry run (`release.yml:283`).

---

## D11. Stay on mypy - and the condition that would change it, restated so it can fire

**Decided 2026-08-21**, replacing a trigger in
[`frontend-and-shell-standard-research.md`](frontend-and-shell-standard-research.md) that named
the wrong tool. That file is a record and keeps its original wording; this is the live version.

**The decision is unchanged: mypy strict, in the gate.** The reason is not that the alternatives
are bad - two of them are better on the axis they compete on - it is that **the axis does not
matter here**. mypy is invisible in every lane's wall clock (`PERFORMANCE.md` §5.1: Windows is
1,638 s of summed test time, ubuntu 121 s; mypy appears in neither). A checker 10-50x faster
saves nothing a person can perceive.

### What actually changed, recorded so the decision rests on current facts

| | May 2026 (as recorded) | 2026-08-21 |
|---|---|---|
| **Pyrefly** | *"58% and 87.8%, disputed"* | **1.0 stable since May 2026**, ~92.2% conformance, deployed at Meta (Instagram, PyTorch, JAX) |
| **`ty`** | *"15% and 53.2%", beta, no plugins* | **still alpha** - not for production CI |
| **mypy** | the incumbent | ~59.6% conformance |

⚠ **The old trigger read *"revisit when `ty` reaches stable 1.0"*, and `ty` is the one that did
not move.** A condition aimed at the wrong subject is a condition that never fires, which is worse
than none: it looks like the question is being watched.

### The trigger, restated

Revisit when **any** of these is true, and the first two name Pyrefly because Pyrefly is what moved:

1. **mypy becomes visible in a lane's wall clock** - the original and still the only reason that
   would force the change on its own.
2. **Pyrefly ships something mypy cannot do that this repo needs**, rather than doing the same
   thing faster. Conformance percentage is not that; a rule we want and cannot express is.
3. **mypy stops being maintained**, or drops a Python version this project runs.

**Cheap and unblocked meanwhile:** a second checker in **advisory** mode produces evidence instead
of argument, the way the 3.14 lane does for the interpreter (D10). Nobody has run it.

**Governance note, carried forward:** uv, ruff and `ty` are all Astral, and Astral joined OpenAI in
March 2026. Three of four toolchain tools under one owner is worth knowing - not a reason to act,
since all are permissively licensed and forkable, but a reason not to add the fourth without
noticing.

---

## D12. Aceternity UI is refused - recorded because it was decided and never written down

**Decided in conversation before 2026-08-21; written down 2026-08-21 after an audit found it was
nowhere in the repository.** `grep -ri aceternity` returned nothing. The decision was being
honoured by memory alone.

**Refused on two grounds, both verified rather than remembered:**

1. **It requires Motion (Framer Motion).** Aceternity is a Tailwind **+ Motion** library; the
   animation dependency is not optional to it. Truestill's UI has no animation requirement, and
   `(adi)`'s React island exists to render a result grid, not to move.
2. **The bundle cost is real and is paid by a local app that has no reason to pay it.** Motion is
   ~34 kB gzipped standalone and adds **~125 kB** in practice; trimming to ~4.6 kB needs explicit
   `LazyMotion` configuration that is easy to skip and easy to regress. The app is served from
   localhost by the user's own machine, so the cost is startup and memory rather than network -
   which makes it cheaper to dismiss and no less real.

**What this does NOT rest on.** Not taste, not "we do not need a component library" - shadcn
components are already in `src/components/ui/`. The refusal is specific to a library whose value
is animation, in a product with none.

**Status:** Settled. Revisit only if the product acquires a genuine motion requirement - and then
the question is Motion itself, not Aceternity, since Aceternity is a set of components built on it.

---

## D13. Python 3.14 is adopted - and D10's deferral was correct reasoning from a wrong number

**Decided 2026-08-22**, reversing [D10](#d10-python-314-is-deferred-and-the-ci-leg-is-evidence-rather-than-a-target).
D10 is corrected in place and left standing; this is what replaced it.

### Why the deferral fell

D10's P1 said *"3.13 is in full bugfix support for four more years"* and cited **October 2029**.
That is 3.13's **security** EOL. The devguide's *"end of life"* column is *"five years after a
release"*, and its status key reads: **"Security: After two years… only security fixes are
accepted and no more binaries are released."** 3.13 shipped 2024-10-07, so **bugfix support ends
around October 2026**.

⚠ **"No more binaries are released" is the operative half for this project**, which installs
interpreters with `uv python install` and ships a PyInstaller build. A security-only branch stops
producing the artefacts the whole toolchain consumes.

⚠ **The reasoning was sound; the premise was false.** Everything else in D10 held on re-reading:
the alternatives were correctly judged, `sys.flags.context_aware_warnings` really is `0`,
`(aey)` really was the blocker and is now closed. **That is the fifty-eighth member from the other
direction** - a written claim, checkable, and therefore caught. A deferral held in conversation
would have quietly expired.

### What made this a bump rather than a gamble

D10 ordered the evidence and the evidence arrived: cp314 wheels on all three platforms for every
pin, `uv.lock` needing **no change** to admit 3.14, and the **3.14 legs green on every run** from
the day they were added. The relock moved **no package version at all**. The condition every 2026
source names for an existing project - *upgrade when your dependencies are ready* - was measured
met before it was acted on.

### What actually changed, and what did not

- ⚠ **`multiprocessing` defaults to `forkserver` on Linux**, so `--pool process` behaves
  differently. Measured on the format corpus: **thread and process agree exactly on both
  interpreters**, and exact deduplication was identical across all four runs. `scan.py` was
  correct for forkserver by design, having been written for spawn.
- ⚠ **One extra near-duplicate** - 262 on 3.13, 263 on 3.14. Filed as `(aff)`; the mechanism is
  **not isolated**, and a near-duplicate is kept and flagged rather than removed, so the effect is
  one extra row in a review list.
- ⚠ **PEP 758 is deliberately NOT adopted yet.** Moving ruff's `target-version` to `py314` makes
  the formatter rewrite `except (A, B):` into `except A, B:` across **25 files** - syntax that is
  a `SyntaxError` on 3.13. That is a language migration, and bundling it into the floor bump would
  have made the bump unrevertible. `target-version` stays `py313` until it gets its own commit.

**Status:** Adopted. The next question is 3.15 (2026-10-01), and the machinery for judging it is
already in place: an allowed-to-fail matrix leg, which is why it was kept rather than deleted.

