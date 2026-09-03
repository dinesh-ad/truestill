"""`api.d.ts` from `openapi.json`: the TypeScript half of the payload contract. `(ahn)` stage E

**Why this exists instead of `openapi-typescript`** (ruled 2026-09-03, P199): the TypeScript 7
package ships no compiler API - `ls node_modules/typescript/lib` is five files - and
`openapi-typescript` builds a TypeScript AST through that API, so npm refuses it on
`peer typescript@"^5.x"` and it crashes under 7.0.2 when forced. Carrying a second compiler for
one generated file was refused; this emitter needs nothing but Python, which also lets the drift
check regenerate the WHOLE file in `make check`, so a hand edit is caught, not only a stale spec.

**Accepted against the field's tool, not against intent.** `openapi-typescript` 7.13.0 under
TypeScript 5.9.3 rendered the spec of 2026-09-03 to 3,793 lines; that pair is frozen under
`packages/truestill-app/tests/fixtures/contract-oracle/` and
`test_the_generated_types_are_current.py` asserts this emitter reproduces it byte for byte
below the header. The shape is therefore the oracle's: `paths` with every method named, an
`operations` interface keyed by `operationId`, `components["schemas"]` with a `/** Title */` per
schema and `/** @enum {unknown} */` before an enum literal, `@description` on every response.

**What it handles, and what it refuses.** `$ref`, `oneOf` and `anyOf` (a union, no discriminator
needed for TypeScript), `const` and `enum` (literals), `NotRequired` as `?`, nested objects,
`additionalProperties` as an index signature, arrays, `null`, `text/event-stream` under a
response like any other content type. **Anything else raises** - `allOf`, `prefixItems`,
`not`, a `type` list - naming the schema, so a construct the oracle never saw cannot be rendered
by guesswork and then trusted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packages/truestill-app/openapi.json"
TYPES = ROOT / "packages/truestill-app/frontend/src/generated/api.d.ts"
METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")
INDENT = "    "
SCALARS = {
    "string": "string",
    "integer": "number",
    "number": "number",
    "boolean": "boolean",
    "null": "null",
}


class UnrenderableError(ValueError):
    """A schema construct the emitter has no accepted rendering for."""

    def __init__(self, where: str, what: str) -> None:
        super().__init__(f"{where}: {what}")


def ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[1]


def literal(value: object) -> str:
    return json.dumps(value)


def type_of(schema: dict[str, Any], depth: int, where: str) -> str:  # noqa: PLR0911 - one return per construct, each named in the module docstring
    """The TypeScript type for one schema, inline."""
    if "$ref" in schema:
        return f'components["schemas"]["{ref_name(schema["$ref"])}"]'
    for keyword in ("allOf", "prefixItems", "not"):
        if keyword in schema:
            raise UnrenderableError(where, f"`{keyword}` has no accepted rendering")
    if "const" in schema:
        return literal(schema["const"])
    if "enum" in schema:
        return " | ".join(literal(v) for v in schema["enum"])
    for keyword in ("oneOf", "anyOf"):
        if keyword in schema:
            return " | ".join(type_of(m, depth, where) for m in schema[keyword])
    kind = schema.get("type")
    if isinstance(kind, list):
        raise UnrenderableError(where, f"a `type` list {kind} has no accepted rendering")
    if kind in SCALARS:
        return SCALARS[kind]
    if kind == "array":
        inner = type_of(schema["items"], depth, where)
        return f"({inner})[]" if " | " in inner else f"{inner}[]"
    if kind == "object":
        return object_type(schema, depth, where)
    raise UnrenderableError(
        where, f"no `type`, `$ref`, `const`, `enum`, `oneOf` or `anyOf` in {sorted(schema)}"
    )


def object_type(schema: dict[str, Any], depth: int, where: str) -> str:
    """An inline object: properties with `?` for the optional ones, or an index signature."""
    pad = INDENT * (depth + 1)
    close = INDENT * depth
    if "properties" in schema:
        required = set(schema.get("required", []))
        lines = ["{"]
        for name, sub in schema["properties"].items():
            if "enum" in sub:
                lines.append(f"{pad}/** @enum {{unknown}} */")
            elif "const" in sub:
                lines.append(f"{pad}/** @constant */")
            mark = "" if name in required else "?"
            lines.append(f"{pad}{name}{mark}: {type_of(sub, depth + 1, f'{where}.{name}')};")
        lines.append(f"{close}}}")
        return "\n".join(lines)
    if "additionalProperties" in schema:
        inner = type_of(schema["additionalProperties"], depth + 1, where)
        return f"{{\n{pad}[key: string]: {inner};\n{close}}}"
    return "Record<string, never>"


def render_components(schemas: dict[str, dict[str, Any]]) -> list[str]:
    out = ["export interface components {", f"{INDENT}schemas: {{"]
    for name, schema in schemas.items():
        out.append(f"{INDENT * 2}/** {schema.get('title', name)} */")
        out.append(f"{INDENT * 2}{name}: {type_of(schema, 2, name)};")
    out.append(f"{INDENT}}};")
    out.extend(
        f"{INDENT}{k}: never;"
        for k in ("responses", "parameters", "requestBodies", "headers", "pathItems")
    )
    out.append("}")
    return out


def render_parameters(params: list[dict[str, Any]], depth: int) -> list[str]:
    pad = INDENT * depth
    out = [f"{pad}parameters: {{", f"{pad}{INDENT}query?: never;", f"{pad}{INDENT}header?: never;"]
    path = [p for p in params if p.get("in") == "path"]
    if path:
        out.append(f"{pad}{INDENT}path: {{")
        out.extend(
            f"{pad}{INDENT * 2}{p['name']}: {type_of(p['schema'], depth + 2, p['name'])};"
            for p in path
        )
        out.append(f"{pad}{INDENT}}};")
    else:
        out.append(f"{pad}{INDENT}path?: never;")
    out.append(f"{pad}{INDENT}cookie?: never;")
    out.append(f"{pad}}};")
    return out


def render_paths(paths: dict[str, dict[str, Any]]) -> list[str]:
    out = ["export interface paths {"]
    for path, item in paths.items():
        out.append(f'{INDENT}"{path}": {{')
        out.extend(render_parameters([], 2))
        for method in METHODS:
            if method in item:
                out.append(f'{INDENT * 2}{method}: operations["{item[method]["operationId"]}"];')
            else:
                out.append(f"{INDENT * 2}{method}?: never;")
        out.append(f"{INDENT}}};")
    out.append("}")
    return out


def render_operation(name: str, op: dict[str, Any]) -> list[str]:
    pad = INDENT * 2
    out = [
        f"{INDENT}{name}: {{",
        *render_parameters(op.get("parameters", []), 2),
        f"{pad}requestBody?: never;",
        f"{pad}responses: {{",
    ]
    for status, response in op["responses"].items():
        out.append(f"{pad}{INDENT}/** @description {response['description']} */")
        out.append(f"{pad}{INDENT}{status}: {{")
        out.append(f"{pad}{INDENT * 2}headers: {{")
        out.append(f"{pad}{INDENT * 3}[name: string]: unknown;")
        out.append(f"{pad}{INDENT * 2}}};")
        content = response.get("content")
        if content:
            out.append(f"{pad}{INDENT * 2}content: {{")
            for media, body in content.items():
                out.append(
                    f'{pad}{INDENT * 3}"{media}": {type_of(body["schema"], 5, f"{name} {status} {media}")};'
                )
            out.append(f"{pad}{INDENT * 2}}};")
        else:
            out.append(f"{pad}{INDENT * 2}content?: never;")
        out.append(f"{pad}{INDENT}}};")
    out.append(f"{pad}}};")
    out.append(f"{INDENT}}};")
    return out


def render_operations(paths: dict[str, dict[str, Any]]) -> list[str]:
    out = ["export interface operations {"]
    for item in paths.values():
        for method in METHODS:
            if method in item:
                out.extend(render_operation(item[method]["operationId"], item[method]))
    out.append("}")
    return out


def body(spec: dict[str, Any]) -> str:
    """Everything below the header, in the oracle's shape."""
    lines = [
        *render_paths(spec["paths"]),
        "export type webhooks = Record<string, never>;",
        *render_components(spec["components"]["schemas"]),
        "export type $defs = Record<string, never>;",
        *render_operations(spec["paths"]),
    ]
    return "\n".join(lines) + "\n"


