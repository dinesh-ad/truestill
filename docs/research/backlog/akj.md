# (akj) NO LANE ANYWHERE EXECUTES `app.js` ON WINDOWS, AND THE FOLDER PICKER'S BREADCRUMB IS WHAT THAT COST

**Filed 2026-09-09 (P250). No work attempted.** Found while censusing the siblings of the
`destination_tree` separator bug (`4d533da`), which is a different defect with a different fix.

The defect is small and the coverage gap is not. **The gap is this entry's subject**; the
breadcrumb is the evidence that it is real rather than theoretical.

## The defect

`app.js:pkNavigate`:

```js
const segs = pk.path ? pk.path.split("/").filter(Boolean) : [];
let acc = "";
const crumbs = [`<a data-p="/">/</a>`].concat(segs.map((s) => { acc += "/" + s; ... }));
```

`pk.path` is `data.path` from `/api/fs/dirs`, which is `str(path)` at `fs_browse.py:fs_dirs` - an
**absolute path in the OS's own spelling**. On Windows that is `C:\Users\me\Pictures`.

| step | POSIX | Windows |
|---|---|---|
| `pk.path` | `/home/you/Pictures` | `C:\Users\me\Pictures` |
| `.split("/")` | `["home", "you", "Pictures"]` | `["C:\Users\me\Pictures"]` - **one segment** |
| crumb targets | `/home`, `/home/you`, `/home/you/Pictures` | `/C:\Users\me\Pictures` |

So the breadcrumb renders the whole path as a single crumb, and its navigation target is a string
with a leading `/` bolted onto a drive-letter path. It does not resolve. The hardcoded root crumb
`<a data-p="/">/</a>` is POSIX-only in the same way: there is no `/` on Windows.

**Reached in ordinary use**: clicking any `Browse…` button. There are five
(`data-browse` on the source, destination, library root, and the Settings and Backups fields).

## `as_posix()` at the producer would be a BUG, not a fix

This is the difference from the `destination_tree` defect, and it is why that fix does not
generalise here.

`destination_tree`'s keys are `Decision.relative` - a path **within** a destination, declared
backend-independent by `Decision`'s own docstring, promised as `"/"` by its field docstring, and
consumed only for display. `as_posix()` is correct there and is what the rest of the tree already
does (`run_record.py:files_from_resolutions` on the same field).

`/api/fs/dirs`'s `path` is the opposite kind of value. It is a **real path on this machine**:
`pkUse` writes it back into `#org-source` / `#org-dest`, `app.js` posts it to routes that hand it
to the filesystem, and `fs_validate` resolves it. Rewriting it to posix at the producer would
corrupt every Windows path the picker returns - the field would stop naming a place that exists.
**The producer is already correct.**

## The plausible fix, recorded rather than taken

Have the server return the crumbs it is already able to compute:

```json
{"path": "C:\\Users\\me\\Pictures",
 "crumbs": [{"label": "C:\\", "path": "C:\\"},
            {"label": "Users", "path": "C:\\Users"},
            {"label": "me", "path": "C:\\Users\\me"}, ...]}
```

`PurePath.parts` and `parents` give exactly this, and **only the server knows which platform it is
on** - which is the whole argument. A client-side split on `/[\\/]/` gets the *segments* right and
still cannot rebuild the targets: it would have to know that Windows has no leading separator, that
`C:` is a root and `C:\` is a different thing, and that a UNC path starts with two.

⚠ **This touches the API contract**, so it needs the payload, `openapi.json` and the frozen
oracle pair regenerated (`scripts/emit_api_types.py`, and `packages/truestill-app/tests/fixtures/contract-oracle/README.md`
for why that pair is never regenerated casually). That is why it is filed rather than done.

## The real subject: nothing in CI can see this

**No lane anywhere executes `app.js` on Windows.**

| lane | what it runs | platforms |
|---|---|---|
| `check` | `make check` - Python only; cannot execute client-side JS | ubuntu, **macos, windows** |
| `e2e` | the browser lane, chromium + webkit - the only thing that runs `app.js` | **ubuntu only** |

The three-OS matrix is described in `IMPLEMENTATION_STANDARDS.md` §6.1 as *"the only thing that
sees Windows and macOS"*, and it is - **for Python**. `ci.yml`'s e2e job is
`runs-on: ubuntu-latest` with a chromium/webkit matrix, so the axis it varies is the **engine**,
never the **OS**. The two lanes' coverage is a cross with a hole exactly where this defect lives.

That is not an argument for adding a Windows browser lane. `(ajx)` measured what the existing lane
costs and `D3` records what the browser lane deliberately does not cover; a fourth leg is a
separate ruling with a real price. **It is an argument for knowing the hole is there**, because
the same hole hides every other OS-dependent thing `app.js` does - and the census that found this
one turned up five path-splitters of which two take `"/"` alone.

## The check that produced this

```sh
grep -rnE "\.split\(['\"/]|lastIndexOf\(['\"]/" \
  packages/truestill-app/src/truestill_app/static/app.js packages/truestill-app/frontend/src/
```

Five sites. `main.tsx:421` and `app.js:previewView` split on `/[\\/]/`; `app.js:pathBasename` uses
`lastIndexOf` on both separators; those three are safe. `preview.tsx:405` took `"/"` alone and was
fixed at its producer in `4d533da`. `app.js:pkNavigate` is this entry.

⚠ **Confirmed by reading code and by the separator's behaviour, NOT by running on Windows** -
which is the entry's own point. `PureWindowsPath("C:/Users/me")` renders as `C:\Users\me` under
`str()`, and `"C:\\Users\\me".split("/")` is a one-element list; both are checkable anywhere. What
is not checkable here is the screen.
