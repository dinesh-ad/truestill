# (ake) WEBKIT REPORTS `backdrop-filter` AS SUPPORTED AND PAINTS NOTHING

*Body of entry `(ake)`, under **Rulings**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(ake)** Measured 2026-09-04 (P219), before a glassmorphism direction was specified rather than
  after a screen was built on it.

  ## MEASURED

  A hard checkerboard backdrop - high frequency, so a blur must average it toward flat grey while
  no blur keeps the black/white extremes. Sampled inside the panel, `spread = max - min`:

  ```
  webkit    CSS.supports -> true   computed -> blur(14px)   spread 229 -> 229   NO BLUR
  chromium  CSS.supports -> true   computed -> blur(14px)   spread 229 ->   1   BLUR PAINTS
  ```

  **Headed WebKit gives the identical result**, so it is not a headless artifact. Playwright
  WebKit **26.5**. Chromium collapses the checkerboard to flat `#8c8c8c`; WebKit leaves it
  untouched.

  ⚠ **A first probe could not tell the difference and is recorded because the method matters**: it
  used a smooth `linear-gradient` backdrop and both engines returned **identical pixels**. Blurring
  a low-frequency image returns that image. The test only works with high-frequency content.

  ## 🔑 WHAT IT INVALIDATES

  **`@supports (backdrop-filter: blur(1px))` is a guard that cannot fire here.** It answers `true`
  on the engine that renders nothing, so the standard progressive-enhancement pattern reports
  success and ships a surface that is not there. `CSS.supports` and `getComputedStyle` both agree
  with it - the property is parsed, stored and reported; only the paint is missing.

  **And the stake is not hypothetical.** `ci.yml` records it: *"WebKit is what the Tauri shell
  renders in on Linux and macOS, so a chromium-only lane said nothing about the shipped engine."*
  Two of three platforms. A glass design guarded by `@supports` would have looked correct in every
  test and in Chromium, and shipped flat to every Linux user.

  This is `ENGINEERING_STANDARD.md` §4's cry-wolf class expressed in CSS rather than in a test: a
  check that returns the answer you want and covers nothing.

  ## THE CONSEQUENCE, ALREADY TAKEN

  `docs/design-system.md` is **solid-first**: every glass surface must be complete and legible
  with `backdrop-filter` doing nothing, and the blur is added on top. That makes WebKit's gap
  **free** rather than a compromise, and it makes the WebKit half of the browser lane the
  fallback's own test.

  🔑 **The reason the direction survives at all**: the glass *look* is translucency, a hairline and
  a shadow over a gradient. Measured above - over a smooth gradient the blur contributes almost
  nothing - and the preview's own glass is `bg-white/70 border-white/60 shadow-xl backdrop-blur-2xl`
  over `from-rose-50 via-white to-orange-50`, a smooth backdrop. **The appearance never depended on
  the property WebKit ignores.**

  ## ⚠ WHAT THIS IS NOT

  **Playwright's WebKit is a custom build**, not Safari and not WebKitGTK as a distribution ships
  it. So this is **indicative, not proof**, about the engine inside a shipped Tauri app - and
  Safari on macOS has supported `backdrop-filter` since Safari 9, so the macOS side may well paint
  it.

  **It is proof about our lane**, which is enough on its own: any assertion about a blurred surface
  is untestable on the webkit half, and that half is the one `ci.yml` treats as the shipped engine.
  The solid-first rule makes the uncertainty cost nothing, which is the main argument for it over
  and above the measurement.

  ## RELATED

  `docs/design-system.md` §5 (the rule this produced), `research/organize-preview/` (the style
  reference), `(ajm)` (the last instrument defect that would have corrupted a measurement).
