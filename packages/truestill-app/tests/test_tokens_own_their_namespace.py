"""No design token may sit in a namespace Tailwind v4 claims.

**Why this exists before Tailwind does.** `tokens.css` is the source of truth for colour, type and
spacing, and it stays that way through the React migration - Tailwind is meant to *consume* it via
`@theme inline`, not to become a second home for the same values. That plan has one failure mode,
and it is not a build error.

**Measured in a Tailwind 4.3.3 spike rather than read.** Tailwind emits its own theme variables
inside `@layer theme`; `tokens.css` is unlayered; **unlayered wins the cascade**. So a token named
`--radius-md` silently redefines what `rounded-md` means for every shadcn component on the page.
Nothing errors, no build fails - the utility just quietly means something else. That is worse than
a break, and it is invisible to every other test here.

The same spike ruled out the alternative. `@theme { --radius-*: initial }` does reset the
namespace, and it removes the utilities with it: `rounded-md`, `text-sm` and `text-muted` stopped
being generated at all, which breaks the shadcn components that ship those classes. Reset and keep
is only expressible as `--radius-md: var(--radius-md)`, a documented same-name self-reference
breakage. Renaming was the option that worked, so renaming is what this guard protects.

**One rename was not about collisions at all**, and it is the reason this is worth a test rather
than a note. `--text-*` was carrying two unrelated meanings: a type scale (`--text-sm`) *and* text
colours (`--text-muted`). `--text-*` is Tailwind's FONT-SIZE namespace, so the colour would have
landed there and produced a `text-muted` utility meaning a size. Splitting them into `--type-*`
and `--fg-*` fixed an ambiguity that predated Tailwind and would have outlived it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TOKENS = Path(__file__).resolve().parents[1] / "src/truestill_app/static/tokens.css"

#: Tailwind v4's theme namespaces. A custom property named `--<namespace>-<something>` is claimed
#: by Tailwind and will generate or redefine utilities. Taken from the v4 theme documentation.
TAILWIND_NAMESPACES = frozenset(
    {
        "color",
        "font",
        "text",
        "font-weight",
        "tracking",
        "leading",
        "breakpoint",
        "container",
        "spacing",
        "radius",
        "shadow",
        "inset-shadow",
        "drop-shadow",
        "blur",
        "perspective",
        "aspect",
        "ease",
        "animate",
    }
)


def _declared() -> list[str]:
    """Every custom property `tokens.css` declares, without the leading dashes."""
    return sorted(set(re.findall(r"^\s*--([a-z0-9-]+)\s*:", TOKENS.read_text(), re.MULTILINE)))


def test_tokens_css_declares_something() -> None:
    """The cry-wolf guard for the guard. A regex that silently matched nothing would make every
    assertion below vacuously true - the empty-set-reads-as-success trap, one level up."""
    names = _declared()
    assert len(names) > 30, f"only parsed {len(names)} tokens; the regex has stopped matching"


@pytest.mark.parametrize("namespace", sorted(TAILWIND_NAMESPACES))
def test_no_token_sits_in_a_tailwind_namespace(namespace: str) -> None:
    """`--radius-md` in our file silently redefines `rounded-md` in every shadcn component.

    Parametrized per namespace so a failure names the one that collided rather than handing back
    a list to read.
    """
    offenders = [n for n in _declared() if n.startswith(f"{namespace}-")]
    assert not offenders, (
        f"these tokens sit in Tailwind's --{namespace}-* namespace and would silently redefine "
        f"its utilities: {['--' + o for o in offenders]}. Rename them; --{namespace}-*: initial "
        "removes the utilities entirely (measured), which breaks the shadcn components using them."
    )


def test_the_type_scale_and_the_text_colours_are_not_the_same_namespace() -> None:
    """The ambiguity that predated Tailwind: `--text-sm` was a SIZE and `--text-muted` a COLOUR.

    Asserted as the property rather than as "no `--text-*` exists", so it keeps meaning something
    if the names change again: sizes live under one prefix, colours under another, and no prefix
    carries both.
    """
    names = _declared()
    sizes = {n for n in names if n.startswith("type-")}
    colours = {n for n in names if n == "fg" or n.startswith("fg-")}

    assert sizes, "the type scale is gone"
    assert colours, "the text colours are gone"
    assert not (sizes & colours), f"one prefix carries both sizes and colours: {sizes & colours}"
