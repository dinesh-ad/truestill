"""The four states the browser had never drawn. `DECISIONS.md` D5, D16 §5; `(aam)`.

⚠ **THE GAP THIS CLOSES, stated as the defect it was.** The suite runs with no licence file, so
every browser assertion in this project had only ever exercised **ABSENT**. Core pinned the five
states' *wording*; nothing pinned their *rendering*. A `renderAccount` that threw on a payload
carrying a name - an undefined field, a bad template branch, a null dereference - would have
passed `make check`, passed the whole browser lane, and shipped a rail that went blank the moment
somebody paid.

**THE KEY IS GENERATED AT TEST TIME AND NEVER TOUCHES THE TREE.** `PUBLIC_KEYS` ships one real
entry whose private half lives outside every git work tree, so this suite cannot mint against it
and must not try. Instead each test generates its own Ed25519 pair, injects the **public** half
into `licence.PUBLIC_KEYS` through `monkeypatch`, and mints with the private half it holds in
memory for the length of one test. Three properties follow, and all three are the point:

* no private key is committed, or written to disk, or shared between tests;
* the injection is `monkeypatch.setitem`, so the shipped table is restored even on failure;
* nothing in the product changes - there is deliberately no environment variable that adds a
  trust root, because that would be a forgery hole wearing a test helper's clothes.

**This works because the app runs IN-PROCESS.** `e2e_support.boot_app` starts uvicorn on a thread
in this interpreter, so the server reads the same `licence.PUBLIC_KEYS` dict this file mutates,
and the same `TRUESTILL_DATA_DIR` the root `conftest.py` isolates per test. A subprocess server
would need a different mechanism and would be worth saying so about; this one does not.
"""

from __future__ import annotations

from collections.abc import Callable

import nacl.signing
import pytest
from e2e_support import open_app
from playwright.sync_api import Page, expect
from truestill_core import allowance, app_paths, licence
from truestill_core.licence import Licence, LicenceState
from truestill_core.licence_notice import account_summary

#: Deliberately not "k1". A fixture that reused the shipped key id would still pass if the
#: injection silently did nothing, because the real `k1` is in the table already.
KID = "e2e-throwaway"
NAME = "Ada Lovelace"
EMAIL = "ada@example.com"


@pytest.fixture
def mint(monkeypatch: pytest.MonkeyPatch) -> Callable[..., str]:
    """A throwaway keypair, trusted for one test, and a way to mint against it.

    `setitem` rather than assigning a whole dict: it restores exactly the one entry it added, so
    a failure mid-test cannot leave a trusted stranger in the table for whatever runs next.
    """
    signer = nacl.signing.SigningKey.generate()
    monkeypatch.setitem(licence.PUBLIC_KEYS, KID, licence.b64url_encode(bytes(signer.verify_key)))

    def _mint(**overrides: object) -> str:
        fields: dict[str, object] = {
            "v": licence.PAYLOAD_VERSION,
            "kid": KID,
            "sub": "acc-e2e",
            "lic": "lic-e2e",
            "name": NAME,
            "email": EMAIL,
            "edition": "pro",
            "covers_through": licence.BUILD_EPOCH,
            "issued_at": "2026-09-11",
            "updates_until": "2027-09-11",
        }
        fields.update(overrides)
        encoded = licence.encode_payload(fields)
        signature = signer.sign(licence.signing_input(encoded)).signature
        return f"{encoded}.{licence.b64url_encode(signature)}"

    return _mint


def _reload(ui: Page) -> Page:
    """Re-open the app so the shell fetches `/api/account` again.

    The rail loads once at boot, which is correct for a state that only changes when the user
    changes it - so a test that installs a licence after the page is up must reload to see it.
    The URL carries the session token, so this keeps its authentication.
    """
    return open_app(ui, ui.url)


def _slot_state(ui: Page, expected: str) -> None:
    expect(ui.locator("#account-slot")).to_have_attribute("data-state", expected)


