# Plan 006: Release-gate and authored-block failure evals

> **Executor instructions**: Follow step by step; verify each step. STOP conditions
> are binding. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- quoin/check.py quoin/blocks.py evals/`
> Re-read live code; excerpt references below are from `0203c4b`.

## Status

- **Priority**: P2 · **Effort**: M · **Risk**: LOW
- **Depends on**: 002
- **Category**: tests
- **Planned at**: commit `0203c4b`, 2026-08-29

## Why this matters

`quoin check --release` is the path that decides whether a book ships (placeholder
rejection, stylepass sidecars, non-empty grounded claims), and nothing exercises it:
the harness only ever runs draft mode with blocks missing (`evals/run_evals.py:43`).
The gate that matters most is the least tested.

## Current state

- `quoin/check.py:88` region — release-only branch: placeholders, sidecars, claims.
- `quoin/blocks.py:12` region — block status/validation (present/missing/invalid).
- Fixture books: `evals/fixtures/sample/` (2 block slots, unfilled) and
  `evals/fixtures/furniture/` (from plan 002).

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Unit tests | `python3 -m unittest discover -s tests` | pass |
| Evals | `python3 evals/run_evals.py --iteration 2` | `all_pass: true` |

## Scope

**In scope**: `evals/fixtures/sample/blocks-valid/` (a set of valid authored blocks +
sidecars for the sample book, synthetic prose), `evals/run_evals.py` (E16-E18),
`tests/test_release_gates.py` (create). Fix `quoin/` code ONLY where a test reveals a
gate not enforcing its documented contract, and list every such fix in the closeout.
**Out of scope**: relaxing any gate; `corpus/`.

## Steps

1. Author valid blocks for the sample book's two slots (title_deck + interlude,
   synthetic prose, claims with quoted support, stylepass sidecars). Harness copies
   them in for release-mode runs only.
   **Verify**: `quoin build && quoin check --release` in the temp sample book → all
   PASS, exit 0.
2. E16: release run with valid blocks → PASS. E17: release run with one block missing
   → `check --release` exits nonzero and names the block. E18: release run with a
   corrupted sidecar (claims: []) → exits nonzero naming the empty-claims gate.
   **Verify**: evals all green.
3. `tests/test_release_gates.py` failure matrix via direct function calls where
   possible, CLI subprocess otherwise: malformed block JSON, block_id mismatch with
   filename, `<script>` in html, invalid XHTML fragment, missing sidecar, placeholder
   in non-draft build (build without `--draft` and missing block → hard error).
   **Verify**: unit tests pass, each case asserts the specific complaint substring.

## Done criteria

- [ ] Evals E1-E18 `all_pass: true`; unit suite green
- [ ] Every gate in check.py's release branch has at least one failing-input test
- [ ] Any gate-enforcement fix is listed in the closeout with one line
- [ ] `plans/README.md` updated

## STOP conditions

- A release gate turns out to be unimplemented (documented but absent): report scope
  before writing it — that is a compiler change beyond test work.

## Maintenance notes

New release gates added by later plans must land with their E-row and failure-matrix
case in the same commit.
