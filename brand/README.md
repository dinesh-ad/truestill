# Brand assets

The one directory for authored brand artwork. `docs/brand.md` is the reference - the wordmark,
the indigo gradient, the icon set and, importantly, **which surfaces each file is for**. Read it
before wiring anything in, because most of the web icon set belongs to the landing page rather
than to a localhost tool.

## What is here now

**Nothing but this file.** The identity was supplied as HTML and CSS, which specifies the
wordmark and the palette completely but carries no image data: the page *links* the icons, it
does not contain them. Rather than commit invented artwork under the name of the brand, this
records the gap.

## What belongs here when it arrives

Expected files, per `docs/brand.md` section 4:

```
truestill-wordmark.svg        outlined paths, NOT text in a font
truestill-monogram-light.svg  TS monogram for light backgrounds
truestill-monogram-dark.svg   TS monogram for dark backgrounds
favicon.ico                   multi-size: 16, 32, 48
favicon-16x16.png
favicon-32x32.png
favicon-48x48.png
apple-touch-icon.png          180x180
mstile-144x144.png            144x144
site.webmanifest
```

When they land, update `docs/brand.md` section 5 to state the sizes and formats actually present,
so a future reader knows what exists without opening any of them.

## Two things not to get wrong

**The wordmark must be a vector with outlined paths.** The supplied CSS uses Georgia, which is a
placeholder: it is absent on most Linux systems, so the shape of the word changes per platform.
A logo is a fixed shape, not text rendered in whatever font happens to be installed.

**Installer icons are a separate set.** Windows wants an embedded `.ico`, macOS an `.icns`, Linux
desktop entries PNGs at their own sizes. Same monogram, different deliverables, and the bundler
chosen in `BACKLOG.md` `(aad)` decides the exact shapes. The favicon is not a substitute.