# --- the four states, each drawn in a real browser ---------------------------------------------


def test_an_active_licence_shows_the_buyers_name_and_no_allowance(
    ui: Page, mint: Callable[..., str]
) -> None:
    """ACTIVE. `(aam)`: *"identity visible in the interface, not buried in a settings page."*

    ⚠ **The allowance must be ABSENT, and that is the assertion with teeth.** An entitlement has
    no cap, so a number here would be either wrong or invented - and `.account-allowance` is not
    rendered at all rather than rendered empty, so an element that still took its margin would
    fail this too.
    """
    licence.write_licence(mint())
    _reload(ui)

    _slot_state(ui, "active")
    expect(ui.locator("#account-slot .account-name")).to_have_text(NAME)
    expect(ui.locator("#account-slot .account-allowance")).to_have_count(0)


def test_an_active_licence_names_what_was_bought_in_cores_own_words(
    ui: Page, mint: Callable[..., str]
) -> None:
    """The detail sentence, compared against core's string rather than a retyped fragment of it.

    This file's sibling in `test_rail_shell.py` shipped `to_contain_text("free files")` and went
    red the moment the wording was shortened - a retyped fragment is the exact seam this feature
    exists to close, and it is easier to reproduce than to avoid.
    """
    token = mint()
    licence.write_licence(token)
    owned = account_summary(licence.verify_token(token), None, allowance.FREE_FILE_ALLOWANCE)
    _reload(ui)
    ui.click("#account-slot summary")

    expect(ui.locator("#account-slot .account-body")).to_contain_text(owned.detail)
    expect(ui.locator("#account-slot .account-body")).to_contain_text(EMAIL)


def test_a_lapsed_licence_still_shows_the_name_and_says_nothing_was_lost(
    ui: Page, mint: Callable[..., str]
) -> None:
    """LAPSED. D16 §2: *"a lapsed licence loses nothing it bought."*

    Two things are asserted because a renderer could get either one wrong on its own: the buyer
    is still greeted by name, and the allowance is still absent - a lapsed licence is an
    entitlement, so showing a free-tier count would tell a paying customer they had been
    demoted.
    """
    licence.write_licence(mint(covers_through=licence.BUILD_EPOCH - 1))
    _reload(ui)

    _slot_state(ui, "lapsed")
    expect(ui.locator("#account-slot .account-name")).to_have_text(NAME)
    expect(ui.locator("#account-slot .account-allowance")).to_have_count(0)
    ui.click("#account-slot summary")
    expect(ui.locator("#account-slot .account-body")).to_contain_text("yours for ever")


def test_signing_out_from_the_rail_changes_the_slot_without_a_reload(
    ui: Page, mint: Callable[..., str]
) -> None:
    """SIGNED_OUT, reached the way a user reaches it - by pressing the button.

    ⚠ **No reload**, which is what makes this an assertion about the product rather than about
    the fixture: `/api/account/sign-out` answers with the account as it now stands, so the rail
    must repaint from that response. A version that signed out correctly and left the rail
    describing a signed-in user would pass every other test in this file.
    """
    licence.write_licence(mint())
    _reload(ui)
    ui.click("#account-slot summary")

    ui.click("[data-testid='account-signout']")

    _slot_state(ui, "signed_out")
    expect(ui.locator("#account-slot .account-name")).to_have_text("Signed out")
    # Capped again, because a signed-out installation has no entitlement to read.
    expect(ui.locator("#account-slot .account-allowance")).to_have_count(1)
    assert not app_paths.licence_path().exists()


