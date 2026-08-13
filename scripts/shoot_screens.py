"""Photograph every screen's resting state, and say what the photographs do not show.

**Not part of any gate.** It asserts nothing and fails nothing; it is a tool for looking at the
app, in the same category as `build_brand_assets.py` and `make_pillar_t.py`. It is inside the
ruff and mypy fence because §6 puts every script there - a script that imports the app is real
code, and `benchmark_hashing.py` sat outside that fence importing a module that had not existed
for two renames.

**IT PHOTOGRAPHS THE APP THE BROWSER TESTS DRIVE.** The server comes from
`e2e_support.boot_app`, which the `app_server` fixture also calls. A private server built here
would be a second artifact drifting quietly from the real one - the shape
`IMPLEMENTATION_STANDARDS.md` §6.1 refuses for a curated smoke suite, arriving from the other
direction.

**THE MANIFEST IS THE POINT, NOT THE IMAGES.** A screenshot set that does not state its coverage
gets read as complete - by whoever runs it, and by the same person a month later. So every run
writes `manifest.md` beside the pictures naming the viewport, the catalog and its size, the
theme, and **which regions the client fills rather than the template** - the ones whose contents
depend on this catalog and on what has been run, where most of `app.js`'s markup lives. That list
is *derived from `index.html`*, never transcribed. Same property as `verify_icon.py` printing
`NOT CHECKED` rather than skipping quietly.

**Two decisions, and the reasoning is the useful part:**

* **The viewport is an argument, repeatable, defaulting to 1920x1080.** A constant would mean
  editing the tool to photograph the case it exists for: `ui-inventory.md` records three real
  panels at **1920, 2560 and 3072 CSS px** - the last two read as a broken layout before the
  1600px cap - and the rail becomes a top bar below 720. Those are the shots the UI work wants.
* **Populating a catalog is the CALLER's job (`--db`).** A corpus builder in here would duplicate
  `truestill organize` and the `library` fixture, and would bake in a shape - which months, how
  many photos - that has nothing to do with photographing screens and rots the first time dating
  or layout changes. `--db` takes any catalog: omit it for a first-run empty one, or point it at
  a library built however you like. The manifest records which it was, so an empty set can never
  be mistaken for a populated one.

Complexity: O(screens x viewports), one page load each. Writes only under ``--out``.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "tests" / "e2e"))

from e2e_support import boot_app, open_app, open_screen
from playwright.sync_api import Page, sync_playwright

_TEMPLATE = _ROOT / "packages/truestill-app/src/truestill_app/templates/index.html"

#: The regions `app.js` writes into rather than the template. Most of its markup renders here, so
#: this is the list that says why a resting-state set under-represents the product.
#:
#: **NOT "empty after a run", which is what this said first and was wrong**: `#panel` and
#: `#stats-result` fill from a plain load whenever the catalog has anything in it. The honest
#: claim is the one the manifest now makes - these are written by the client, so what appears in
#: them depends on the catalog and on what has been run, and a picture of them at rest is a
#: picture of one state out of many.
_JS_WRITTEN = re.compile(r'id="([\w-]*(?:result|confirm|panel|clusters|moves|declines))"')


def screens() -> list[str]:
    """Every screen, read from the template rather than transcribed.

    `(abc)`'s rule. A hand-kept list is the one thing in this tool that would silently go short
    the day a screen is added, and the answer would be a photograph set missing a screen with
    nothing to say so.
    """
    html = _TEMPLATE.read_text(encoding="utf-8")
    seen: list[str] = []
    for name in re.findall(r'data-screen="([\w-]+)"', html):
        if name not in seen:
            seen.append(name)
    return seen


def client_written_regions() -> list[str]:
    """Element ids `app.js` fills, derived from the template rather than transcribed."""
    html = _TEMPLATE.read_text(encoding="utf-8")
    found = sorted(set(_JS_WRITTEN.findall(html)))
    runs = len(re.findall(r'class="run-mount"', html))
    return [*found, f"({runs} shared run/progress blocks, all hidden until a job starts)"]


def catalog_size(db: Path) -> str:
    """How much is in this catalog, so an empty set cannot read as a populated one."""
    if not db.is_file():
        return "empty (created on first open)"
    import sqlite3  # noqa: PLC0415 - only needed on this path, and never by the shooting loop

    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            drives = conn.execute("SELECT COUNT(*) FROM drives").fetchone()[0]
    except sqlite3.Error as error:  # a catalog we cannot read is a fact, not a crash
        return f"unreadable ({error})"
    return f"{files:,} files across {drives} registered drive(s)"


def shoot(page: Page, out: Path, label: str) -> list[str]:
    """Every screen at one viewport. Returns the screens actually photographed."""
    out.mkdir(parents=True, exist_ok=True)
    taken: list[str] = []
    for name in screens():
        open_screen(page, name)
        page.screenshot(path=str(out / f"{name}.png"), full_page=True)
        # The rendered text beside each image: greppable, diffable between runs, and the thing
        # §9 actually governs. An image cannot be searched for a wrong sentence.
        (out / f"{name}.txt").write_text(page.inner_text(f"#screen-{name}"), encoding="utf-8")
        taken.append(name)
        print(f"  {label}/{name}.png")
    return taken


def manifest(out: Path, db: Path, theme: str, shots: dict[str, list[str]]) -> Path:
    """What this set covers, and - the half that matters - what it does not."""
    lines = [
        "# Screen shots - what this set covers",
        "",
        f"Taken {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by `scripts/shoot_screens.py`.",
        "",
        f"- **Catalog:** `{db}` - {catalog_size(db)}",
        f"- **Theme:** {theme}",
        f"- **Viewports:** {', '.join(shots)}",
        f"- **Screens:** {', '.join(next(iter(shots.values()), []))}",
        "",
        "## What these images do NOT show",
        "",
        "Every screen is at **rest**: opened, nothing clicked. That is deliberate - the empty",
        "resting state is a first impression rather than an afterthought - but it means the",
        "majority of `app.js`'s markup is absent from every image here. The regions below are",
        "written by the client rather than by the template, so what is in them depends on this",
        "catalog and on what has been run; at rest most are empty, and a couple (`panel`,",
        "`stats-result`) fill from a plain load once the catalog holds anything:",
        "",
    ]
    lines += [f"- `{item}`" for item in client_written_regions()]
    lines += [
        "",
        "Also absent: any completion card, tally, duplicate report, trip proposal, migration",
        "preview or typed-confirm block, and the folder picker. Reaching those needs a driven run,",
        "which this tool deliberately does not fake.",
        "",
        f"Only the listed viewports were photographed, and only the `{theme}` theme.",
    ]
    path = out / "manifest.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="photograph every screen's resting state")
    parser.add_argument("--out", type=Path, default=Path("screenshots"))
    parser.add_argument("--db", type=Path, help="a catalog to photograph; omit for an empty one")
    parser.add_argument(
        "--viewport",
        action="append",
        default=None,
        help="WxH in CSS px, repeatable (default 1920x1080; try 2560x1440, 3072x1728, 700x900)",
    )
    parser.add_argument("--theme", default="system", choices=("system", "light", "dark"))
    args = parser.parse_args(argv)

    sizes = args.viewport or ["1920x1080"]
    temp = tempfile.TemporaryDirectory() if args.db is None else None
    db = args.db if args.db is not None else Path(temp.name) / "catalog.sqlite"  # type: ignore[union-attr]

    started, server, thread, sock = boot_app(db)
    shots: dict[str, list[str]] = {}
    try:
        with sync_playwright() as driver:
            browser = driver.chromium.launch()
            for size in sizes:
                width, _, height = size.partition("x")
                context = browser.new_context(
                    viewport={"width": int(width), "height": int(height)},
                    device_scale_factor=1,
                    color_scheme=None if args.theme == "system" else args.theme,
                )
                page = open_app(context.new_page(), started.url)
                shots[size] = shoot(page, args.out / size, size)
                context.close()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        if temp is not None:
            temp.cleanup()

    print(f"\nmanifest: {manifest(args.out, db, args.theme, shots)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
