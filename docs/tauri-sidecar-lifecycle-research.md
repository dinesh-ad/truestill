# Tauri shell + Python sidecar - Stage 1

Recorded 2026-08-13. **Measured on one machine** (Ubuntu 26.04, GNOME, Wayland, WebKitGTK 2.52.3).
Windows and macOS untested - there is no box here and D9 does not publish macOS.

Stage 1 proved one property: whether a Tauri v2 shell can start the existing frozen Python app and
stop it cleanly. It migrated nothing. `app.js`, `tokens.css`, `templates/` and every test are
untouched.

## Option A is dead, and on Linux rather than off it

Two mechanisms can carry a sidecar, and one build with **both** configured settles it:

```
externalBin  ->  /usr/bin/probe-sidecar             755   (the -$TARGET_TRIPLE suffix is stripped)
resources    ->  /usr/lib/probe/payload/inner-exe   755
                 /usr/lib/probe/payload/_internal/  644
```

They land in **different trees**. A one-folder PyInstaller executable resolves `_internal`
**relative to itself**, so via `externalBin` it would sit in `/usr/bin/` and look for
`/usr/bin/_internal` while the 217 MB tree is at `/usr/lib/<app>/`. That is not fragility to be
managed - it is broken on the platform D9 ships first.

The macOS argument (`Contents/MacOS` and `Contents/Resources` provably do not coincide) was
correct, and turned out to be unnecessary: Linux already decides it.

**Option B: the whole folder via `resources`, resolved with `resource_dir()`, spawned as an
ordinary child.** It does not handle the two documented traps, it deletes them - with no
`externalBin` there is no target triple to get wrong, and Tauri never holds the sidecar's pid, so
issue #11686 cannot apply. Independently, the frozen one-folder build runs as **1 process**, so the
bootloader-pid problem behind #11686 was never present either.

## What was measured

| | |
|---|---|
| rustup install | **9 s** |
| apt dev packages | **24 s** |
| `cargo build --release`, first | **126 s** (probe), **131 s** (shell) |
| Tauri hello-world `.deb` | **3.8 MB** |
| Generated `Depends` | `libwebkit2gtk-4.1-0, libgtk-3-0` - both already present here |
| Executable bit through the bundler | **survives**: `755 / 755 / 644` on the **installed** package, both binaries run from `/usr/lib/` |

Runtime is not build-time: the eight `-dev` packages are the developer's. A user needs the two
above, plus appindicator only if a tray is used. `libgtk-3-0t64` **Provides** `libgtk-3-0`, so
Tauri's hard-coded default resolves on Ubuntu 24.04+ and Debian trixie.

For comparison, the pywebview spike measured **601 MB** frozen for a hello-world window, and
PyGObject has no wheel for the bundled 3.13.

## What (a) actually exercised, since it is recorded as a PASS

**The normal-quit test closed the window programmatically (`WebviewWindow::close()`), not through
the window manager.** It is the same code path - `close()` raises `ExitRequested`, which is what a
WM close raises - but it is not a human clicking the close button. Neither `xdotool` nor `wmctrl`
is installed here, and under Wayland neither could see a WebKitGTK window in any case.

Stated because a PASS without its caveat is the defect this repo keeps finding. **What remains
unobserved is the window manager's own path**, on this platform and on the two untested ones.

## Two notes on method, because both nearly produced a false finding

**`/tmp` is tmpfs here.** The quit-during-a-copy test first ran there, completed at RAM speed
before the kill landed, and left no staged file at all. See `ENGINEERING_STANDARD.md` §4, the
forty-sixth member.

**Tauri's `RunEvent` documentation specifies neither the shutdown ordering nor signal behaviour.**
That is why (a), (c) and (f) had to be run rather than read, and it is the whole justification for
this stage.
