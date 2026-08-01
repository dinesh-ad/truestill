# Security Policy

## Reporting a vulnerability

**Please report privately, not in a public issue.**

Use GitHub's private vulnerability reporting: go to the
[Security tab](https://github.com/dinesh-ad/truestill/security/advisories) → **Report a
vulnerability**. That opens a private advisory visible only to you and the maintainers, and
lets us work on a fix before anything is public.

If you cannot use GitHub advisories, open a public issue saying only that you have a security
report and asking for a private channel - **no details in the issue itself.**

**What to include:** what you did, what happened, and why you think it is a security problem.
A minimal reproduction is worth more than a long report. The output of `truestill --version`
and your OS help.

**What to expect:** an acknowledgement that a human has read it, and honest updates as it is
looked at. This is a small project, so please do not expect same-day turnaround. If a report
is valid we will tell you, fix it, and credit you in the release notes unless you would rather
we did not.

**No bug bounty.** There is no payment, and none is implied. Reports are welcome regardless.

## Scope - what truestill actually exposes

truestill is a local-first tool. It runs entirely on your machine, sends **no telemetry**, and
transmits **nothing about your library** - not filenames, not counts, not hashes. That removes
most of the surface a web application has, and it means the interesting security questions here
are different.

> **Planned, not yet built:** a one-time account activation against a self-hosted licensing
> server (`docs/DECISIONS.md` D5). When it ships, the licensing server and the activation
> exchange become part of this scope, and this section will be rewritten to say so. Nothing in
> the product contacts a server today.

**In scope, and genuinely worth reporting:**

- **The local web UI (`truestill-app`).** It binds `127.0.0.1` only and guards every request
  with a per-session token plus `Host` and `Origin` checks (`truestill_app/security.py`).
  Anything that gets past that - a DNS-rebinding path, a token leak, a route that skips the
  guard, a way for a web page you visit to reach the API - is a real finding.
- **Path handling.** Anything that makes truestill read or write outside the source and
  destination you pointed it at, including via crafted filenames or archive contents.
- **Data-destroying behaviour.** truestill's core promise is that it copies and never destroys.
  Any path that relocates, deletes or overwrites an original outside the three documented,
  opt-in exceptions - `--move` and `reclaim` (both gated on re-hashing a proven second copy),
  and `--in-place` (moves by rename, reversible via `truestill undo-organize`) - is a
  **serious** bug. Report it as one. So is any way to reach one of those three *without* its
  confirmation, or to defeat the gate that protects it.
- **Metadata parsing.** Crashes or worse when handling malformed media or Takeout sidecars.
- **A dependency vulnerability we have missed.** CI runs `pip-audit` against the locked set,
  but it only knows about published advisories.

**Out of scope:**

- Anything requiring an attacker who already has your user account on your machine. truestill
  reads and writes files as you; someone who is already you does not need it.
- The absence of encryption at rest. truestill writes ordinary files to ordinary folders, on
  purpose - you can read your library with any file manager, forever, without truestill.
- Denial of service by pointing truestill at a pathological library. It is a tool you run, not
  a service that accepts untrusted input.

## Supported versions

Pre-1.0 and not yet published. Only the current `main` is supported; there are no backports.
This section will be replaced with a real support table at the first release.

## Handling of your files

Reports should never include your actual photos or personal data. If a reproduction needs a
file, please construct or strip one first - and if you believe the *content* of a file is
essential to the report, say so and we will agree a way to handle it before you send anything.
