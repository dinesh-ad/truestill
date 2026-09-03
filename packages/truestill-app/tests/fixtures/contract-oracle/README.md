# The contract oracle - frozen, never regenerated

`openapi.json` here is the committed spec as of 2026-09-03 (`7b476d9`), and `api.d.ts` is what
`openapi-typescript` 7.13.0 rendered from it under TypeScript 5.9.3 - **3,793 lines, run once in a
scratch directory**, because the TypeScript 7 package in the tree ships no compiler API and the tool
cannot run there. `scripts/emit_api_types.py` is accepted against this pair, byte for byte below the
header, by `test_the_generated_types_are_current.py`. A record: when the spec grows a construct this
pair never saw, the emitter refuses it by name rather than guessing, and the fixture is not edited.
