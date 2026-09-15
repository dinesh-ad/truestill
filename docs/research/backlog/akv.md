# (akv) EVERY RELEASE SHIPPED THE WEB UI WEARING THE CLI'S NAME, AND NO CLI AT ALL.

*Body of backlog entry `(akv)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

## THE DEFECT, FOUND BY INSTALLING THE PRODUCT

`release.yml` froze `packages/truestill-app/src/truestill_app/__main__.py` and named the result
`truestill`. That is the **app**. The CLI was never an entry point, so `truestill-cli` had zero
entries in the bundle - a fact the workflow's own comment stated, as a *reason*, having mistaken
the defect for a design.

Measured on the 2026-09-15 dry-run `.deb` (run 35005819074):

```
truestill account      -> exit 2 (unrecognized arguments)
truestill analyze      -> exit 2
truestill organize     -> exit 2
truestill verify       -> exit 2
truestill self-check   -> exit 2
```

`dpkg -c` confirms it from the other side: `/usr/bin` held one file, and `truestill_cli` matched
nothing in the payload. There was no `/usr/bin/truestill-app` either, so README's `truestill-app`
line named a command no installed machine had.

⚠ **SIX CAPABILITIES HAVE NO OTHER HOME**: `reclaim`, `rescan`, `repoint-sources`, `carried`,
`self-check`, `catalog --move`. For anyone who installed the product they were not *"CLI-only"* -
the phrase `docs/cli-app-parity.md` used - they were **unreachable**. That document had been
measuring a surface no customer had.

## WHY EVERY GATE WAS GREEN, WHICH IS THE PART WORTH KEEPING

* **A bundler drops what nothing imports, with a zero exit.** A missing entry point looks exactly
  like a successful build.
* **A self-check runs inside a process and can only report on that process.** The app's report
  was `complete: true`, all fifteen findings, in a tree containing no CLI whatsoever. It is
  structurally incapable of noticing a sibling's absence.
* **The install detector asserted `/usr/bin/truestill` exists.** It did. It was the app. **A true
  assertion and a false conclusion** - and the single command CI ran against the installed copy,
  `--self-check`, is the one flag both surfaces happen to share. CI exercised the only path that
  worked.

That is why the fix has two halves, and why the second is the one that matters.

## THE FIELD'S ANSWER, NOT AN INVENTED ONE

The identical defect was fixed elsewhere in July 2026 - a macOS bundle step that embedded the GUI
only, so the CLI was absent from the shipped app while Linux users had it. **They also added a
`verify_bundle_binaries` step so a future regression fails the build**, which is the half this
entry copies deliberately: the payload is compared against a **written promise held outside the
artifact**, because nothing inside an artifact can testify to what is missing from it.

On shape: *"If you can live with multiple executables, separate CLI and GUI projects are the
cleanest solution for dual interface applications. Each can run in its intended environment
without any hacks."* PyInstaller supports exactly that - multiple `Analysis`, `PYZ` and `EXE`
objects passed into a **single** `COLLECT`, sharing the stdlib and third-party code.

⚠ **ONE BINARY DOING BOTH WAS REFUSED, and PyInstaller issue #6244 is the price.** A `--noconsole`
build has no stdout on Windows; the issue is people piping to `| more` to get any output at all.
`console` is one attribute of an `EXE` and it cannot hold both values. A CLI needs `True`, a
double-clicked app needs `False`.

## THE NAMES ARE NOT A CHOICE

`[project.scripts]` has declared them all along:

| package | entry point |
|---|---|
| `truestill-cli` | `truestill = truestill_cli.cli:main` |
| `truestill-app` | `truestill-app = truestill_app.__main__:main` |

`CLAUDE.md`'s own first paragraph says the same - *"The command is `truestill`; the local web UI
is `truestill-app`"*. **The freeze is what diverged.** Matching it makes every existing document
true of the artifact rather than requiring a document to change, which is why no rename was
considered: the alternative, calling the CLI `truestill-cli`, is a name nothing in the tree uses.

## THE SIZE, MEASURED

One `COLLECT` de-duplicates by destination, so numpy, Pillow, the stdlib, the fonts and the
vendored exiftool are written once. What does **not** de-duplicate is each `EXE`'s own `PYZ`,
which is embedded in the executable.

| | bytes | |
|---|---|---|
| before, one executable | 235,608,504 | app EXE 16,113,696 |
| after, two executables | 250,642,749 | + CLI EXE 15,031,888 |
| **growth** | **+15,034,245 (+6.4%)** | |

The increase is the second executable's own archive, near-exactly. **It did not double.**

## WINDOWS: THE PATH QUESTION, ANSWERED

`{app}` is `%LOCALAPPDATA%\Programs\Truestill` under `PrivilegesRequired=lowest`, which is **not**
on `PATH`. Shipping a CLI there unreachable would repeat this entry's own defect one platform
over, so `installer.iss` adds it - `HKCU\Environment` (never `HKLM`: this is a per-user install),
`expandsz` to preserve the type the shell expects, `Check: NeedsAddPath` so a repeat install is
idempotent, and `CurUninstallStepChanged` to remove exactly our entry on the way out.

⚠ **There is deliberately no `uninstalldeletevalue`.** It would delete the user's entire `PATH` -
the worst thing an uninstaller in that file could do, and one flag away from the correct
behaviour. CI asserts both directions: the entry present after install, absent after uninstall,
and the rest of `PATH` non-empty.

## WHAT PROVES IT

`test_the_package_ships_every_binary_it_promises.py`, five tests, and the mutation is not a
patched anchor but the real thing - **deleting an executable from the real frozen tree**:

| removed from `dist/truestill/` | `build_deb.py` |
|---|---|
| `truestill` | refuses, names it, names the spec, **writes no package** |
| `truestill-app` | refuses, names it, names the spec, **writes no package** |
| nothing | builds, 99,596,414 bytes |

Two existing tests went red and both were right to: `test_release_out_holds_only_deliverables`'s
fixture wrote a single binary - **the defect, modelled faithfully in a fixture** - and now derives
the pair from `BUNDLE_BINARIES`, so a third name cannot be promised while that file keeps testing
two.