def test_an_unreadable_licence_is_drawn_with_its_notice_and_never_as_an_error(ui: Page) -> None:
    """UNREADABLE. The state that must never become a locked door.

    ⚠ **No `mint` fixture, deliberately**: this is the one state that needs no trusted key,
    because the bytes on disk are not a token under anybody's key. Taking the fixture anyway
    would suggest the injection mattered here and hide that it does not.

    The global error banner is asserted **hidden**: a damaged licence file is not a failure with
    no home, and painting it across whatever screen is open is what D16 §5 rules out by name.
    """
    app_paths.licence_path().parent.mkdir(parents=True, exist_ok=True)
    app_paths.licence_path().write_bytes(b"\xff\xd8\xff\xe0 not a token at all")
    _reload(ui)

    _slot_state(ui, "unreadable")
    expect(ui.locator("#account-slot .account-name")).to_have_text("Licence problem")
    expect(ui.locator("#account-slot .account-allowance")).to_have_count(1)
    expect(ui.locator("#global-error")).to_be_hidden()

    ui.click("#account-slot summary")
    expect(ui.locator("#account-slot .account-notice")).to_be_visible()
    expect(ui.locator("#account-slot .account-body")).to_contain_text(
        "nothing about your library has changed"
    )


# --- what each state offers ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "signs_out"),
    [("active", True), ("lapsed", True), ("unreadable", True), ("absent", False)],
)
def test_sign_out_is_offered_exactly_where_there_is_something_to_sign_out_of(
    ui: Page, mint: Callable[..., str], state: str, signs_out: bool
) -> None:
    """**The census, and the half that keeps `(aam)`'s ruling from being decorative.**

    Asserting sign-out is present in three states proves the control exists; asserting it is
    **absent** in ABSENT proves the condition is real rather than the button being unconditional.
    Without the second row, a renderer that always drew it would pass - and would offer to sign a
    brand-new user out of nothing.

    UNREADABLE offers it deliberately: the file may be a licence that will not verify, and
    removing it is one of the two things a user can do about that.
    """
    if state == "active":
        licence.write_licence(mint())
    elif state == "lapsed":
        licence.write_licence(mint(covers_through=licence.BUILD_EPOCH - 1))
    elif state == "unreadable":
        app_paths.licence_path().parent.mkdir(parents=True, exist_ok=True)
        app_paths.licence_path().write_bytes(b"rubbish")
    _reload(ui)

    _slot_state(ui, state)
    expect(ui.locator("[data-testid='account-signout']")).to_have_count(1 if signs_out else 0)


