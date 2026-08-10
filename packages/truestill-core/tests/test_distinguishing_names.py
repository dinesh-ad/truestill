"""A drive is never named ambiguously - `(acr)`.

**The defect is a confident wrong pointer, which is worse than no pointer.** The strip said
*"never checked: Morrowkeep"* and the maintainer could not tell which Morrowkeep: a local folder,
a cloud folder and an external disk may all carry that name. Sent to the wrong one, a person finds
their files, concludes nothing is wrong, and **stops looking** - the warning does not merely fail
to help, it ends the search.

**The invariant is not that labels are unique.** It is that Truestill never names a drive
ambiguously, which is a property of the moment of naming - where the set being named is known -
and cannot be established at registration, where it is not. Nothing here renames anything: a label
lives in the marker on the user's own disk.

`drives.label` is `TEXT NOT NULL` with no UNIQUE constraint, and three of four registration sites
mint `label=path.name`, so collisions are likely rather than merely possible.
"""

from __future__ import annotations

from truestill_core.drive import distinguishing_names, drive_path_hint


class _Settings:
    """A dict standing in for the catalog, which is all `_SettingsReader` asks for.

    Counts its reads, so the "no collision costs no lookup" claim is measured rather than asserted
    of the source.
    """

    def __init__(self, hints: dict[str, str]) -> None:
        self._hints = {drive_path_hint(uuid): path for uuid, path in hints.items()}
        self.reads = 0

    def get_setting(self, key: str) -> str | None:
        self.reads += 1
        return self._hints.get(key)


# ------------------------------------------------------------------ the collision itself


def test_two_drives_sharing_a_label_are_told_apart_by_where_they_are() -> None:
    """The maintainer's shape. Both are called Morrowkeep; only the path separates them."""
    settings = _Settings({"A": "/mnt/photos", "B": "/media/cloud/Morrowkeep"})

    names = distinguishing_names(settings, [("A", "Morrowkeep"), ("B", "Morrowkeep")])

    assert names == (
        "Morrowkeep at /mnt/photos",
        "Morrowkeep at /media/cloud/Morrowkeep",
    )


def test_a_drive_that_cannot_be_placed_says_so_rather_than_naming_nothing() -> None:
    """`The Memory Cabinet` has no hint in the real catalog, so this is a live case.

    Stated plainly, not apologetically: "I do not know where this is" is actionable - plug it in
    and let it be seen - where silence is not.
    """
    settings = _Settings({"A": "/mnt/photos"})

    names = distinguishing_names(settings, [("A", "Morrowkeep"), ("B", "Morrowkeep")])

    assert names == ("Morrowkeep at /mnt/photos", "Morrowkeep (location not known)")


def test_two_unplaceable_drives_sharing_a_label_stay_two_entries() -> None:
    """`(acs)`'s invariant, at the point where collapsing them is most tempting: hiding may reduce
    detail, never the COUNT nor a drive's identity as a distinct thing.

    They read alike, and that is the honest output - Truestill genuinely cannot tell them apart by
    place. Ordinals were rejected for the opposite reason: `#1` and `#2` would invent an identity
    the user cannot act on.
    """
    names = distinguishing_names(_Settings({}), [("A", "Morrowkeep"), ("B", "Morrowkeep")])

    assert len(names) == 2, "two drives collapsed into one entry"
    assert names == ("Morrowkeep (location not known)", "Morrowkeep (location not known)")


def test_only_the_colliding_label_is_qualified() -> None:
    """A collision does not make the whole list noisy. `Cabinet` is unique here and must come back
    untouched even though it sits beside two drives that are not."""
    settings = _Settings({"A": "/mnt/photos", "C": "/mnt/cabinet"})

    names = distinguishing_names(
        settings, [("A", "Morrowkeep"), ("B", "Morrowkeep"), ("C", "Cabinet")]
    )

    assert names[2] == "Cabinet"


def test_the_callers_order_is_preserved() -> None:
    """The caller decides the order - `library_status` hands these to a sentence. A function that
    silently sorted would reorder a warning the user is reading."""
    settings = _Settings({"A": "/mnt/a", "B": "/mnt/b"})

    names = distinguishing_names(settings, [("B", "Backup"), ("A", "Backup")])

    assert names == ("Backup at /mnt/b", "Backup at /mnt/a")


# ------------------------------------------------------------------ the guard half


def test_distinct_labels_come_back_exactly_as_they_were() -> None:
    """**A GUARD, not a red: this passes before and after by design.**

    That is the point of it. The cry-wolf half of `(acr)` is that a user whose drives are named
    distinctly, or who has one drive, must see nothing new. A unique label returns untouched as
    the function's FIRST branch, so the common case is unchanged structurally rather than by care
    - and a test that went red here would mean the change had leaked into it.
    """
    labels = ["The Memory Cabinet", "Morrowkeep", "Backup"]
    settings = _Settings({"A": "/mnt/a", "B": "/mnt/b", "C": "/mnt/c"})

    names = distinguishing_names(settings, list(zip("ABC", labels, strict=True)))

    assert list(names) == labels


def test_one_drive_is_never_qualified() -> None:
    """A GUARD, for the same reason. A single drive cannot collide with anything, and a lone
    warning naming a path the user never asked to see would be a privacy regression `(acs)` is
    still deciding."""
    assert distinguishing_names(_Settings({"A": "/mnt/a"}), [("A", "Morrowkeep")]) == (
        "Morrowkeep",
    )


def test_no_collision_reads_no_setting_at_all() -> None:
    """The common case does not touch the catalog, measured rather than claimed of the source.

    It matters beyond cost: a function that read a path hint for every drive would be handling the
    sensitive value on the surface `(acs)` is about, in the case where it is never used.
    """
    settings = _Settings({"A": "/mnt/a", "B": "/mnt/b"})

    distinguishing_names(settings, [("A", "Morrowkeep"), ("B", "Cabinet")])

    assert settings.reads == 0


def test_nothing_is_returned_for_no_drives() -> None:
    """An honest zero, and the branch a `Counter` over an empty list would otherwise decide."""
    assert distinguishing_names(_Settings({}), []) == ()
