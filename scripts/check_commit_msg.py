#!/usr/bin/env python3
"""commit-msg hook: keep AI co-authorship and Anthropic/Claude emails out of history.

Project rule (non-negotiable): commit messages must not carry a ``Co-Authored-By`` trailer,
an ``@anthropic`` email, or a "generated with Claude" signature. Referencing the file
``CLAUDE.md`` by name is fine -- only trailers/emails/signatures are blocked.
"""

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
        print(f"commit-msg: refused -- forbidden content {match.group(0)!r}.", file=sys.stderr)
        print(
            "Project rule: no Co-Authored-By trailer / Anthropic-Claude email in commit history.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
