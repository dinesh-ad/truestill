"""Every route `app.js` calls through its JSON client answers `application/json`, by the contract.

**The defect this pins** (nightly 33731353952, WebKit, 2026-09-03): `sendCancel` called
`/api/jobs/{job_id}/cancel` through `api()`, which parses every 2xx body as JSON, and the route
answers a bodiless 202 - so every accepted cancel threw `did not return JSON`, painted the red
banner on every browser, and when the click was queued before the job was named the throw
aborted `runJob` before it subscribed to the stream. The contract already said so:
`openapi.json`'s 202 for that route carries no content, and the generated types read
`content?: never`. Nothing compared the client's calls against it. This does, in `make check`,
with no browser.

**Cost, declared rather than suppressed** (`ENGINEERING_STANDARD.md` §4): one regex pass over
`app.js`, one JSON parse of the spec, milliseconds.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
APP_JS = ROOT / "packages/truestill-app/src/truestill_app/static/app.js"
SPEC = ROOT / "packages/truestill-app/openapi.json"

#: The JSON client's two spellings, followed by the opening quote of a literal path.
_CALL = re.compile(r"(?<![.\w])(?:api|get)\(\s*([`'\"])")


def _literal(text: str, start: int, quote: str) -> str:
    """The literal beginning at ``start`` (just after its opening quote), with every `${...}`
    replaced by `{p}` - nested braces and inner backticks inside a substitution respected."""
    out, i, depth = [], start, 0
    while i < len(text):
        ch = text[i]
        if depth == 0 and ch == quote:
            break
        if text.startswith("${", i):
            depth += 1
            if depth == 1:
                out.append("{p}")
            i += 2
            continue
        if depth and ch == "}":
            depth -= 1
        elif depth == 0:
            out.append(ch)
        i += 1
    return "".join(out)


def _client_calls() -> dict[str, list[int]]:
    """``call path -> lines``. A `{p}` that is not a whole segment carries a query or a suffix the
    route does not see, so the path is cut there."""
    text = APP_JS.read_text(encoding="utf-8")
    found: dict[str, list[int]] = {}
    for match in _CALL.finditer(text):
        path = _literal(text, match.end(), match.group(1)).split("?", 1)[0]
        segments = []
        for segment in path.split("/"):
            if "{p}" in segment and segment != "{p}":
                # `files{p}` is `/api/dates/files` plus a query the route never sees.
                segments.append(segment.split("{p}", 1)[0])
                break
            segments.append(segment)
        found.setdefault("/".join(segments), []).append(text.count("\n", 0, match.start()) + 1)
    return found


def _json_routes() -> dict[str, bool]:
    """``template path -> whether some operation's 2xx answers application/json``."""
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    return {
        path: any(
            "application/json" in (response.get("content") or {})
            for op in item.values()
            for status, response in op["responses"].items()
            if status.startswith("2")
        )
        for path, item in spec["paths"].items()
    }


def _matches(call: str, template: str) -> bool:
    """Segment by segment: a `{p}` in the call, or a `{...}` in the template, matches anything -
    `/api/events/{p}/{p}` in `app.js` is `/api/events/{session}/merge` and four siblings."""
    a, b = call.split("/"), template.split("/")
    return len(a) == len(b) and all(
        x in {y, "{p}"} or (y.startswith("{") and y.endswith("}"))
        for x, y in zip(a, b, strict=True)
    )


def test_every_json_client_call_targets_a_route_that_answers_json() -> None:
    routes = _json_routes()
    calls = _client_calls()
    assert len(calls) >= 30, f"only {len(calls)} client calls found; the pattern moved"
    unknown: list[str] = []
    bodiless: list[str] = []
    for call, lines in sorted(calls.items()):
        hits = [t for t in routes if _matches(call, t)]
        if not hits:
            unknown.append(call)
        bodiless.extend(f"{call} -> {t} (lines {lines})" for t in hits if not routes[t])
    assert not unknown, f"app.js calls routes the contract does not declare: {unknown}"
    assert not bodiless, (
        "app.js parses JSON from a route the contract says answers none - use a bodiless request:\n"
        + "\n".join(bodiless)
    )
