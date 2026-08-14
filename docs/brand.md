# Truestill brand identity

Recorded 2026-08-01. **This is the reference for what the mark IS; §6 governs which surfaces may
use it.** Read §6 before wiring anything new in - most of the icon set belongs to a landing page
rather than to a localhost tool.

> **This line said "nothing here is wired into the product yet" until 2026-08-13, and it had been
> false for a week.** The wordmark, the pillar T and `#4C63C4` are all shipped; the `.deb` and the
> Windows installer carry the icons. A sentence asserting a **machine state** expires the moment
> somebody changes the machine, and nothing can notice - `ENGINEERING_STANDARD.md` §4, the
> thirty-second member. Every clause below states **intent**, which stays true, or carries its own
> date. Where a rule was reversed, the reversal is annotated in place rather than swept: the dated
> notes are the record and are not to be deleted.

The product name is **Truestill**, capitalised, wherever a person reads it. The import package
stays `truestill_core`, the command stays `truestill`, and the app entry point stays
`truestill-app`: those are identifiers, and lowercase is right for all three. See
`app_paths.APP_NAME`, which carries the same distinction for the OS data directory.
**Enforced on the surfaces a person reads** by `scripts/check_product_name.py` (`make check`),
which skips code, identifiers and `truestill <subcommand>` invocations - this paragraph is the
source it enforces, so change the rule here first.

---

## 1. Wordmark - MONOSPACE (this heading said "serif" until 2026-08-13)

**The rule: the wordmark is `Truestill.` in `var(--family-mono)` with the accent dot.** The serif
sheet below is kept because it is the record of what was authored and why it was reversed - see
the 2026-08-05 note - but the heading claimed the superseded answer, so a reader who stopped at
the heading got the wrong one. The CSS immediately below is a **colour and proportion reference
only**, not a specification of the shipped mark.

*Original sheet:* the word **Truestill**, set in a serif, filled with the indigo gradient below.

```css
.truestill-logo {
    font-family: 'Georgia', serif;   /* PLACEHOLDER - see the warning below */
    font-size: 72px;
    font-weight: bold;
    letter-spacing: -0.02em;
    background: linear-gradient(90deg, #4C63C4 0%, #2A3B8C 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    color: transparent;
    display: inline-block;
}
```

> **THE MONOSPACE FACE IS BUNDLED, 2026-08-05.** `--font-mono` now leads with **DejaVu Sans
> Mono 2.37** (Book + Bold), shipped in `truestill-app/static/fonts/` with the Bitstream Vera
> notice beside it. The old stack named five faces and none exists on a stock Linux box, so the
> wordmark and every path, count and hash resolved to a different typeface per OS. Chosen on
> measurement, not taste - see `IMPLEMENTATION_STANDARDS.md` §7. **Never subset, never
> `local()`.** The wordmark's `--weight-semibold` resolves to the real Bold; no SemiBold ships.

> **AUTHORED 2026-08-04. Artwork lives in `brand/`; provenance and licence in
> `brand/PROVENANCE.md`. What follows is the original sheet, kept as the source of the palette.**
>
> **⚠ REVERSED 2026-08-05 for the WORDMARK ONLY.** The rail wordmark is `Truestill.` in
> `var(--font-mono)` again, with the accent dot - which is what `ui-v2-research` §2 argued for:
> monospace is the product's type signature, every path, count and hash is set in it, and the
> wordmark heads that system. A serif mark took the wordmark out of the one thing it was chosen
> to lead. The Georgia reasoning below still holds and is why no serif *font* is used; what
> changed is that the answer is not a serif at all.
> **The gradient was tried on the rail and rejected on evidence:** both stops clear AA there
> (9.17:1, 6.04:1), but across nine characters at 18px the shift is imperceptible and it
> swallows the accent dot, whose colour is the gradient's own high stop.
> **The MONOGRAM and the icons are unchanged** and still Libre Caslon.
> **Orphaned by this, kept deliberately:** `brand/wordmark-light.svg` and
> `brand/wordmark-dark.svg` now have no consumer. They are NOT deleted - the website header may
> still want a set wordmark, where a serif at size is a different question from a serif at 18px
> in a rail, and the monogram question is still open.
>
> - **Outlined from Libre Caslon Text (SIL OFL 1.1).** Artwork is *not* subject to the OFL - OFL
>   condition 5 and OFL-FAQ 1.13. No licence file required; no attribution required.
> - **Not Georgia.** It cannot be redistributed in any format, outlines included.
> - **Superseded: DejaVu Serif Bold**, used briefly in `c7c923e`. Wrong for the brief - a
>   low-contrast slab, not a high-contrast old-style.
> - **Three marks, not one:** wordmark, TS monogram for the 64px rail, and the **pillar T alone**
>   for 16px, where TS closes up. The ICO carries the T at 16/24 and TS above.
> - **The gradient below is for a LIGHT ground.** On the dark rail `#2A3B8C` measures **1.81:1**;
>   the dark variant is authored separately as `#A9B6F0` -> `#7D90E6`.
> - **Inline SVG is a conscious exception** to the "no SVG" line in the UI inventory, which was
>   about icon libraries. Authored assets, no library, no request.

> **Georgia is a placeholder, and the shipped wordmark must be a vector.**
> Georgia is absent on most Linux systems, so the CSS above falls through to whatever the
> platform calls `serif` - DejaVu Serif, Liberation Serif, Times, or something else again. The
> letterforms, widths and therefore the whole shape of the word differ per machine, which is
> exactly what a wordmark cannot do. It is also not a licensing question that gets solved by
> shipping a webfont: a logo is a fixed shape, so it should be **an SVG with outlined paths**,
> not text rendered in a font at all. Treat the CSS as a colour and proportion reference.

