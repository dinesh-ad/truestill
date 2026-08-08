"""Propose a name for a cluster from the folders its members came from. Pure - no I/O, no catalog.

**Suggester-only.** `layout.event_folder` stays path-safety-only and must not start altering
names for taste: a name the USER types keeps everything it has. This module chooses what to
PROPOSE, never what to overrule.

**Deepest-qualifying, never strongest.** A name's share rises monotonically with depth, because
an ancestor set is a superset of its descendants - so "the strongest majority anywhere" always
degenerates to a library root (`Vintage`, `Crypto Folder`). Measured on the real catalog and
rejected. The first level, counting up from the file, that carries a real majority wins.

**70% is UNTUNED.** Twenty-one clusters cannot distinguish 70 from 75, and one of them sits at
70.4%. It is a stated starting point, not a fitted parameter, and it must not be tuned against
this corpus.

**The suggestion stays verbose rather than clever, and that is the design.**
`Trichy~Thanjavur~Gokul's Marriage` is three labels a human joined - two places and an occasion -
and no structural rule can separate them: to a counter, `Trichy` and `Gokul` are identical. So the
whole string is proposed. Verbose and truthful beats clever and wrong, and the cost is one edit in
a box the user was going to touch anyway.

That string is the MOTIVATING CASE for two future items, recorded here rather than as a TODO:
an optional naming helper (a language model reading it knows Trichy is a city and a marriage is an
occasion - this is the case that earns it its place), and GPS place-name subtraction (if reverse
geocoding puts the photos in Trichy and Thanjavur, those tokens are redundant with location the
file already carries, and the remainder is `Gokul Marriage` - mechanical, offline, no model, and
it falls out of the GPS work already in the backlog). **Both are future. Neither is in scope.**

**Order of operations** (each step can only take away, so silence is always reachable):
tidy punctuation, strip a redundant year, reject junk and roots, then reject what has nothing
left. Anything leaving no alphanumeric is silence.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence

#: Levels above the file that may supply a name; level 0 is the folder the file sat in. Bounded
#: because above this is library plumbing, and because it is what makes the cost linear.
MAX_LEVEL = 3

#: Share of a cluster's members a name needs to be proposed. **UNTUNED** - see the module note.
MAJORITY = 0.70

#: A four-digit year, as opposed to the two-digit `'14` shorthand.
_FULL_YEAR_DIGITS = 4

#: A POSSESSIVE is removed whole - `Gokul's Marriage` becomes `Gokul Marriage`, not
#: `Gokuls Marriage`. Read literally, "remove the apostrophe, substitute nothing" would leave the
#: orphaned `s`; both worked examples drop it, and dropping it is the more faithful reading of a
#: proper noun - `Gokul` is the person's name and `Gokuls` is not a word in any language. It stays
#: mechanical: one anchored pattern, no dictionary, so rule 3 is untouched.
_POSSESSIVE = re.compile("['\u2019\u2018`\u00b4]s\\b")

#: Any REMAINING apostrophe is removed outright, substituting nothing, so `B'day` becomes `Bday`
#: rather than `B day`.
#: The straight and curly apostrophes are the obvious two; the BACKTICK is here because it is
#: what `Trichy~Thanjavur~Gokul`s Marriage` actually contains on disk - long read as a display
#: mangling, it is real, and in sh it is command substitution rather than mere quoting.
_APOSTROPHES = str.maketrans("", "", "'\u2019\u2018`\u00b4")

#: Treated as word separators and replaced with a space. `-` is deliberately NOT here:
#: `TCS-M05-Batch`'s hyphens are part of the name, and the shipped folder format is
#: `2015-10-25 - <name>`, so a hyphen inside the name makes one character do two jobs.
#: `&` is not here either - it is a word (`Siveram & My Treat ILP`).
_SEPARATORS = re.compile(r"[~_+|\\/·•]+")

_WHITESPACE = re.compile(r"\s+")

#: Surrounding brackets and quotes, peeled in pairs: `(Goa Trip)`, `"Goa"`, `[Goa]`.
_WRAPPERS = (
    ("(", ")"),
    ("[", "]"),
    ("{", "}"),
    ("<", ">"),
    ('"', '"'),
    ("\u00ab", "\u00bb"),
    ("\u201c", "\u201d"),
)

#: Trimmed from the ENDS only. Periods and hyphens survive INSIDE a name - `J.R. Tolkien` keeps
#: its initials, `TCS-M05-Batch` keeps its hyphens - so this is anchored, never global.
_EDGE_PUNCTUATION = " -_~!?.,;:"

#: A leading date, which the `{yyyy}/{yyyy}-{mm}` parents already carry, exactly as a trailing
#: year does. `2015_10_25 Gokuls-Marriage` proposes `Gokuls-Marriage`, not silence: the folder
#: does name an event and only its prefix is redundant.
_LEADING_DATE = re.compile(r"^\d{4}([-_/. ]\d{1,2}){0,2}\s+(?=\S)")

#: Trailing year, in the shapes folders actually use: `2014`, `14`, `(2014)`, `- 2014`.
#: Anchored at the end and preceded by a separator, so `TCS-M05-Batch` and `IMG2015x` are safe.
_TRAILING_YEAR = re.compile(r"[\s(\[-]+(\d{2}|\d{4})[)\]]?\s*$")

#: Names that carry no event, whatever else is true of them.
_JUNK_EXACT = frozenset(
    {
        "dcim",
        "camera",
        "camera uploads",
        "camerauploads",
        "screenshots",
        "screenshot",
        "pictures",
        "picture",
        "photos",
        "photo",
        "images",
        "image",
        "img",
        "video",
        "videos",
        "movies",
        "media",
        "downloads",
        "download",
        "takeout",
        "google photos",
        "whatsapp",
        "whatsapp images",
        "telegram",
        "instagram",
        "facebook",
        "saved",
        "misc",
        "untitled",
        "temp",
        "tmp",
        "backup",
        "backups",
        "restored",
        "recovered",
        "import",
        "imports",
        "input",
        "output",
        "export",
        "exports",
        "unsorted",
        "sorted",
        "all",
        "src",
        "home",
    }
)

_JUNK_PATTERNS = tuple(
    re.compile(pattern, flags)
    for pattern, flags in (
        (r"^\d{3}[a-z]{5}$", re.I),  # 100APPLE, 101MSDCF
        (r"^\d{3}_?\w{0,6}$", re.I),  # 100MEDIA, 100_FUJI
        (r"^new folder( ?\(\d+\))?$", re.I),
        (r"^\d{4}$", 0),  # a bare year
        (r"^\d{4}[-_/.]\d{1,2}", 0),  # 2015-07, 2015-07-29
        (r"^\d{6,8}$", 0),  # 20150729
        (r"^day ?\d+$", re.I),  # Day 1 - structural, not an event
        # Month names, FULL or standard abbreviation only. A `[a-z]*` suffix here was far too
        # greedy: it read `Marys` as `mar` + anything, and would equally have eaten `Maryland`,
        # `Junction`, `Novel` and `Octopus`. The classifier never fired once on the real corpus,
        # so nothing exercised it until a test happened to name someone Mary.
        (
            (
                r"^(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?"
                r"|sep(t|tember)?|oct(ober)?|nov(ember)?|dec(ember)?)( \d{2,4})?$"
            ),
            re.I,
        ),
        (r"^takeout", re.I),
        (r"^copy of\b", re.I),
        (r"^untitled\b", re.I),
        (r"^(new )?folder( ?\(\d+\))?$", re.I),
        (r"^\(?\d+\)?$", 0),  # a bare counter, bracketed or not
        (r"^(whatsapp|telegram|signal|viber)\b", re.I),
        (r"^(wa|img|vid|dsc|pxl|mvimg)[-_ ]?\d+$", re.I),
        (r"^(sent|received|documents|audio|voice notes|stickers|animated gifs)$", re.I),
        (r"^scratch[-_]", re.I),
        (r"^pytest", re.I),
        (r"^[a-f0-9]{16,}$", re.I),  # hash-like
    )
)


def _has_content(name: str) -> bool:
    """Whether anything meaningful survived tidying.

    NOT `isalnum` alone. Tamil, Devanagari and Han are alphanumeric to Python and pass either
    way, but an emoji is not, and a folder named with one is still a real name a person chose.
    The test is therefore "anything that is not punctuation or space", so a suggestion can be
    emoji and only genuinely empty leftovers fall silent.
    """
    return any(not character.isspace() and character not in _EDGE_PUNCTUATION for character in name)


def is_junk(name: str) -> bool:
    """Whether a folder name carries no event, whatever a majority of members share it."""
    cleaned = (name or "").strip()
    if not cleaned:
        return True
    if cleaned.casefold() in _JUNK_EXACT:
        return True
    return any(pattern.search(cleaned) for pattern in _JUNK_PATTERNS)


def tidy(name: str) -> str:
    """Mechanical, dictionary-free punctuation tidying. **Never spelling correction.**

    Siveram, Trichy, Thanjavur, Gokul and Wayanad are proper nouns no dictionary holds. A speller
    would rewrite a real name into a wrong one while looking authoritative - worse than silence,
    because the whole value of a suggestion is that it is visible evidence from the user's own
    folder. A corrected word is no longer evidence of anything.
    """
    cleaned = (name or "").strip()
    for opening, closing in _WRAPPERS:
        if len(cleaned) > 2 and cleaned.startswith(opening) and cleaned.endswith(closing):  # noqa: PLR2004
            cleaned = cleaned[1:-1].strip()
    cleaned = _POSSESSIVE.sub("", cleaned).translate(_APOSTROPHES)
    cleaned = _SEPARATORS.sub(" ", cleaned)
    cleaned = _LEADING_DATE.sub("", cleaned)
    # camelCase is NOT split. `GokulsMarriage` stays whole: splitting would break `TCS-M05` and
    # would turn `McDonald` into `Mc Donald`, and a wrong split looks authoritative - the exact
    # failure this module avoids everywhere else. Case is left as found; the user's
    # capitalisation is evidence, not noise.
    return _WHITESPACE.sub(" ", cleaned).strip(_EDGE_PUNCTUATION)


def strip_year(name: str, year: int | None) -> str:
    """Drop a trailing year that only repeats the one the folder tree already carries.

    Only when it MATCHES the cluster's own year. A year that disagrees is evidence the folder is
    not about this cluster, and evidence must reach the person rather than be tidied away.
    """
    if year is None:
        return name
    match = _TRAILING_YEAR.search(name)
    if match is None:
        return name
    digits = match.group(1)
    same = int(digits) == year if len(digits) == _FULL_YEAR_DIGITS else int(digits) == year % 100
    return name[: match.start()].rstrip(" -") if same else name


def suggest_name(
    chains: Sequence[Sequence[str]],
    *,
    year: int | None = None,
    roots: Collection[str] = (),
) -> str | None:
    """A name to propose for a cluster, or ``None`` when the folders do not say.

    ``chains`` is one entry per member: its ancestor folder names, **deepest first**. A member
    with no usable source path contributes an empty chain and **still counts in the denominator** -
    missing evidence weakens a claim rather than being quietly excluded from it.

    **O(members x MAX_LEVEL)** time, which is linear in members since the depth is a constant, and
    **O(members)** space. No filesystem access: every name here came from the catalog.

    Never raises. A suggestion sits behind a naming screen and may not block it or throw.
    """
    total = len(chains)
    if not total:
        return None
    needed = total * MAJORITY
    root_names = {root.casefold() for root in roots}

    for level in range(MAX_LEVEL + 1):
        counts: dict[str, int] = {}
        for chain in chains:
            if len(chain) > level:
                name = chain[level]
                counts[name] = counts.get(name, 0) + 1
        if not counts:
            continue
        winner, held = max(counts.items(), key=lambda item: item[1])
        if held < needed:
            continue
        # Rule 5's order. Each step only takes away, so a candidate can fall to silence at any
        # of them - and a level that fails is skipped rather than ending the search, because a
        # deeper junk folder must not hide a real name above it (`Day 1` over `Wayanad '14`).
        candidate = strip_year(tidy(winner), year)
        if winner.casefold() in root_names or candidate.casefold() in root_names:
            continue
        # Judged on the CANDIDATE, per rule 5's order, not on the raw name. Judging the raw
        # would undo the tidying that precedes it: `2015_10_25 Gokuls-Marriage` reads as a bare
        # date to `^\d{4}[-_/.]\d{1,2}` and would be discarded, when only its prefix is
        # redundant and `Gokuls-Marriage` is exactly the name the folder is offering.
        if is_junk(candidate):
            continue
        if not _has_content(candidate):
            continue
        return candidate
    return None
