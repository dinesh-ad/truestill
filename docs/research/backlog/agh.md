# (agh) `LocalGuard` MAKES FORGETTING THE TOKEN IMPOSSIBLE AND UN-EXEMPTING INVISIBLE.

*Body of backlog entry `(agh)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(agh)** Recorded 2026-08-23, found while answering *"is the session token enforced on every
  route, or only carried in the launch URL?"*. **The answer was: enforced, and well.** This is the
  one part of it that can regress without anything noticing.

  ## What is already right, so the entry is not misread as an alarm

  The token is ASGI middleware, not a per-route check: `app.add_middleware(LocalGuard, token=token)`
  (`server.py:1012`) wraps the whole app including the `/static` mount (`server.py:1010`). **A
  new route cannot forget it** - there is nothing per-route to forget. `security.py:84-94` checks
  Host (421), Origin (403) and the token with `secrets.compare_digest` (403), and the refusal names
  the session-link *file* rather than the token (`security.py:54-56`).

  The one exemption, `/static/` (`security.py:85-86`), is inert and was checked rather than
  assumed: the mount serves the package's own assets, `app.js` reads `window.TRUESTILL_TOKEN` - a
  global defined by the **protected** HTML at `server.py:186` - and the `token` matches in
  `tokens.css` are **design tokens**. You need the token to get the token.

  ## The gap

  **No test enumerates the exemption list.** Coverage today is per-route and per-condition:
  `test_server.py:20` (missing token), `:33` (bad host), `:39` (cross-origin), `:44` (static is
  exempt), and the best of them, `test_thumb_route.py:115`, whose docstring has the right instinct
  - *"asserts the new route is on the guarded side of that line rather than trusting that it is."*

  Every one of those pins **one** route or **one** condition. Nothing pins that
  `_reject`'s exemption list is **exactly `/static/`**. A second `startswith` added there - for a
  health endpoint, a favicon, an asset path that moved - would be caught by nothing, and it is a
  two-line change that looks harmless in review.

  🔑 **The asymmetry is the point.** The middleware makes the *common* mistake structurally
  impossible and leaves the *rare* one completely unguarded, which is the shape that survives
  longest: everyone knows the token is enforced, so nobody re-reads the thing that enforces it.

  ## The pattern to copy already exists

  `test_every_job_declares_whether_it_mutates.py` walks the routes and asserts a property of each,
  and it carries the floor that makes such a scan honest (`:63`):

  ```
  assert len(declared) >= 12, f"only {len(declared)} routes were read; the scan is broken"
  ```

  **That floor is the load-bearing half** and must be copied with it: a route scan that finds
  nothing passes silently, so it has to assert it found something before asserting anything about
  what it found. There are 50 routes in `server.py:818-869` today.

  ## SHAPE, NOT DECIDED

  Two candidates, and they guard different things:

  - **Enumerate `app.routes` and assert each rejects a tokenless request.** Direct, and it would
    catch a route mounted outside the middleware as well. Costs a request per route.
  - **Assert the exemption list itself** - that `_reject` exempts exactly one prefix. Cheaper and
    more precise about what can regress, but it pins an implementation detail rather than the
    property.

  The first is probably right, with the second as a cheap addition. Not chosen here.

  ## Why it is worth a letter at all

  A localhost port is reachable by any local process - that is the standing cost of a Python
  sidecar over local HTTP rather than an in-process channel with no port. The token is what makes
  that acceptable, so *"which requests skip the token"* is a question the repository should be able
  to answer from a test rather than from a reading.

  ## RELATED

  `security.py` and its module docstring (DNS rebinding, why not a cookie), `(aad)` (the desktop
  app this hardening exists for).
