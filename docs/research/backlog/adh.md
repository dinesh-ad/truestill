# (adh) TAURI SHELL + PYTHON SIDECAR - STAGE 1 MEASURED, THREE GAPS NAMED AND UNFIXED.

*Body of backlog entry `(adh)`, under **Approved - still to build**. The index is [`BACKLOG.md`](../../BACKLOG.md); the letter namespace is shared with [`SHIPPED.md`](../../SHIPPED.md).*

- **(adh) TAURI SHELL + PYTHON SIDECAR - STAGE 1 MEASURED, THREE GAPS NAMED AND UNFIXED.**
  Recorded 2026-08-13. Target architecture: Tauri v2 window, the existing Python app as a child
  process, React later. **The backend does not move.** Stage 1 proved the process lifecycle only;
  it migrated nothing, and `app.js`, `tokens.css`, `templates/` and every test are untouched.
  Evidence and method: [`tauri-sidecar-lifecycle-research.md`](../../tauri-sidecar-lifecycle-research.md).

  | | test | result |
  |---|---|---|
  | a | normal quit | **PASS** - sidecar killed, no orphan (close was programmatic, see the doc) |
  | b | **quit mid-copy** | **PASS** - see below |
  | c | SIGKILL the shell | **CLOSED 2026-08-14** on the sidecar side - see below |
  | d | launch twice | two sidecars, two ports, two catalogs; `session-url.txt` names one |
  | e | sidecar cannot start | **FAIL** - the error window used a `data:` URL and panicked |
  | f | SIGTERM the shell | **CLOSED 2026-08-14** on the sidecar side - see below |

  **(b) is the result this stage existed to get, and it is truestill's own doing rather than
  Tauri's.** SIGKILL to shell and sidecar mid-copy, on ext4: one legitimate `.partial`
  (36,175,872 bytes), **27 real-name files byte-identical to source, zero incomplete at a real
  name**. `safe_copy`'s claim - *no partial ever takes the real name* - holds under the hardest
  kill available.

  ⚠ **(f) is security-shaped, not merely untidy.** The orphaned sidecar **keeps serving**, and
  `session-url.txt` still names a live port with a valid token. `__main__.py`'s
  `release_session_link` exists and is correct; it never runs, because the **shell** died rather
  than the sidecar. (c) is the same cause: Tauri's `RunEvent::ExitRequested`/`Exit` fire on a
  *window* close, not on a *signal*, and Tauri's own docs specify neither the ordering nor signal
  behaviour - which is why these were run rather than read.

  **The fixes, named as fixes and NOT as work done:** a SIGTERM/SIGINT handler in the Rust shell
  that kills the child before exiting; for SIGKILL, which cannot be caught, the sidecar must
  self-terminate when its parent goes - `prctl(PR_SET_PDEATHSIG)` on Linux, or a stdin-close
  watchdog as the portable form; single-instance detection that focuses the running window; and
  either the `webview-data-url` Cargo feature or a static error page for (e).

  ✅ **(f) AND (c) CLOSED 2026-08-14, from the sidecar side, which is the side that could close
  both.** `truestill_app/parent_watch.py` plus `--parent-stdin-watch`: the parent holds a pipe on
  stdin, and its closing - by any death, including `SIGKILL` - clears the credential and stops the
  server. **A shell-side signal handler could never have closed (c)**, because `SIGKILL` runs no
  handler; that remedy is now redundant rather than pending.
  - The **stdin watchdog rather than `prctl`**, and the entry offered either: `prctl` needs no
    cooperation from the parent and is better for it, but it is Linux only and a Windows installer
    ships beside the `.deb`. A remedy covering one of two shipped platforms is not the remedy.
  - It needs the parent's cooperation, so **the contract is checked rather than assumed**: given a
    terminal instead of a pipe the watchdog would block on a handle nobody closes and protect
    nothing while looking like it worked, so that case refuses to start and says why.
  - **Opt-in**, so launching `truestill-app` from a terminal is unchanged. Pinned by a test that
    closes stdin on a run *without* the flag and asserts the app is still there.

  ⚠ **(d) and (e) REMAIN, and are blocked on something the entry did not anticipate: the Stage 1
  spike no longer exists.** It lived in `/tmp`, which has since been cleared, and nothing was ever
  committed - there is no `Cargo.toml` or `tauri.conf.json` in this repo. Both remaining gaps are
  Rust-side, so closing them means **bringing a Rust crate into the uv workspace**, which is an
  architecture decision rather than a bug fix and belongs in a commit that says so. The toolchain
  is present (rustup, 1.97.1, installed 2026-08-13).

  **Numbers:** rustup 9s · apt 24s · probe build 126s · shell build 131s · Tauri `.deb` **3.8 MB**
  · `Depends: libwebkit2gtk-4.1-0, libgtk-3-0` · frozen sidecar = **1 process**. Against the
  pywebview spike's 601 MB hello-world, the vehicle is not close.

  **Measured on one machine** - Ubuntu 26.04 / GNOME / Wayland. Windows and macOS untested.