## 2. Colour

| Token | Hex | Use |
|---|---|---|
| Indigo, light end | `#4C63C4` | gradient start (`0%`, left) |
| Indigo, dark end | `#2A3B8C` | gradient end (`100%`, right) |

Gradient: `linear-gradient(90deg, #4C63C4 0%, #2A3B8C 100%)` - horizontal, light to dark.

The supplied page also sets `msapplication-TileColor` and `theme-color` to `#ffffff`. Those are
**chrome colours for a web page**, not brand colours, and they are listed here only so nobody
mistakes them for part of the palette.

## 3. Icon - the pillar T (the TS monogram is RETIRED)

**The rule: there is one mark, the pillar T.** `703e3b1` replaced the monogram with it everywhere,
and `index.html` says why in the markup: *"there is no TS in this product"*. The mark must stay
legible on a **light** and a **dark** ground, which is what the two authored variants are for; the
dark one is not an inversion of the light one.

> **Superseded 2026-08-05, kept as the record.** This section required a **TS monogram** in the
> indigo gradient, in light and dark variants. It was authored, shipped, and then withdrawn: TS
> closes up at 16px, and the product has one mark rather than a family. The rail renders the
> pillar T inline from `brand/pillar-t-geometric-noflute.svg`.

## 4. The icon set, by filename and size

This is the set the supplied page links, which is the full web-facing set. **See section 6: not
all of it applies to truestill.**

| File | Size | Format | For |
|---|---|---|---|
| `favicon.ico` | multi-size (16, 32, 48) | ICO | legacy and Windows shortcuts |
| `favicon-16x16.png` | 16x16 | PNG | browser tab |
| `favicon-32x32.png` | 32x32 | PNG | browser tab, retina |
| `favicon-48x48.png` | 48x48 | PNG | Windows site icon |
| `apple-touch-icon.png` | 180x180 | PNG | iOS home screen |
| `mstile-144x144.png` | 144x144 | PNG | Windows tile |
| `site.webmanifest` | n/a | JSON | PWA metadata |

## 5. Where the assets live, and what they are for

**`brand/` is the one directory for authored artwork, and it is the source every consumer reads
from.** Provenance and licence: `brand/PROVENANCE.md`. The rule that decides what belongs here is
`brand/README.md`'s, not a file list - a list goes stale the day something is added.

> **This section said "None of the files in section 4 are in the repo yet" until 2026-08-13.** It
> was written when the identity existed only as HTML and CSS, and it stopped being true when the
> artwork was authored (`0ba93b7`, `703e3b1`) without anything to notice. Same failure as the
> header above, one section down: it described a **state** rather than a **rule**.

Committing artwork is not a new precedent: the repo already tracks binaries
(`docs/qa-screenshots/*.jpg`, the video fixture). The rule that matters is the existing one -
**generated media never goes in git**; brand artwork is authored source, not generated output.
The icon PNGs are the one nuance: they are *rendered* from the SVGs by
`scripts/build_brand_assets.py`, and they are committed because the packaging steps consume them
and a build must not depend on a rendering toolchain being present.

Committing them when they arrive is not a new precedent: the repo already tracks 12 binaries
(`docs/qa-screenshots/*.jpg`, and the video fixture). The rule that matters is the existing one -
**generated media never goes in git**; brand artwork is authored source, not generated output.

## 6. Which surfaces use what, and which should not

Worth settling *before* the wiring commit, because most of the set above belongs to a website
Truestill does not have, and adding it anyway would mean carrying web-app scaffolding in a
desktop tool.

**The local app (`truestill-app`, served on `127.0.0.1`) - yes, but only the favicon.**
It serves real HTML to a real browser tab, so `favicon.ico` plus the 16 and 32 PNGs are a small,
genuine improvement: the tab stops showing a blank page icon. That is the whole win.

**The local app - no, for everything else.**

* `site.webmanifest` describes an **installable web app**: name, icons, `start_url`, display
  mode. Truestill is installed as a desktop application, not added to a home screen, and a
  manifest would advertise a second, different installation route for the same product.
* `apple-touch-icon.png` is for **iOS home-screen bookmarks** of a website. A localhost server is
  not reachable from a phone.
* `mstile-144x144.png` is for **pinned Windows Start tiles** of a website, a feature Microsoft
  itself has retired.
* `theme-color` / `msapplication-TileColor` style browser chrome around a **site**.

**The landing page (`truestill.app`) - all of it.** That is a public website, where every entry
in section 4 does the job it was designed for. The landing page does not exist yet;
`BACKLOG.md` `(aad)` records that installers are to be served from it.

**The installers - a different problem, and half of this paragraph was wrong** (corrected
2026-08-13, when it was built). A Windows `.exe` needs an embedded `.ico`; macOS needs an
`.icns`; Linux desktop entries want PNGs at specific sizes. What it got wrong was the warning:
*"Do not try to reuse `favicon.ico` for the installer and assume it is done."* **`brand/favicon.ico`
is exactly the right Windows artifact** - PyInstaller's `--icon` takes a `.ico` and
`normalize_icon_type` passes it through **unchanged** when suffix and magic agree, and Inno's
`SetupIconFile` wants a `.ico` carrying 16/32/48/64/256, which this one does. The half that was
right is that it does **not** finish the job: Linux resolves `Icon=truestill` through the hicolor
theme and needs `brand/icons/truestill-<N>.png` staged at eight sizes, and macOS is unserved
because no `.icns` exists here. See `packaging/verify_icon.py`, which asserts the shipped
artifacts carry these bytes rather than trusting that a flag was passed.