def test_activation_from_a_file_reaches_active_in_a_real_browser(
    ui: Page, mint: Callable[..., str], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """**The whole path a first customer walks**, end to end through the browser.

    Everything before this asserted a state the fixture had already written. This one starts at
    ABSENT, types a path the way a person would, presses the button, and requires the rail to
    arrive at ACTIVE with the buyer's name on it - without a reload, because the activation
    response carries the new account.
    """
    handed_over = tmp_path_factory.mktemp("licence") / "truestill-licence.token"
    handed_over.write_text(mint())

    _slot_state(ui, "absent")
    ui.click("#account-slot summary")
    ui.fill("#account-file", str(handed_over))
    ui.click("#account-activate")

    _slot_state(ui, "active")
    expect(ui.locator("#account-slot .account-name")).to_have_text(NAME)
    expect(ui.locator("#account-error")).to_be_hidden()


def test_the_injected_key_is_the_only_reason_these_pass(ui: Page, mint: Callable[..., str]) -> None:
    """**Anti-vacuity for the whole file, and it is not ceremony.**

    Every test above installs a token and asserts a state. If the injection silently did nothing,
    `verify_token` would answer UNREADABLE - and the UNREADABLE test would still pass, the
    sign-out census row for `unreadable` would still pass, and a reader would have no way to tell
    that ACTIVE and LAPSED were never reached. This asserts the dependency directly: the same
    token, minted the same way, is not trusted once its key is gone.
    """
    token = mint()
    licence.write_licence(token)
    assert licence.verify_token(token).state is LicenceState.ACTIVE

    del licence.PUBLIC_KEYS[KID]
    try:
        assert licence.verify_token(token).state is LicenceState.UNREADABLE
    finally:
        # Restored by hand because this test removed it outside monkeypatch's knowledge; the
        # fixture's own teardown would otherwise raise on a key that is no longer there.
        licence.PUBLIC_KEYS[KID] = licence.b64url_encode(
            bytes(nacl.signing.SigningKey.generate().verify_key)
        )

    _reload(ui)
    _slot_state(ui, "unreadable")
    assert account_summary(Licence(LicenceState.UNREADABLE), None, 1).headline


# --- the small window ----------------------------------------------------------------------------


def test_a_narrow_window_can_still_activate_a_licence(
    ui: Page, mint: Callable[..., str], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """**The gap this closes was a paying customer locked out by a window size.**

    The slot was `display: none` below 720px for one commit, which took the only activation path
    with it: a user on a small window could not activate a licence they had paid for. "The window
    is narrow" is not a reason to withhold the one control that turns a paying customer into a
    working app.

    It is now out of flow instead of absent, so the bar's 120px budget is untouched - and the
    test that owns that budget, `test_narrow_top_bar.py`, still passes. This asserts the other
    half: that the control actually works down here, all the way to ACTIVE.
    """
    handed_over = tmp_path_factory.mktemp("licence") / "licence.token"
    handed_over.write_text(mint())
    ui.set_viewport_size({"width": 480, "height": 800})

    expect(ui.locator("#account-slot")).to_be_visible()
    ui.click("#account-slot summary")
    ui.fill("#account-file", str(handed_over))
    ui.click("#account-activate")

    _slot_state(ui, "active")


def test_the_narrow_panel_does_not_push_the_bar_open(ui: Page, mint: Callable[..., str]) -> None:
    """The mechanism, asserted rather than trusted: an out-of-flow child adds nothing to its
    parent's height.

    ⚠ **Measured with the panel OPEN**, which is the only state where it could push - a closed
    `<details>` would satisfy a naive version of this test while an open one broke the bar. The
    ceiling itself lives in `test_narrow_top_bar.py` and is not restated here; what is asserted
    is that opening the account changes the bar's height by nothing at all.
    """
    licence.write_licence(mint())
    _reload(ui)
    ui.set_viewport_size({"width": 480, "height": 800})

    closed = ui.eval_on_selector("#sidebar", "el => el.getBoundingClientRect().height")
    ui.click("#account-slot summary")
    expect(ui.locator("#account-slot .account-body")).to_be_visible()
    opened = ui.eval_on_selector("#sidebar", "el => el.getBoundingClientRect().height")

    assert opened == closed, f"opening the account grew the top bar from {closed} to {opened}"


@pytest.mark.parametrize("state", ["absent", "active", "lapsed", "signed_out", "unreadable"])
def test_no_state_truncates_its_own_headline(
    ui: Page, mint: Callable[..., str], state: str
) -> None:
    """**The real budget guard, and it exists because a character count lied twice.**

    Core carries a length proxy; this is the property. The summary row's name box measures 127px,
    and a count cannot decide what fits it - letters are not the same width, so
    "1,000 of 1,000 left" fits at 19 characters and "Licence unreadable" truncates at 18. Both
    shipped inside a passing length budget and both rendered with an ellipsis on screen.

    ⚠ **Only the strings TRUESTILL owns are asserted.** A buyer's name is arbitrary - somebody is
    called Featherstonehaugh-Wellington - and clipping a long one with the full identity in the
    details below is the right behaviour, not a defect. The fixture name is short on purpose so
    this measures our wording rather than theirs.
    """
    if state == "active":
        licence.write_licence(mint())
    elif state == "lapsed":
        licence.write_licence(mint(covers_through=licence.BUILD_EPOCH - 1))
    elif state == "signed_out":
        licence.write_licence(mint())
        licence.sign_out()
    elif state == "unreadable":
        app_paths.licence_path().parent.mkdir(parents=True, exist_ok=True)
        app_paths.licence_path().write_bytes(b"not a token")
    _reload(ui)
    _slot_state(ui, state)

    overflow = ui.eval_on_selector_all(
        "#account-slot .account-name, #account-slot .account-allowance",
        "els => els.map(el => ({text: el.textContent, over: el.scrollWidth - el.clientWidth}))",
    )

    assert overflow, "nothing was measured; the summary row rendered neither line"
    clipped = [row for row in overflow if row["over"] > 0]
    assert not clipped, f"{state}: truncated in the rail - {clipped}"


# --- the state dot -------------------------------------------------------------------------------

#: What each state's dot must be, as the browser computes it. `filled` carries the distinction a
#: colour-blind user can still see; the hue separates the two filled states that are both fine.
DOT = {
    "active": ("rgb(92, 196, 127)", True),
    "lapsed": ("rgb(253, 164, 175)", True),
    "unreadable": ("rgb(224, 169, 74)", True),
    "absent": ("rgba(0, 0, 0, 0)", False),
    "signed_out": ("rgba(0, 0, 0, 0)", False),
}


@pytest.mark.parametrize("state", list(DOT))
def test_the_dot_carries_fill_as_well_as_hue_in_every_state(
    ui: Page, mint: Callable[..., str], state: str
) -> None:
    """**The defect was three of five states sharing one colour, not the colour being too dark.**

    Measured before anything changed, every dot was between 8.07:1 and 9.00:1 against the rail -
    two to three times WCAG 2.2 1.4.11's 3:1 floor. An indicator that says the same thing in the
    majority case carries no information, so a person stops reading it and then misses the day it
    turns amber.

    So the assertion is on **both channels**: the fill, which a colour-blind user can still see,
    and the hue, which separates the two filled states that are both fine. A change that
    recoloured the dot but collapsed the fill distinction would still leave three states
    indistinguishable to a large minority of people, and would pass a colour-only test.
    """
    if state == "active":
        licence.write_licence(mint())
    elif state == "lapsed":
        licence.write_licence(mint(covers_through=licence.BUILD_EPOCH - 1))
    elif state == "signed_out":
        licence.write_licence(mint())
        licence.sign_out()
    elif state == "unreadable":
        app_paths.licence_path().parent.mkdir(parents=True, exist_ok=True)
        app_paths.licence_path().write_bytes(b"not a token")
    _reload(ui)
    _slot_state(ui, state)

    seen = ui.eval_on_selector(
        "#account-slot .account-dot",
        """el => {
            const s = getComputedStyle(el);
            const box = el.getBoundingClientRect();
            return {bg: s.backgroundColor, ring: s.boxShadow, w: box.width, h: box.height};
        }""",
    )
    expected_bg, filled = DOT[state]

    assert seen["bg"] == expected_bg, f"{state}: dot is {seen['bg']}"
    assert (seen["ring"] == "none") is filled, f"{state}: fill channel is wrong - {seen['ring']}"
    # The ring is an inset shadow rather than a border precisely so switching states cannot
    # change the row's height. A border would make the hollow states 12px and the filled ones 8.
    assert (seen["w"], seen["h"]) == (8, 8), seen


def test_the_five_states_do_not_all_look_alike() -> None:
    """**Anti-vacuity for the table above, and it is the whole point of the change.**

    The parametrised test asserts each state matches its own row. If every row held the same
    pair, all five would pass while the rail said one thing in five situations - which is exactly
    the defect being fixed, surviving its own guard.

    ⚠ **Four, not three** - three filled hues plus one hollow ring, across five states. The prose
    first said three, conflating "three fills" with "three appearances"; this assertion is what
    caught it, which is the cheapest possible place for that to happen.
    """
    assert len(set(DOT.values())) == 4, DOT
    assert sum(1 for _, filled in DOT.values() if filled) == 3
