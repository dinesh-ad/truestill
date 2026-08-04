# Truestill brand identity

Recorded 2026-08-01. **Reference only - nothing here is wired into the product yet**, and the
wiring commit should read the "Which surfaces use what" section before adding anything.

The product name is **Truestill**, capitalised, wherever a person reads it. The import package
stays `truestill_core`, the command stays `truestill`, and the app entry point stays
`truestill-app`: those are identifiers, and lowercase is right for all three. See
`app_paths.APP_NAME`, which carries the same distinction for the OS data directory.
**Enforced on the surfaces a person reads** by `scripts/check_product_name.py` (`make check`),
which skips code, identifiers and `truestill <subcommand>` invocations - this paragraph is the
source it enforces, so change the rule here first.

---

## 1. Wordmark

The word **Truestill**, set in a serif, filled with the indigo gradient below.

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

> **AUTHORED 2026-08-04. Artwork lives in `brand/`; provenance and licence in
> `brand/PROVENANCE.md`. What follows is the original sheet, kept as the source of the palette.**
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

## 3. Icon - the TS monogram

A **TS** monogram in the indigo gradient, required in a **light** and a **dark** variant so it
stays legible on either background. The dark variant is not a recolour of the light one by
inversion; both are wanted as artwork.

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

## 5. Status of the assets in this repo

**None of the files in section 4 are in the repo yet.** The identity above was supplied as HTML
and CSS, which fully specifies the wordmark and the palette but contains no image data - the
page links the icons, it does not carry them.

So there is nothing to describe the sizes and formats *of*, and this section says so rather than
listing files that do not exist. `brand/README.md` records where they go and what is expected.

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

**The installers themselves - a different problem, not this set.** A Windows `.exe`/`.msi` needs
an embedded `.ico`; macOS needs an `.icns`; Linux desktop entries want PNGs at specific sizes.
Those are produced from the same monogram artwork but are **not** the web icon set, and the
bundler chosen in `(aad)` will dictate the exact shapes. Do not try to reuse `favicon.ico` for
the installer and assume it is done.
