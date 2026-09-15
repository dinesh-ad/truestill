# (akq) A LICENSED RUN CHARGED THE FREE COUNTER, AND SELF-CHECK SAID NOTHING ABOUT THE LICENCE.

*Body of backlog entry `(akq)`, closed in [`SHIPPED.md`](../../SHIPPED.md); the letter namespace is shared with [`BACKLOG.md`](../../BACKLOG.md).*

## THE DEFECT, FOUND BY BUYING A LICENCE AND WATCHING THE NUMBER MOVE

`allowance.record_files_written` was unconditional. It read the counter, added the run's file
count, wrote it back, and never asked whether this install held an entitlement. So the first
licensed run over the maintainer's own 2,574-file library took the counter from **844 to 3,418**.

Nothing looked wrong at the time, and that is the shape of it: an entitled install never *reads*
the counter, so the damage is invisible until the moment the token is lost or signed out. Then
`remaining_for` falls back to the free tier and answers **"0 of 1,000 left"** - a paying customer
left **worse off than someone who had just downloaded truestill**, at exactly the moment they are
already in trouble.

⚠ **THE COUNTER IS NOT A METER. IT IS A CAP.** A meter charges whoever used the thing; a cap
exists to be exceeded by people who have not paid. Charging a licence holder against a limit that
does not apply to them is not conservative bookkeeping - it is accruing a debt that can only ever
be collected from someone who has already paid it off.

## WHAT D16 §1 ACTUALLY SAID

> *"cumulative across every run"*

That clause is the **free tier's arithmetic**, and its own sentence says why: *"A per-run cap is
not a cap: a user runs it n times and the free tier is the entire product."* It was written to
close a bypass, not to bill an entitlement. Reading it as "every run, licensed or not" is reading
a rule about the cap as a rule about the counter.

Recorded as `DECISIONS.md` **D16 §8**, and deliberately as a **clarification of §1 rather than a
change to it** - §1 is not wrong and is not edited.

## THE TEST IS `remaining_for`, NEVER A LIST OF STATES

The guard is one line:

```python
if remaining_for(current.state, 0) is None:
    return files_written()
```

`remaining_for` already owns the question *"does this state have a cap at all?"* and already
carries its asymmetry: **ACTIVE and LAPSED are entitlements; UNREADABLE is not.** Writing
`if state is not ABSENT` instead would have handed anyone a free bypass for the price of writing
garbage into `licence.token`, and it is the mutation that proves the guard bites.

⚠ **LAPSED does not charge**, and D16 §2 is why: *"a lapsed licence loses nothing it bought."*
Charging it would give someone who paid a **smaller** free tier than someone who never did.

## NOT A RESET

Installing a licence does **not** zero the counter. What an install wrote while it was on the
free tier is a fact about that install, and it survives a purchase; what changes is that nothing
is added to it. The 3,418 already accrued is corrected back to **161** - the value before this
work began - by `DECISIONS.md` §3's documented means, which is the same means any customer has.
Correcting a number this defect wrote is not a special entitlement.

## THE SECOND HALF: SELF-CHECK WAS SILENT

`truestill self-check` printed install path, core version, **entitlement epoch**, exiftool, trash,
catalog, cache and session url. Its output was **byte-identical licensed and unlicensed**, while
printing *"entitlement epoch 1"* - a property of the **build**, not of the install. Support's
first question is *"what does self-check say"*, and the answer said everything except the thing
being asked about.

`licence_finding()` reports **what it holds**, which is the module's founding rule unchanged: the
comparison against the source of truth belongs to the caller. It says which file is present, which
`kid` signed it, what it claims to cover, and what that verifies as **on this build**.

**Included**: `state`, `path`, `kid`, `licence` (the id), `edition`, `covers_through`,
`updates_until`.
**Excluded**: `name`, `email`, `account`.

⚠ **NOTHING PERSONAL, BECAUSE THIS REPORT EXISTS TO BE PASTED.** The payload carries the buyer's
name, their email and an account id. A diagnostic a person is invited to paste into a public issue
must carry none of them, and the account id is the worst of the three - it links one person's
separate purchases to each other. The **licence id** is included and earns its place: opaque on
its own, and the exact key `scripts/licences.py find` resolves, so support needs no second round
trip.

`UNREADABLE` is the only `DEGRADED` state here. Absent, signed-out and lapsed are facts about an
install rather than faults in one - `entitlement_epoch_finding`'s reasoning - and a free user is
not a broken user. A token that is present and will not verify is a real fault, and carries
`reason` so the user knows what to replace.

## THE THIRD HALF: THERE WAS NO CLI LICENCE SURFACE AT ALL

A terminal-only customer received a token file and had to discover, unaided, that it belongs at
`app_paths.licence_path()`. `scripts/licences.py` is the **maintainer's** tool, lives outside the
product, and `whois` is not theirs to run.

**The smallest honest surface is two things: see the state, and use a file.** `truestill account`,
and `truestill account --use-file PATH`.

⚠ **NO SECOND VOCABULARY.** The name is not chosen; it is read off the rail that already exists -
`aria-label="Account and licence"`, `/api/account`, `service/account.py`, and the button that says
**"Use this licence file"**. `licence`, `activate` and `register` would each have been a word the
product says nowhere else. Every sentence the command prints comes from
`licence_notice.account_summary`, which is what the rail renders, so the two surfaces cannot word
one outcome differently.

⚠ **SIGN-OUT IS DELIBERATELY ABSENT.** It deletes the licence file, and the app spends a whole
paragraph warning before it does - *"Keep a copy - you need it to sign back in."* A one-line
destructive verb with no ceremony is worse than no verb. `reclaim`'s ceremony rule, and the path
is printed in every state, so removing the file is already obvious to anyone who means it.

## WHAT PROVES IT

Nine mutations, nine caught:

| mutation | caught by |
|---|---|
| `if False:` - the entitlement guard never fires | 4 of 8 in `test_a_licensed_run_does_not_charge_the_free_counter.py` |
| `if state is not ABSENT:` - a state list instead of `remaining_for` | `test_an_unreadable_token_still_charges` |
| `if state in (ACTIVE, LAPSED, SIGNED_OUT):` - sign-out keeps the entitlement | `test_a_signed_out_install_charges_again` |
| `licence_finding()` removed from `core_findings()` | core, app and the new suite, 3 files |
| `"email": payload.email` added to the evidence | `test_the_finding_never_carries_the_buyers_identity` |
| `Status.DEGRADED` for a lapsed licence | `test_a_lapsed_licence_still_reports_what_it_bought_and_is_not_a_fault` |
| the signed-out detail hard-codes `absent` | `test_a_signed_out_install_says_so_rather_than_reading_as_a_fresh_one` |
| `--use-file` reads instead of installing | 3 of 6 in `test_the_account_command.py` |
| a `--sign-out` flag appears on the parser | `test_the_command_offers_no_sign_out` |

⚠ **The lapsed fixture had to be corrected before it asserted anything.** Backdating
`updates_until` produced `ACTIVE`, because **the entitlement is a version ceiling, not a date** -
`licence.py`'s own opening sentence. Lowering `covers_through` is what produces `LAPSED`, and the
test now says so in its body so the next person does not repeat it.

⚠ **The privacy test's first version asserted the substring `"name"` was absent and failed against
correct code**, because `Finding.as_json()` always carries a `name` **key** - the finding's own
name. Searching for a field name proves nothing. It now mints a real Ed25519 token against an
injected throwaway `kid` and searches for the **values**.
