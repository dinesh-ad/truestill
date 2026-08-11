# Folder-name suggestions on the Trips & events screen

**Built 2026-08-08** across `0071088`, `e702792`, `31de6f8`, on a defect fixed first in
`fe5a9ae`, `3ffb8d5`, `e91b4be`, `d7c6bfc`. A record of what was measured and why the rules are
the rules - not a design document, and not rewritten to match later work.

## The question

Naming a trip or event turns `2015-10-25 - Everyday` into `2015-10-25 - Sam Wedding`. The
screen offered a blank box while the maintainer's own hand-sorted folder names - `Rock Climbing`,
`Wayanad '14`, `Riverside Mall 2015` - sat unused in `files.source_path`. Can the folder propose the
name?

## The rule, and the variant that was measured and rejected

**Deepest ancestor level, 0 to 3, whose majority is >= 70%, is not junk, and is not a root.**
First qualifying level wins.

**"Strongest majority anywhere" was tried and it fails structurally.** A name's share rises
**monotonically with depth** - an ancestor set is a superset of its descendants - so the strongest
majority is always at or near the root. Measured, it proposed `Archive` over
`Northport~Southbury~Sam's Wedding` (100% vs 93%) and `Vault` / `TruestillLibrary` over
everything. The scoring function cannot discriminate; only the junk list can, and that list would
have to enumerate each user's own roots - which is the configuration burden that forced Immich's
folder-album script into `--album-levels`. **Do not reintroduce it.**

**70% is UNTUNED.** Twenty-one clusters cannot distinguish 70 from 75, and the 618-file Wayanad
cluster sits at **70.4%** - it drops out entirely at 75. A stated starting point, not a fitted
parameter, and it must not be tuned against this corpus.

**Depth capped at 3.** Above that is library plumbing, and the cap is what makes the cost linear.
Wayanad needs level 2, leaving one level of headroom.

## What was measured

| | |
|---|---|
| cards receiving a suggestion | **11 of 11**, through `assemble_trip_review` |
| `Wayanad '14` | proposes `Wayanad` - the name the maintainer chose by hand |
| clusters, before the screen's own assembly | 20 of 21, of which 13 judged usable |

The cluster figures and the card figures are not the same measurement. The first ran
`propose_from_catalog` directly; **the screen uses `assemble_trip_review`**, which folds the four
Wayanad days into ONE trip card. That correction removed a problem the design had been built
around - six identical Wayanad suggestions - and it is why 11/11 is the number to quote.

**A trip card carries no member identities.** `TripProposal` holds `start_date`, `end_date` and
day counts, never SHA-256s, so a trip's members are derived by date from the days it claims - the
day-claim rule, not a new one.

## The naming rules, and why each is the rule

Every rule is **suggester-only**. `layout.event_folder` stays path-safety-only: a name the user
TYPES keeps everything it has. This chooses what to propose, never what to overrule.

**No apostrophes.** `U+0027` and `U+0060` are shell metacharacters, and a path carrying one breaks
unquoted scripts. `U+0060` is worse than quoting - it is command substitution. **It is also what
is really in this catalog:** `North~South~Gokul` + U+0060 + `s Marriage`. That was read as a
display mangling in three earlier reports; it is not, it is the character on disk.

**A possessive goes whole** - `Sam's Wedding` proposes `Sam Wedding`, not `Sams`.
`Gokul` is the person's name and `Gokuls` is not a word in any language. The pattern is anchored
on a **lowercase `s` followed by a word boundary**, and that margin is one character wide:
`O'Sullivan` survives as `OSullivan` only because the S is uppercase and, case-insensitively,
because a letter follows the S so `\b` fails. Loosen either half and `O'Sullivan` becomes `O`.
`O'Brien` becomes `OBrien` - no letter lost, no space inserted; it cannot keep the mark.

**Spaces, not hyphens.** The shipped folder format is `2015-10-25 - <name>`, a
space-hyphen-space separator, so a hyphen inside the name makes one character do two jobs in one
string. `TCS-M05-Batch` is the other side of it: those hyphens are part of the name and survive
untouched. Periods survive too - they appear in initials.

**No spelling correction, ever.** Siveram, Gokul and Wayanad are proper nouns
no dictionary holds. A speller would rewrite a real name into a wrong one **while looking
authoritative**, which is worse than silence: the whole value of a suggestion is that it is
visible evidence from the user's own folder, and a corrected word is no longer evidence of
anything. camelCase is not split for the same reason - `McDonald` must not become `Mc Donald`.
Case is left exactly as found; the user's capitalisation is evidence, not noise.

**Order of operations:** tidy punctuation, strip a redundant year, reject junk and roots, reject
what has nothing left. Each step can only take away, so silence is always reachable.

## The junk classifier has never been exercised against a real phone dump

**Its true rate is unknown, and nothing here should be read as coverage.** All 21 folder names in
this corpus are hand-made and clean: the classifier fired **zero** times against them. The messy
fixture in the tests is **constructed** from documented conventions - WhatsApp export folders,
DCIM camera naming, desktop "Copy of" and "New folder (2)" - and is labelled as constructed. It
exercises the rules; it is not evidence of what a real library contains.

What that untested state already cost: `^mar[a-z]*$` classified **`Marys`** as a month, and would
equally have eaten `Maryland`, `Junction`, `Novel`, `Octopus` and `Mayfair`. Nothing exercised it
until a test happened to name someone Mary. **A pattern that never fires is never checked**, so
every widened pattern now carries a cry-wolf partner.

## The motivating case for two future routes

`Northport~Southbury~Sam's Wedding` proposes `Northport Southbury Sam Wedding`. That is three
labels a human joined - **two places and an occasion** - and no structural rule can separate them:
to a counter, `Northport` and `Gokul` are identical. Verbose and truthful beats clever and wrong, and
the cost is one edit in a box the user was going to touch anyway.

Recorded as documentation, **not as TODOs**:

1. **An optional local naming helper.** A language model reading that string knows Northport is a
   city and a marriage is an occasion. This is the case that would earn it its place.
2. **GPS place-name subtraction.** If reverse geocoding puts the photos in Northport and Southbury,
   those tokens are redundant with location the file already carries, and the remainder is
   `Sam Wedding`. Mechanical, offline, no model - it falls out of the GPS work already in the
   backlog.

## "A suggestion appears only on a cluster with no name yet"

True now. It took three commits to become true, and the reason is the record:

1. The claim was written into the plan while **nothing on the screen could tell**.
   `assemble_trip_review` never consults `trip_for_day`, so an already-named trip is re-offered
   on every visit, and `ReviewCardPayload` carried no name for the screen to show it with
   (`3ffb8d5`).
2. Fixing trips left the gate **vacuous for events**, where `existing_name` was hardcoded `None` -
   and a library holds one trip for every several events, so that was the larger half
   (`d7c6bfc`).
3. Only then was the gate real on both kinds, and only then could the sentence be written down.

Twice the promise would have been documented while false. That is the same defect class the
whole arc began with: **a statement made at the moment of decision that is not so.**

## Still open

`commit_trips` and `commit_catalog` both discard a name for something already recorded. Nothing on
the screen can now reach either path, but the code is unchanged - `(abw)`, with the open question
being what a rename **costs** on a library already placed on disk.
