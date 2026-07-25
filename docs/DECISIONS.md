# vaeon - Product Decisions (binding, with rationale)

Durable product decisions and the reasoning that produced them. Unlike `BACKLOG.md` (approved
but *unbuilt* work), entries here are **settled stances** that govern what vaeon is - kept so the
rationale outlives chat history. Where a decision is also a binding engineering invariant, the
short form lives in `IMPLEMENTATION_STANDARDS.md` and this file holds the full "why".

---

## D1. No accounts, no required telemetry - permanently

**Decision.** vaeon collects **no user accounts** and **no required telemetry**, permanently.
There is no login, no sign-up, no device identifier, no phone-home, and no usage beacon compiled
into the product. This is not a launch-phase posture that relaxes later; it is a permanent
property of what vaeon is.

**Scope - what this forbids inside the product:**

- No account creation or authentication of any kind to use vaeon (free **or** Pro).
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
3. **Privacy-friendly site analytics on `vaeon.app`** - a Plausible-class analytics tool: **no
   cookies, no personal data, no cross-site tracking**. Page-level aggregates only.
4. **Purchase records for Pro customers** - name / email / country, held by the **payment
   provider** as the record of a transaction. This is a payment record, not product telemetry:
   the software never sees or sends it, and it exists only because someone chose to buy.

These four give a truthful picture of adoption and revenue without a single byte of behavioral
telemetry leaving a user's machine.

### Rationale - the Audacity 2021 precedent

In 2021 Audacity's new steward proposed **opt-in** telemetry. The reaction from exactly the kind
of privacy-conscious, self-hosting audience vaeon serves was decisive: roughly **3,500 downvotes**
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
- **Self-hosted** - reports go to infrastructure vaeon controls, never a third-party SaaS.
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

**Status:** Settled. Binding invariant recorded in `IMPLEMENTATION_STANDARDS.md §1`; Pro-tier
seam in `§2`. Related parked Pro-tier ideas are tracked in `BACKLOG.md`.