def header(spec_text: str) -> str:
    """The header, with the spec's digest over its TEXT - newline-normalised, never raw bytes.

    ⚠ The first cut hashed `read_bytes()`, and the Windows lane went red on the day it landed:
    git checks `openapi.json` out with CRLF there, so the same spec had a different digest on
    each platform while the rendered body was identical. `read_text` translates line endings on
    every platform, which is what makes the digest a fact about the spec and not about git.
    """
    digest = hashlib.sha256(spec_text.encode("utf-8")).hexdigest()
    return (
        "/**\n"
        " * GENERATED by scripts/emit_api_types.py from packages/truestill-app/openapi.json.\n"
        " * Do not edit: make check regenerates it and refuses every difference.\n"
        " * Regenerate: uv run python scripts/emit_api_types.py --write\n"
        f" * Spec sha256: {digest}\n"
        " */\n\n"
    )


def generate(spec_path: Path = SPEC) -> str:
    text = spec_path.read_text(encoding="utf-8")
    return header(text) + body(json.loads(text))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--write", action="store_true", help=f"write {TYPES.relative_to(ROOT).as_posix()}"
    )
    args = parser.parse_args(argv)
    text = generate()
    shown = TYPES.relative_to(ROOT).as_posix()
    if args.write:
        TYPES.parent.mkdir(parents=True, exist_ok=True)
        TYPES.write_text(text, encoding="utf-8")
        print(f"wrote {shown}")
        return 0
    if TYPES.exists() and TYPES.read_text(encoding="utf-8") == text:
        print(f"{shown} is current")
        return 0
    print(f"{shown} is stale; run: uv run python scripts/emit_api_types.py --write")
    return 1


if __name__ == "__main__":
    sys.exit(main())
