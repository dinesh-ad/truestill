"""The bundled mono font travels with the notice Bitstream Vera requires.

**Why this is a source-tree test and not only a browser one.** The obligation is about *copies*,
not about rendering: Vera requires the notice to be included "in all copies of one or more of the
Font Software typefaces". A browser test can prove the font renders; only this can prove the
notice sits where every copy will carry it.

**Why beside the font and not in `brand/`.** `brand/` is not packaged - the wheel contains
`truestill_app/static/*` and nothing else. A notice there would stay behind while the typefaces
travelled, which is the exact failure the clause names. `brand/LICENSE-DejaVu.txt` existed once
(`c7c923e`) and was correctly deleted in `8b31b03` when the derived outlines left; it is not
revived, because that location cannot satisfy the condition now that we ship the font itself.
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "truestill_app" / "static"
FONTS = STATIC / "fonts"
LICENCE = FONTS / "LICENSE-DejaVu.txt"
TOKENS_CSS = STATIC / "tokens.css"

# Book and Bold only. 600 resolves to Bold by CSS weight matching, so the wordmark needs no
# separate SemiBold - measured, not assumed: at 18px, weight 600 and weight 700 rasterise to
# byte-identical bitmaps while 400 differs.
FACES = ("DejaVuSansMono.ttf", "DejaVuSansMono-Bold.ttf")


def test_every_shipped_face_is_present_and_is_really_a_truetype_file() -> None:
    """A truncated or LFS-pointer font would satisfy `exists()` and render nothing."""
    for face in FACES:
        path = FONTS / face
        assert path.is_file(), f"{face} is missing from static/fonts/"
        head = path.read_bytes()[:4]
        assert head == b"\x00\x01\x00\x00", f"{face} is not a TrueType file (magic {head!r})"
        assert path.stat().st_size > 100_000, f"{face} is implausibly small - truncated?"


def test_the_vera_notice_ships_beside_the_typefaces() -> None:
    """The condition is on copies of the typefaces, so the notice lives with them."""
    assert LICENCE.is_file(), "the Bitstream Vera notice is not beside the fonts"
    text = LICENCE.read_text(encoding="utf-8")
    # The canonical text is hard-wrapped and must NOT be reflowed to suit an assertion, so
    # phrases are matched against a whitespace-flattened copy.
    flat = " ".join(text.split())

    # The permission notice itself.
    assert "Permission is hereby granted, free of charge" in flat
    assert "reproduce and distribute the Font Software" in flat

    # The clause that binds us, quoted so a future edit cannot quietly drop it.
    assert "shall be included in all copies of one or more of the Font Software typefaces" in flat

    # THE COPYRIGHT AND TRADEMARK NOTICES. The clause names these FIRST ("The above copyright
    # and trademark notices AND this permission notice"), and the deleted brand/ file omitted
    # them - it opened at "Permission is hereby granted". That was thin for outlines and is not
    # acceptable for shipping the font.
    assert "Copyright (c) 2003 by Bitstream, Inc." in flat, "the copyright notice is missing"
    assert "Bitstream Vera is a trademark of Bitstream, Inc." in flat, "trademark notice missing"
    assert "DejaVu changes are in public domain." in flat, "the DejaVu notice is missing"


def test_nothing_is_sold_by_itself_and_the_reserved_name_clause_is_recorded() -> None:
    """Both constraints are quoted in the file, so a reader meets them without leaving the repo.

    Neither binds us today - we ship upstream 2.37 byte-for-byte inside a larger package - but
    "does not apply" is a conclusion, and the text it was drawn from has to be present for anyone
    to check it.
    """
    text = LICENCE.read_text(encoding="utf-8")
    assert "may be sold as part of a larger software package" in text
    assert 'renamed to names not containing either the words "Bitstream"' in text


def test_the_font_stack_leads_with_the_bundled_family() -> None:
    """Bundled first, existing stack retained behind it.

    The fallback is kept deliberately: if a bundle ever fails to carry the file, the app degrades
    to exactly today's behaviour rather than to an unstyled default.
    """
    tokens = TOKENS_CSS.read_text(encoding="utf-8")
    match = re.search(r"--family-mono:\s*([^;]+);", tokens)
    assert match is not None, "--family-mono is not declared"
    stack = [f.strip().strip('"').strip("'") for f in match.group(1).split(",")]

    assert stack[0] == "DejaVu Sans Mono", f"the bundled family does not lead the stack: {stack}"
    for kept in ("ui-monospace", "monospace"):
        assert kept in stack, f"{kept} was dropped from the fallback stack: {stack}"


def test_the_font_is_self_hosted_with_no_external_request_and_no_local_shortcut() -> None:
    """Offline-first: nothing may reach the network, and `local()` is banned on purpose.

    `local("DejaVu Sans Mono")` would look like a free optimisation and would reintroduce the
    exact variance the bundle exists to remove - a user's installed DejaVu can be any version.
    The bundled file must always win.
    """
    tokens = TOKENS_CSS.read_text(encoding="utf-8")
    faces = re.findall(r"@font-face\s*\{([^}]*)\}", tokens, re.S)
    assert faces, "no @font-face rule found"

    mono = [f for f in faces if "DejaVu Sans Mono" in f]
    assert len(mono) == len(FACES), f"expected {len(FACES)} DejaVu faces, found {len(mono)}"

    for rule in mono:
        assert "local(" not in rule, "local() reintroduces the machine variance we are removing"
        for scheme in ("http://", "https://", "//fonts.", "cdn"):
            assert scheme not in rule, f"an external reference appeared in @font-face: {scheme}"
        assert "/static/fonts/" in rule, "the face is not served from our own static directory"
        assert "font-display: swap" in rule, "font-display: swap is not declared"


def test_only_the_two_weights_we_ship_are_declared() -> None:
    """Declaring a weight with no file behind it is worse than not declaring it.

    No italic face is shipped and none is needed: the only `font-style: italic` in app.css is
    `.input::placeholder`, which resets `font-family` to `var(--family-sans)`. Asserted here so
    that adding a mono italic forces the question rather than silently getting a synthesised
    oblique.
    """
    tokens = TOKENS_CSS.read_text(encoding="utf-8")
    faces = re.findall(r"@font-face\s*\{([^}]*)\}", tokens, re.S)
    weights = sorted(
        int(m.group(1))
        for rule in faces
        if "DejaVu Sans Mono" in rule
        for m in [re.search(r"font-weight:\s*(\d+)", rule)]
        if m
    )
    assert weights == [400, 700], f"expected exactly weights 400 and 700, got {weights}"

    app_css = (STATIC / "app.css").read_text(encoding="utf-8")
    italic_blocks = [
        block
        for block in re.findall(r"\{[^}]*font-style:\s*italic[^}]*\}", app_css, re.S)
        if "--family-sans" not in block
    ]
    assert italic_blocks == [], (
        "an italic rule no longer resets to the sans stack; no mono italic face is shipped, "
        f"so this would be a synthesised oblique: {italic_blocks}"
    )
