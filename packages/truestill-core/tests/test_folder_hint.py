"""Proposing a name from the folders a cluster's members came from.

**Suggester-only, and the boundary is the point.** `layout.event_folder` stays path-safety-only:
it may not start altering names for taste, because a name the USER typed keeps everything it has.
This module chooses what to PROPOSE, never what to overrule.

**The character set was chosen from what is actually in this catalog**, not from a general idea of
punctuation, and the survey is worth recording because one entry corrected a premise:

======  =====================================  ==================================================
char    where it really appears                what happens to it
======  =====================================  ==================================================
``-``   ``TCS-M05-Batch``                      **kept** - part of the name, not a separator
``&``   ``Siveram & My Treat ILP``             **kept** - it is a word
``~``   ``Trichy~Thanjavur~Gokul`s Marriage``  separator -> space
``_``   ``test_skip_undated_names_skippe0``    separator -> space
``'``   ``Rajesh B'day``, ``Wayanad '14``      **removed**, substituting nothing
`````   ``Trichy~Thanjavur~Gokul`s Marriage``  **removed** - see below
======  =====================================  ==================================================

**The apostrophe in "Gokul's Marriage" is a BACKTICK on disk.** It had been read as a display
mangling in earlier reports; it is not, it is U+0060 in the folder name. That makes the removal
rule stronger rather than weaker: a backtick is command substitution in sh, not merely a quoting
character. The curly ``'`` (U+2019) is covered too - folders made on macOS or Windows carry it -
even though this catalog holds none, because the cost of covering it is one codepoint.

**No spelling correction, deliberately, and the reason belongs here so nobody adds it later.**
Siveram, Trichy, Thanjavur, Gokul, Wayanad are proper nouns no dictionary holds. A speller would
rewrite a real name into a wrong one while looking authoritative, which is worse than silence.
The whole value of a suggestion is that it is visible evidence from the user's own folder; a
corrected word is no longer evidence of anything.
"""

from __future__ import annotations

from truestill_core.folder_hint import suggest_name

# The real Wayanad shape: one photographer filed directly under the event, the others under a
# Day folder, so the event name sits at a DIFFERENT LEVEL for different members of one cluster.
_WAYANAD = (
    *([["Gokul CAM", "Wayanad '14", "2014"]] * 3),
    *([["Vj 1", "Day 1", "Wayanad '14", "2014"]] * 4),
    *([["DD 1", "Day 1", "Wayanad '14", "2014"]] * 3),
)


def test_the_event_name_is_found_above_day_folders_at_differing_depths() -> None:
    """No fixed depth reaches it: level 1 is 'Wayanad '14' for some members and 'Day 1' for others."""
    assert suggest_name(_WAYANAD, year=2014) == "Wayanad"


def test_a_library_root_is_never_proposed() -> None:
    """Silence, not 'Vintage'. Share rises monotonically with depth, so the roots always win on
    share alone - which is why 'strongest majority anywhere' was measured and rejected."""
    chains = [["Sea Diving", "2015", "Vintage", "Photos"]] * 9
    assert suggest_name(chains, year=2015, roots={"Vintage", "Photos"}) == "Sea Diving"
    assert suggest_name([["Vintage", "Photos"]] * 9, roots={"Vintage", "Photos"}) is None


# --- rule 1: apostrophes ------------------------------------------------------------------


def test_every_apostrophe_shape_is_removed_substituting_nothing() -> None:
    for raw in ("Gokul's Marriage", "Gokul\u2019s Marriage", "Gokul`s Marriage"):
        assert suggest_name([[raw]] * 9) == "Gokul Marriage", raw


def test_removing_an_apostrophe_leaves_no_double_space() -> None:
    """`B'day` must not become `B day`, and a trailing one must not leave a dangling space."""
    assert suggest_name([["Rajesh B'day"]] * 9) == "Rajesh Bday"
    assert suggest_name([["Marys'"]] * 9) == "Marys"


# --- rule 2: spaces, not hyphens ----------------------------------------------------------


def test_hyphens_inside_a_name_survive_untouched() -> None:
    """THE CRY-WOLF HALF for rule 2. `TCS-M05-Batch`'s hyphens are part of the name. A suggester
    that hyphenated word separators would also be free to rewrite these, and the shipped folder
    format is `2015-10-25 - <name>` - a space-hyphen-space separator - so a hyphen inside the
    name makes one character do two jobs in one string."""
    assert suggest_name([["TCS-M05-Batch"]] * 9) == "TCS-M05-Batch"


def test_spaces_between_words_are_never_converted_to_hyphens() -> None:
    assert suggest_name([["Phoenix Mall"]] * 9) == "Phoenix Mall"


# --- rule 4: mechanical punctuation tidying -----------------------------------------------


