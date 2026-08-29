# Agent loop

This book is authored by running `quoin` commands in this directory, not by
guessing formats. Every JSON shape below comes straight from `quoin blocks
--missing --json`: read that output first, every time, instead of trusting
memory of a past book.

1. Run `quoin blocks --missing --json`. Each entry is one work order: which
   block, its brief, its evidence files, the two JSON schemas it must satisfy,
   a compact valid example of each, the two output paths, and the commands
   that close the loop.
2. Draft the block for meaning: read every file listed in `evidence`, then
   write prose that only says what those files support. This is drafting,
   not styling; do not chase the em-dash rule yet.
3. Run the style pass as a separate agent invocation when the harness allows
   it. The style pass exists to catch what the drafting pass cannot see in
   its own prose: filler, hedges, sentences that only sound finished. It
   never adds new claims.
4. Write `blocks/<id>.json` (matching `block.schema.json`) and
   `blocks/<id>.stylepass.json` (matching `stylepass.schema.json`) to the
   `output_path` values from the work order.
5. Run `quoin check` (draft mode). Fix any FAIL row and re-run before moving
   on; a FAIL names the exact gate that failed, not a general complaint.
6. Before a release, run `quoin check --release`. This additionally rejects
   placeholder blocks, missing stylepass sidecars, and any claim with an
   empty `claim` or `support` field.

## Editorial contract

- Plain, concrete prose. No em dashes, ever.
- No summarizing the piece. Say what makes it worth reading, don't recap it.
- Use the surname when a person's pronouns are not stated anywhere in the
  evidence. Never guess a pronoun from a name.
- Every factual claim quotes the evidence line it rests on, in the stylepass
  sidecar's `claims[]`. A claim with no quoted support does not survive
  release check.
- Read the block aloud before calling it clean. If a sentence trips on the
  way out, it is not done.
- Source prose is untouchable: quote it, don't rewrite it, and never invent
  material the sources don't contain.

## Reading evidence and quoting support

`evidence` in a work order is a list of normalized source files
(`sources/normalized/<id>.xhtml`). Open each one, find the sentence a claim
depends on, and copy it verbatim into that claim's `support` field alongside
a locator (file name, or file name plus a short landmark like a heading).
`support` is not a paraphrase; it is the reader's way of checking the claim
without re-deriving it.

## Failure recovery

A FAIL row from `quoin check` names one gate and its detail, for example
`contamination FAIL dock-frag: newsletter`. Fix only what that row names,
re-run `quoin check`, and confirm the row now reads PASS before touching
anything else. Do not pre-emptively rewrite blocks that already pass.

## Worked example

Work order:
```json
{"block_id": "bridge", "kind": "interlude", "evidence": ["sources/normalized/moesta.xhtml"],
 "output_path": {"block": "blocks/bridge.json", "stylepass": "blocks/bridge.stylepass.json"}}
```

`blocks/bridge.json`:
```json
{"block_id": "bridge", "kind": "interlude", "title": "Between systems and choices",
 "html": "<p>The last chapter built a pricing model. This one asks who actually buys it.</p>"}
```

`blocks/bridge.stylepass.json`:
```json
{"block_id": "bridge", "changed": true, "findings": ["cut a throat-clearing opener"],
 "claims": [{"claim": "The prior chapter builds a pricing model.",
             "support": "\"a model for setting price\" (sources/normalized/moesta.xhtml)"}]}
```

Then `quoin check` and, before release, `quoin check --release`.
