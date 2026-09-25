# Golden repo rules (portable across product projects)

**Not truestill-specific.** Copy this file into any product repo and keep it as the floor for
git history and commit-time checks. Product behaviour (copy-only media, catalogs, fences) lives
in that repo's own binding contract - here, [`IMPLEMENTATION_STANDARDS.md`](IMPLEMENTATION_STANDARDS.md).

This document wins on **commit identity** and **pre-commit install / hook discipline** when a
product contract is silent or restates them. It does **not** replace `make check` / CI.

---

## 1. No AI co-author in git history (non-negotiable)

Commit messages must not carry:

- a `Co-Authored-By:` trailer (any author),
- an `@anthropic` email,
- a "Generated with Claude" / robot-signature line.

Referencing a file named `CLAUDE.md` is fine. Only trailers, emails, and signatures are blocked.

**Why:** history is the permanent record of who shipped what. An AI trailer makes the tool look
like a co-author of the product; it is not.

**Enforce with a `commit-msg` hook** (this repo: `scripts/check_commit_msg.py`, hook id
`no-ai-coauthor`). Activate:

```sh
uv run pre-commit install --hook-type commit-msg
```

Prove it once on a fresh clone:

```sh
git commit --allow-empty -m "test
Co-Authored-By: someone <x@y.z>"   # MUST be refused
```

Minimal portable checker (adapt the path; keep the patterns):

```python
# commit-msg hook: refuse AI co-author trailers / Anthropic-Claude signatures
import re, sys
from pathlib import Path

_FORBIDDEN = re.compile(
    r"co-authored-by:|@anthropic|\U0001f916 generated|generated with \[claude",
    re.IGNORECASE,
)
message = Path(sys.argv[1]).read_text(encoding="utf-8")
match = _FORBIDDEN.search(message)
if match is not None:
    print(f"commit-msg: refused -- forbidden content {match.group(0)!r}.", file=sys.stderr)
    raise SystemExit(1)
```

---

## 2. Pre-commit is a floor, not the gate

### Install all three stages

```sh
uv run pre-commit install                         # pre-commit (staged files)
uv run pre-commit install --hook-type commit-msg  # message guards
uv run pre-commit install --hook-type pre-push    # push-time guards (if the repo has any)
```

A green column of hooks is **not** permission to push. The product gate (`make check` or
equivalent) still runs before every commit when the repo says so.

### Portable hook kinds (keep these in every product repo)

| Kind | Typical ids | Job |
|---|---|---|
| Lint / format | `ruff`, `ruff-format` (or language equivalent) | Catch style/import noise at commit |
| Types | `mypy` (or language equivalent) | Same fence as CI for the paths you typecheck |
| Commit message | `no-ai-coauthor` (§1) | Keep AI signatures out of history |
| Artifact / prose | optional local scripts | Repo taste (dashes, redirect filenames, …) |

### Product-specific hooks (do **not** copy blindly)

These belong in the product repo's binding contract / config, not in this golden file's
"must ship everywhere" list:

| This repo's id | Why it is not portable |
|---|---|
| `product-name` | Product spelling on user-facing surfaces |
| `entry-closure` | Backlog letter ↔ `SHIPPED.md` closure |
| `push-gate` | CI tip green/red for *this* GitHub repo |

### Hard rules for any hook you keep

1. **A message that matters must ride a non-zero exit.** A passing pre-commit hook's stdout is
   usually suppressed; `Passed` is not a warning channel. Prefer refuse over warn-and-exit-0.
2. **Do not use `--no-verify` to dodge these.** Fix the message or the files.
3. **Hooks do not run the test suite.** Green hooks + red `make check` still means do not commit.

### Example `commit-msg` stanza (portable half only)

```yaml
- repo: local
  hooks:
    - id: no-ai-coauthor
      name: block AI co-author / Anthropic-Claude signature in commit message
      entry: python3 scripts/check_commit_msg.py
      language: system
      stages: [commit-msg]
```

---

## 3. Author identity (maintainer default)

Prefer a stable human author identity on product repos (this maintainer: `dinesh-ad`). Do not
add AI tools as git authors or co-authors. Enforce with local `git config` and §1's hook, not
with a shared machine-wide secret.

---

## 4. How this relates to a product binding contract

| Document | Owns |
|---|---|
| **This file** | Commit identity, no-AI trailers, pre-commit install discipline, hook message rules |
| **Product binding contract** (e.g. `IMPLEMENTATION_STANDARDS.md`) | Product invariants, data safety, gates, corpus fences, truth contract |
| **Portable engineering guide** (e.g. `ENGINEERING_STANDARD.md`) | How to work; loses to the product contract on conflict |

On conflict about **§1–§3 of this file**, this file wins even if a product contract restates them
differently. On product behaviour, the product contract wins.