def test_the_real_wedding_folder_tidies_to_readable_words() -> None:
    raw = "Trichy~Thanjavur~Gokul`s Marriage"
    assert suggest_name([[raw]] * 9) == "Trichy Thanjavur Gokul Marriage"


def test_an_ampersand_is_a_word_and_stays() -> None:
    """`Siveram & My Treat ILP` reads as a name; dropping the & would damage it, and expanding it
    to 'and' would be inventing a word - the same failure as spelling correction."""
    assert suggest_name([["Siveram & My Treat ILP"]] * 9) == "Siveram & My Treat ILP"


def test_underscores_separate_and_runs_of_separators_collapse() -> None:
    assert suggest_name([["Goa__Trip~~2"]] * 9) == "Goa Trip 2"
    assert suggest_name([["~_Goa Trip_~"]] * 9) == "Goa Trip"


def test_a_proper_noun_is_never_corrected() -> None:
    """Rule 3 has no code of its own - it is the absence of a speller - so this is what pins it.
    Every one of these is a real place or person and none is in a dictionary."""
    for name in ("Siveram", "Trichy", "Thanjavur", "Wayanad", "Gokul"):
        assert suggest_name([[name]] * 9) == name


# --- rule 5: order of operations, and the year -------------------------------------------


def test_a_trailing_year_matching_the_cluster_is_stripped() -> None:
    """The `{yyyy}` parent already carries the year, so repeating it in the name is noise."""
    assert suggest_name([["Wayanad '14"]] * 9, year=2014) == "Wayanad"
    assert suggest_name([["Phoenix Mall 2015"]] * 9, year=2015) == "Phoenix Mall"


def test_a_year_that_disagrees_with_the_cluster_survives() -> None:
    """It is evidence that the folder is not about this cluster, so it must reach the person.

    The apostrophe still goes - rule 5 tidies BEFORE stripping, and rule 1 is unconditional - so
    what survives is the year itself, which is the part carrying the evidence.
    """
    assert suggest_name([["Wayanad '13"]] * 9, year=2014) == "Wayanad 13"


def test_a_year_inside_a_token_is_not_a_suffix() -> None:
    assert suggest_name([["TCS-M05-Batch"]] * 9, year=2005) == "TCS-M05-Batch"


def test_a_name_that_is_only_its_year_falls_silent() -> None:
    """Tidy, strip, then the emptiness check: nothing alphanumeric left means no suggestion."""
    assert suggest_name([["2015"]] * 9, year=2015) is None


# --- fallbacks: silence is the correct output ---------------------------------------------


def test_no_majority_is_silence() -> None:
    chains = [["Ar"], ["Vj"], ["DD"], ["Gk"], ["Thala"], ["Ramesh"], ["Ar"], ["Vj"], ["DD"]]
    assert suggest_name(chains) is None


def test_members_with_no_folder_at_all_still_count_against_the_majority() -> None:
    """Missing evidence weakens a claim rather than being quietly excluded from it."""
    assert suggest_name([["Sea Diving"]] * 7 + [[], []]) == "Sea Diving"
    assert suggest_name([["Sea Diving"]] * 6 + [[], [], [], []]) is None


def test_an_empty_cluster_and_a_junk_only_cluster_are_both_silent() -> None:
    assert suggest_name([]) is None
    assert suggest_name([["DCIM"]] * 9) is None
    assert suggest_name([["100APPLE"]] * 9) is None


def test_the_suggester_never_raises_on_anything_it_is_given() -> None:
    """It sits behind a screen; a suggestion feature may never block naming or throw."""
    for chains in ([[""]], [["   "]], [["///"]], [["\u2019"]], [["-"]], [["~"]]):
        assert suggest_name(chains * 9) is None


# --- rules 6 and 7: a CONSTRUCTED messy library ------------------------------------------
#
# EVERY NAME BELOW IS CONSTRUCTED, NOT OBSERVED. All 21 folder names in the corpus this was
# measured on are hand-made and clean, and the junk classifier never fired once against them.
# These are built from documented conventions - Android/WhatsApp export folders, camera DCIM
# naming, desktop "Copy of" and "New folder (2)" - so they exercise the rules; they are not
# evidence of what a real phone dump contains. The classifier's true rate is unknown.


def test_underscored_and_mixed_separator_names_read_as_words() -> None:
    assert suggest_name([["Gokuls_Marriage"]] * 9) == "Gokuls Marriage"
    assert suggest_name([["2015_10_25 Gokuls-Marriage"]] * 9) == "Gokuls-Marriage"


def test_repeated_and_edge_punctuation_is_trimmed_but_inner_punctuation_is_not() -> None:
    assert suggest_name([["Rajesh bday!!!"]] * 9) == "Rajesh bday"
    assert suggest_name([["J.R. Tolkien"]] * 9) == "J.R. Tolkien"


