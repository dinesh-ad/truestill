"""`CLAUDE.md`'s hook sentence is checked against `.pre-commit-config.yaml`. `(ago)`'s shape.

⚠ **THE SENTENCE DRIFTED TWICE, AND BOTH TIMES IN THE PARAGRAPH WHOSE SUBJECT IS THAT FAILURE.**
It is the entry point's warning that *"the hooks print a column of green immediately above the
commit, `make check` does not, and the eye takes the nearer one"*.

* **2026-08-24** - the list omitted `push-gate`, the **only hook in that column with the power to
  refuse a push**. A sentence about not trusting a column of green left out its one entry that can
  stop you.
* **2026-08-26** - the correcting commit (`96af43a`) added `push-gate` to the list and left the
  word **EIGHT** in front of a list of nine. The number and the list it introduced disagreed for
  two days.

⚠ **`CLAUDE.md:207` SAID *"NOTHING PINS THIS SENTENCE"* AND IT WAS RIGHT.** `(ago)` ruled that a
census guard is a new artifact and has to earn itself; the ruling was applied and the answer was
*record it, do not guard it*. **Two drifts in the same paragraph is the evidence that ruling asked
for**, so this file exists now and did not before.

§4's seventy-second member: **loop the DERIVED inventory, assert into the DECLARATION.** The
config is the inventory; the prose is the declaration. A guard listing the hook names itself would
be a third copy, and a third copy is what this is for.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / ".pre-commit-config.yaml"
CLAUDE_MD = ROOT / "CLAUDE.md"

#: The bullet, found by its opening rather than by line number - it has moved twice already.
_SENTENCE = re.compile(r"- \*\*The pre-commit hooks are ([A-Z]+):(.*?)\*\*", re.DOTALL)

_NUMBER_WORDS = {
    3: "THREE",
    4: "FOUR",
    5: "FIVE",
    6: "SIX",
    7: "SEVEN",
    8: "EIGHT",
    9: "NINE",
    10: "TEN",
    11: "ELEVEN",
    12: "TWELVE",
}


def _declared() -> tuple[str, str]:
    match = _SENTENCE.search(CLAUDE_MD.read_text(encoding="utf-8"))
    assert match is not None, (
        "CLAUDE.md no longer contains a '- **The pre-commit hooks are <WORD>: ...**' bullet. "
        "If the sentence was reworded, reword this guard with it; if it was deleted, delete this "
        "file - a guard nobody retires is how a dead check outlives its subject."
    )
    return match.group(1), match.group(2)


def _hook_ids() -> list[str]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    return [hook["id"] for repo in config["repos"] for hook in repo["hooks"]]


def test_the_config_is_actually_read() -> None:
    """Non-emptiness first: a parse that silently found nothing would pass every test below."""
    ids = _hook_ids()
    assert len(ids) >= 3, f"only {len(ids)} hook ids parsed out of {CONFIG}; the shape changed"
    assert "push-gate" in ids, "the one hook that can refuse a push is not in the parsed set"


def test_the_stated_number_is_the_number_of_hooks() -> None:
    """NINE hooks, and the word says nine. This is the assertion that was false for two days."""
    ids = _hook_ids()
    word, _ = _declared()
    expected = _NUMBER_WORDS.get(len(ids))
    assert expected is not None, f"{len(ids)} hooks and no word for it; extend _NUMBER_WORDS"
    assert word == expected, (
        f"CLAUDE.md says the hooks are {word}; .pre-commit-config.yaml declares {len(ids)} "
        f"({expected}): {', '.join(ids)}. The number and the list must move together - they did "
        f"not on 2026-08-24 or on 2026-08-26."
    )


def test_every_hook_is_named_in_the_sentence() -> None:
    """A count can be right while the list is short, which is the 2026-08-24 failure exactly.

    The number alone would have passed that day: the sentence said EIGHT and named eight, and the
    ninth hook - the only one that can refuse a push - was simply absent.
    """
    _, body = _declared()
    # A whole token, with or without backticks: the sentence writes the first three bare and the
    # rest in code spans. `-` counts as part of the word, or `ruff` would match inside
    # `ruff-format` and a missing `ruff` would go unnoticed.
    missing = [
        hook_id
        for hook_id in _hook_ids()
        if not re.search(rf"(?<![\w-]){re.escape(hook_id)}(?![\w-])", body)
    ]
    assert not missing, (
        f"these hooks run and CLAUDE.md's sentence does not name them: {', '.join(missing)}. "
        f"A hook absent from the list is one nobody knows fires - and `push-gate` was absent "
        f"from it for two days while being the only one that can stop a push."
    )
