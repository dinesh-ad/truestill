"""The TypeScript compiler runs in the gate, and the flags it runs with are the ones agreed.

**Why this is a guard and not a note.** `make frontend` called `npx vite build` directly for the
whole life of the React seam, which skipped the `tsc --noEmit &&` in the frontend's own
`package.json` build script. Vite strips types; it does not check them. So `strict`,
`noUncheckedIndexedAccess` and every other flag in `tsconfig.json` were configured and read by
nothing - the config looked like a standard and enforced none of it. When the check was finally
run it was **not clean**: three `TS2591` errors in `vite.config.ts`, present since the seam
landed and invisible to `make check`, `make gate` and CI alike.

Two failure modes, one per test below: the gate stops running the compiler, or the compiler runs
with the strictness turned down. Either restores the silence.

**This file parses text and runs nothing.** No Node, no `npx`, no subprocess - `make check` is
green on a fresh clone with no Node installed (`PROJECT_STATUS.md` §0), and a guard that shelled
out to `tsc` would quietly break that promise to check a thing the browser lane already checks.
What is guarded here is that the *invocation exists*, which is exactly the part that went missing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

_REPO = Path(__file__).resolve().parents[3]
_MAKEFILE = _REPO / "Makefile"
_TSCONFIG = _REPO / "packages/truestill-app/frontend/tsconfig.json"

#: Flags whose removal would be invisible. Each earns its place:
#:
#: * `strict` - the floor.
#: * `noUncheckedIndexedAccess` - without it `list[i]` is typed `T` even when the index is past
#:   the end, so every array read lies. The highest-value flag beyond `strict` for a UI that
#:   indexes into photo lists.
#: * `noUnusedLocals` / `noUnusedParameters` - dead code in a bundle nobody reads.
#: * `noFallthroughCasesInSwitch` - the screen switch is a `switch`.
#: * `isolatedModules` - Vite transpiles file-by-file and cannot see across modules; without
#:   this, code that only type-checks whole-program compiles here and breaks in the bundle.
_REQUIRED_FLAGS = (
    "strict",
    "noUncheckedIndexedAccess",
    "noUnusedLocals",
    "noUnusedParameters",
    "noFallthroughCasesInSwitch",
    "isolatedModules",
)


def _frontend_recipe() -> str:
    """The body of the `frontend:` target, which is what the gate actually executes."""
    text = _MAKEFILE.read_text(encoding="utf-8")
    match = re.search(r"^frontend:\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert match, (
        "no `frontend:` target with a recipe found in the Makefile. Renaming the target is fine; "
        "this guard has to be pointed at the new name in the same commit."
    )
    return match.group(1)


_PACKAGE_JSON = _REPO / "packages/truestill-app/frontend/package.json"
_RELEASE = _REPO / ".github/workflows/release.yml"


def _resolved(recipe: str) -> str:
    """The recipe with every `npm run <script>` replaced by the script `package.json` defines.

    `(ajv)` (2026-09-03) moved the build's ONE definition into `package.json`'s `build` script,
    so the Makefile and the release workflow run the same words. This guard follows that
    indirection rather than reading the recipe's surface, so it still asserts on what executes.
    """
    scripts = json.loads(_PACKAGE_JSON.read_text(encoding="utf-8"))["scripts"]

    def script(match: re.Match[str]) -> str:
        name = match.group(1)
        assert name in scripts, f"`npm run {name}` names no script in package.json"
        return str(scripts[name])

    return re.sub(r"npm run ([\w:-]+)", script, recipe)


def test_the_frontend_target_typechecks_before_it_builds() -> None:
    """THE GUARD. `vite build` alone strips types without checking them."""
    recipe = _resolved(_frontend_recipe())
    assert "tsc --noEmit" in recipe, (
        "`make frontend` does not run `tsc --noEmit`, so the TypeScript compiler never sees the "
        "code and every flag in tsconfig.json is decoration. Vite strips types; it does not "
        f"check them. Recipe was:\n{recipe}"
    )
    assert recipe.index("tsc --noEmit") < recipe.index("vite build"), (
        "`tsc --noEmit` runs after `vite build`, so a bundle is produced before the types are "
        "checked. Order it first, joined by `&&`, so a type error stops the build."
    )


def test_the_agreed_compiler_flags_are_still_set() -> None:
    """The other direction. A gate that runs `tsc` against a permissive config checks nothing,
    and dropping one line from a JSON file is a quieter regression than deleting the step."""
    config = json.loads(_TSCONFIG.read_text(encoding="utf-8"))["compilerOptions"]
    missing = [flag for flag in _REQUIRED_FLAGS if config.get(flag) is not True]
    assert not missing, (
        f"tsconfig.json no longer sets {missing} to true. Each of these closes a hole the others "
        "leave open - see this module's list for why each one is here. Turning one off is a "
        "decision that belongs in its own commit with its reason."
    )


def test_the_flag_list_is_not_vacuous() -> None:
    """Cry-wolf guard. An empty `_REQUIRED_FLAGS`, or a tsconfig this stopped being able to
    parse, would make the test above pass while checking nothing - the empty-set-reads-as-success
    trap this repo keeps finding."""
    assert len(_REQUIRED_FLAGS) >= 5, "the required-flag list has been emptied out"
    config = json.loads(_TSCONFIG.read_text(encoding="utf-8"))
    assert config.get("compilerOptions"), f"no compilerOptions parsed from {_TSCONFIG}"


def _release_steps() -> list[dict[str, object]]:
    """The build job's steps, in order, from the workflow as YAML - never from its text, whose
    comments name the same commands. The first mutation proof of this guard survived on exactly
    that: `npm run build` removed from the step and still present in a comment."""
    doc = yaml.safe_load(_RELEASE.read_text(encoding="utf-8"))
    for job in doc["jobs"].values():
        steps = list(job.get("steps") or [])
        if any("pyinstaller" in str(step.get("run", "")) for step in steps):
            return steps
    msg = "no job in release.yml runs pyinstaller; the guard is pointed at the wrong workflow"
    raise AssertionError(msg)


def test_the_release_builds_the_bundle_the_lane_builds_and_before_it_freezes() -> None:
    """`(ajv)`: the browser lane built the bundle through `make frontend` and the release built
    nothing, so the lane was green for nineteen days over a bundle the release never had. The
    release now runs the same `npm run build` and does it BEFORE PyInstaller collects the tree."""
    assert "npm run build" in _frontend_recipe(), (
        "the lane's build is no longer package.json's script"
    )
    steps = _release_steps()
    runs = [str(step.get("run", "")) for step in steps]
    build = [i for i, run in enumerate(runs) if "npm run build" in run]
    freeze = [i for i, run in enumerate(runs) if "pyinstaller" in run]
    assert build, "no release step runs `npm run build`; the artifact will carry no bundle"
    assert "npm ci" in runs[build[0]], "the release installs the frontend without the lockfile"
    assert freeze, "no release step runs pyinstaller"
    assert build[0] < min(freeze), (
        "the bundle is built AFTER PyInstaller collected the static tree; the artifact will not carry it"
    )
    node = [step for step in steps if str(step.get("uses", "")).startswith("actions/setup-node")]
    assert node, "no setup-node step; npm has no pinned Node to run under"
    with_ = node[0].get("with")
    assert isinstance(with_, dict)
    assert with_.get("node-version-file") == "packages/truestill-app/frontend/.nvmrc"