def test_surrounding_brackets_and_quotes_are_peeled() -> None:
    for wrapped in ("(Goa Trip)", "[Goa Trip]", '"Goa Trip"', "“Goa Trip”"):
        assert suggest_name([[wrapped]] * 9) == "Goa Trip", wrapped


def test_non_latin_scripts_and_emoji_pass_through_unharmed() -> None:
    """A Tamil or Devanagari folder name is a real name, and so is one a person wrote in emoji.

    `isalnum` alone would have failed this: the scripts pass, the emoji does not, and stripping a
    name to nothing because it is not Latin is the worst outcome available here.
    """
    for name in ("கோகுல் திருமணம்", "गोकुल विवाह", "北海道 2015", "🎂 Rajesh"):
        assert suggest_name([[name]] * 9) is not None, name
    assert suggest_name([["கோகுல் திருமணம்"]] * 9) == "கோகுல் திருமணம்"
    assert suggest_name([["🎂🎉"]] * 9) == "🎂🎉"


def test_camel_case_is_never_split() -> None:
    """A wrong split looks authoritative. `McDonald` must not become `Mc Donald`."""
    assert suggest_name([["GokulsMarriage"]] * 9) == "GokulsMarriage"
    assert suggest_name([["McDonald Farewell"]] * 9) == "McDonald Farewell"


def test_case_is_left_exactly_as_found() -> None:
    """The user's capitalisation is evidence, not noise."""
    assert suggest_name([["gokuls marriage"]] * 9) == "gokuls marriage"
    assert suggest_name([["GOKULS MARRIAGE"]] * 9) == "GOKULS MARRIAGE"


def test_the_widened_junk_patterns_are_rejected() -> None:
    """CONSTRUCTED from documented conventions - see the section note. Not observed."""
    for junk in (
        "New folder (2)",
        "Copy of Goa Trip",
        "Untitled folder",
        "WhatsApp Images",
        "Telegram Documents",
        "Sent",
        "Voice Notes",
        "IMG_1234",
        "DSC01234",
        "(3)",
        "100APPLE",
    ):
        assert suggest_name([[junk]] * 9) is None, junk


def test_a_real_name_that_merely_resembles_junk_survives() -> None:
    """THE CRY-WOLF HALF for rule 7, and the one that matters most now that the classifier is
    wider. Every widened pattern is a chance to eat a real name."""
    for real in (
        "Marys Baptism",
        "Maryland Trip",
        "Junction Cafe",
        "Novel Launch",
        "Octopus Diving",
        "Mayfair Wedding",
        "Copyright Talk",
        "Folders Museum",
        "Newquay 2019",
    ):
        assert suggest_name([[real]] * 9) == real, real


def test_a_deeper_name_wins_over_a_stronger_shallower_one() -> None:
    """DEEPEST-QUALIFYING, NEVER STRONGEST - and this is the only test that can tell them apart.

    Share rises monotonically with depth, so a parent always scores at least as well as its
    child. Here `Sea Diving` holds 8 of 10 and its parent `Vintage Trips` holds all 10: taking
    the strongest would propose the parent, which is the failure that made a real measurement
    propose `Vintage` and `Crypto Folder` over the events inside them.

    The earlier tests could not catch this. In every one of them the deepest qualifying level was
    ALSO the strongest, so a mutation swapping the rule passed all 26 of them.
    """
    chains = [["Sea Diving", "Vintage Trips"]] * 8 + [["Boat Day", "Vintage Trips"]] * 2
    assert suggest_name(chains) == "Sea Diving"


def test_an_apostrophe_that_is_not_a_possessive_costs_no_letters() -> None:
    """Irish and Italian surnames, where a possessive rule could do real damage.

    `O'Brien` becomes `OBrien`: no letter lost, no space inserted. It cannot keep the apostrophe -
    rule 1 is unconditional, and U+0060/U+0027 are shell metacharacters - so whole-minus-the-mark
    is the best available, and it is what the user sees before accepting anything.

    What saves these is the ANCHORING: the possessive pattern requires a LOWERCASE `s` followed by
    a word boundary. `O'Sullivan` has an uppercase S, and even case-insensitively the `\\b` fails
    because a letter follows. Loosen either half and `O'Sullivan` becomes `O`.
    """
    assert suggest_name([["O'Brien"]] * 9) == "OBrien"
    assert suggest_name([["O'Sullivan"]] * 9) == "OSullivan"
    assert suggest_name([["D'Angelo"]] * 9) == "DAngelo"
    assert suggest_name([["O'Brien's Party"]] * 9) == "OBrien Party"


def test_a_trailing_possessive_is_not_the_possessive_shape() -> None:
    """`Boys' Day` is `s` then apostrophe, not apostrophe then `s`, so only the mark goes."""
    assert suggest_name([["Boys' Day"]] * 9) == "Boys Day"
    assert suggest_name([["Girls' School Trip"]] * 9) == "Girls School Trip"
