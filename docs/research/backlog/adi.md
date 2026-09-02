# (adi) REACT + SHADCN MIGRATION - PLANNED, GROUNDWORK LANDED, NOTHING MIGRATED.

*Body of backlog entry `(adi)`, under **Internal / tooling**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adi) REACT + SHADCN MIGRATION - PLANNED, GROUNDWORK LANDED, NOTHING MIGRATED.** Recorded
  2026-08-14. Plan and evidence: [`react-migration-plan.md`](../../react-migration-plan.md).
  **The backend does not move**: `service/` stays the facade, `/api/*` stays the boundary, and a
  component holding organize logic is a failed migration however it looks.

  Landed already, and each is a prerequisite rather than a head start: tokens are out of
  Tailwind's namespaces `(fa99e58)`, the browser lane covers WebKit `(9cdd85d)`, and `@theme
  inline` is **verified by build** to leave our `[data-theme]` dark mode intact.

  **Measured, not estimated: 3 of 55 e2e files touch `app.js` internals.** The other 52 assert on
  rendered words, so the existing suite is the acceptance test for every migrated screen rather
  than something to rewrite after.

  ⚠ **One hole remains and it is not closed by this work.**
  `test_the_bundled_family_is_what_rasterises` needs CDP and is therefore blind on WebKit - the
  engine the shell uses on two of three platforms - which is exactly the check a component library
  arriving with its own font stack would need.

  The CSP question is **settled**: a real Tauri 2 build shows a static
  `connect-src http://127.0.0.1:*` reaches a sidecar on an ephemeral port, so none of the
  fixed-port / port-range / route-through-Rust workarounds is needed. `localhost` and `127.0.0.1`
  are distinct host-sources there, which is the part that would have failed silently.
