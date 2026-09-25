# Golden repo rules

**Standalone.** This file is the whole package. Do not assume any other standards
document exists in the target repo. Drop it in first; wire the hook; then continue product work.

**Owns only:** commit identity, no AI co-author in history, and pre-commit install discipline.
It does **not** replace the repo's real test gate (`make check`, `npm test`, CI, or whatever that
repo uses).

**For an agent adding this to a product codebase:** follow §0, then stop. Do not invent product
rules here.

---

## 0. Agent checklist (do this first)

1. Create `docs/GOLDEN_REPO_RULES.md` with **this file's full contents** (or place at repo root as
   `GOLDEN_REPO_RULES.md` if the repo has no `docs/` yet - pick one path and keep it).
2. Create `scripts/check_commit_msg.py` with the script in §1 (create `scripts/` if missing).
3. Ensure `.pre-commit-config.yaml` exists and includes the `no-ai-coauthor` stanza in §2.
4. If the repo has no pre-commit yet: add `pre-commit` as a dev dependency and a minimal config
   that at least contains that stanza (lint/format hooks are recommended but not required by this
   file).
5. Install hooks:

```sh
pre-commit install
pre-commit install --hook-type commit-msg
# only if the repo defines pre-push hooks:
pre-commit install --hook-type pre-push
```

(Use `uv run pre-commit …` when the project is a uv workspace.)

6. Prove the commit-msg guard once:

```sh
git commit --allow-empty -m "test
Co-Authored-By: someone <x@y.z>"
```

That commit **must be refused**. Then continue with normal product setup.

---

## 1. No AI co-author in git history (non-negotiable)

Commit messages must not carry:

- a `Co-Authored-By:` trailer (any author),
- an `@anthropic` email,
- a "Generated with Claude" / robot-signature line.

Naming a file such as `CLAUDE.md` or `AGENTS.md` in prose is fine. Only trailers, emails, and
signatures are blocked.

**Why:** git history is the permanent record of who shipped what. An AI tool is not a co-author
of the product.

### `scripts/check_commit_msg.py`

```python
#!/usr/bin/env python3
"""commit-msg hook: refuse AI co-author trailers / Anthropic-Claude signatures."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_FORBIDDEN = re.compile(
    r"co-authored-by:|@anthropic|\U0001f916 generated|generated with \[claude",
    re.IGNORECASE,
)


def main() -> int:
    message = Path(sys.argv[1]).read_text(encoding="utf-8")
    match = _FORBIDDEN.search(message)
    if match is not None:
        print(
            f"commit-msg: refused -- forbidden content {match.group(0)!r}.",
            file=sys.stderr,
        )
        print(
            "Golden rule: no Co-Authored-By trailer / Anthropic-Claude email in history.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Make it executable if your environment expects that: `chmod +x scripts/check_commit_msg.py`.

---

## 2. Pre-commit is a floor, not the gate

### Required stanza

Add this under `repos:` in `.pre-commit-config.yaml` (or merge into an existing `repo: local`
block that already has `commit-msg` hooks):

```yaml
- repo: local
  hooks:
    - id: no-ai-coauthor
      name: block AI co-author / Anthropic-Claude signature in commit message
      entry: python3 scripts/check_commit_msg.py
      language: system
      stages: [commit-msg]
```

### Recommended (portable) hook kinds

Keep these in every product repo when the stack supports them. Names may vary by language.

| Kind | Example ids | Job |
|---|---|---|
| Lint / format | `ruff`, `ruff-format` (or ESLint/Prettier, etc.) | Catch style/import noise at commit |
| Types | `mypy` (or `tsc --noEmit`, etc.) | Same fence as CI for typed paths |
| Commit message | `no-ai-coauthor` (§1) | **Required** by this file |
| Extra local scripts | optional | Repo taste only - not defined here |

Do **not** treat this file as a list of every hook a given repo already has. Product-specific
hooks stay in that repo's own config and docs.

### Hard rules for any hook

1. **A message that matters must ride a non-zero exit.** A passing pre-commit hook's stdout is
   usually suppressed; `Passed` is not a warning channel. Prefer refuse over warn-and-exit-0.
2. **Do not use `--no-verify` to dodge these.** Fix the message or the files.
3. **Hooks do not run the test suite.** Green hooks plus a red product gate still means do not
   commit / do not push.

---

## 3. Author identity

Use a stable **human** `user.name` / `user.email` for product repos. Do not add AI tools as git
authors or co-authors. Enforce with local `git config` plus §1's hook - not with a shared
machine-wide secret committed to the repo.

Suggested author for this maintainer's product repos: `dinesh-ad` (set locally; do not force via
committed config).

---

## 4. Precedence

| Topic | Winner |
|---|---|
| No-AI trailer, commit-msg install, hook message discipline (§1–§3) | **This file** |
| Product behaviour, architecture, data safety, feature gates | That repo's own product docs / code |
| Day-to-day workflow advice | Whatever that repo documents |

If another document in the same repo restates §1–§3 differently, **this file wins** on those
topics. If no other standards docs exist, this file is still enough.
