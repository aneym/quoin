# Plan 007: Executable agent contract pack

> **Executor instructions**: Follow step by step; verify each step. STOP conditions
> are binding. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- scaffold/ quoin/blocks.py`

## Status

- **Priority**: P2 · **Effort**: S · **Risk**: LOW
- **Depends on**: none (coordinates with 006's sidecar contract)
- **Category**: dx (this is the product wedge: agent skills + CLI enforcing each other)
- **Planned at**: commit `0203c4b`, 2026-08-29

## Why this matters

The scaffold's AGENTS.md is nine lines: it names the loop but not the JSON shapes, so
a fresh agent must guess the block and sidecar formats the release gates enforce.
The work order (`blocks.py:39-47`) lists only `required: [block_id, kind, title,
html]` and prose-y gates. The pitch "any agent is productive with zero orchestration"
is only true if the CLI emits the full contract.

## Current state

- `scaffold/AGENTS.md` — 9-line loop, no schemas, no examples, no release-mode
  mention.
- `scaffold/briefs/{introduction,interlude,title_deck}.md` — one-paragraph contracts.
- `quoin/blocks.py:43-44` (verified): schema is a minimal required-list; gates are
  four prose strings; no sidecar schema, no output example.
- `quoin/schemas/block.schema.json` — the real shape, unused by the work order.

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Work order | in a book dir: `python3 -m quoin blocks --missing --json` | includes block schema, sidecar schema, example, check commands |
| Evals | `python3 evals/run_evals.py --iteration 2` | `all_pass: true` |

## Scope

**In scope**: `scaffold/AGENTS.md`, `scaffold/briefs/*.md`, `quoin/blocks.py` (work
order content only), `quoin/schemas/block.schema.json` (add sidecar schema file
`stylepass.schema.json` and package it).
**Out of scope**: gate behavior in check.py; the editorial rules themselves (do not
soften them).

## Steps

1. Work orders embed: the block JSON schema (loaded from the packaged schema file,
   single source of truth), the stylepass sidecar schema, a compact VALID example of
   each (synthetic), the exact output paths, and the two commands that close the
   loop: `quoin check` (draft) and `quoin check --release` (final).
   **Verify**: `blocks --missing --json | python3 -m json.tool` shows all five.
2. Rewrite `scaffold/AGENTS.md` (~60 lines): the loop with the two-pass rule stated
   as two separate agent invocations; how to read evidence files and quote support
   lines; the full editorial contract (plain concrete prose, no em dashes, surname on
   unstated pronouns, never summarize the piece, read-aloud judgment before calling a
   block clean, source prose untouchable); failure recovery (what a check FAIL row
   means, fix and re-run); one worked block example end to end.
   **Verify**: `quoin init /tmp/qi7 && wc -l /tmp/qi7/AGENTS.md` → ≥50 lines; content
   includes both schemas by name.
3. Expand each brief with: a 5-line worked example, the word-count band, and the two
   or three most common rejection reasons from the aneym canon (introduction: piece
   summary, prestige listing, guessed pronouns; interlude: answering the question;
   title_deck: length).
   **Verify**: evals still green (init fixture unaffected functionally).

## Done criteria

- [ ] Work-order JSON carries schemas + examples + commands (verified above)
- [ ] Fresh `quoin init` book contains the rewritten pack
- [ ] Prose rule holds in everything written: no em dashes, no puffery
- [ ] `plans/README.md` updated

## STOP conditions

- The sidecar shape 006 tests disagrees with what you are about to document: sync
  with 006's executor (or its landed code) first; never document a guess.

## Maintenance notes

The contract text and the schemas must never fork: work orders read schema files at
runtime, and AGENTS.md references them by path rather than duplicating field lists
where possible.
