# Plan 014: Iteration-4 residuals

> **Executor instructions**: Follow step by step; verify each step. STOP conditions
> are binding. Update `plans/README.md` when done (add your own row 014 if absent).
>
> **Drift check (run first)**: `git diff --stat 008695f..HEAD -- quoin/ tests/ evals/`

## Status

- **Priority**: P1 · **Effort**: M · **Risk**: LOW
- **Depends on**: 012, 013
- **Category**: bug + tests + housekeeping
- **Planned at**: commit `d7d80a0`, 2026-08-29

## Why this matters

Iteration 3 left five known residuals, each small, none worth its own plan. Closing
them makes `check --visual` honest on the real corpus (three by-design divider pages
currently fail ink_ratio), finishes the deferred test coverage, and clears the
housekeeping drift so iteration 5's final sweep starts from a clean tree.

## Steps

1. **Divider-aware ink floor (coordinator ruling on 012's finding).** Movement
   divider pages are sparse by design (a single centered h1) and measured 0.18%
   against the 0.2% threshold. Assemble knows which spine entries are movement
   dividers: mark them structurally (e.g. a `data-quoin-kind="divider"` attribute on
   the body or a recorded list in build-record.json — pick the one that keeps the
   default-profile hash change to exactly one recorded baseline move, or zero if you
   can mark via build-record only). `ink_ratio_check` applies a 0.05% floor to
   divider pages (still catches truly blank output) and keeps 0.2% for all others,
   reporting which floor applied per offender. If the marking approach requires a
   byte change, record the new baseline hash in the closeout exactly as 013 did.
   **Verify**: `corpus/vol2 check --visual` all rows PASS; a synthetic blank divider
   test still fails in `tests/test_ink_ratio.py`.
2. **Fetch size-cap boundary test** (010 residual): unit test that a stream just
   over the 20 MB cap raises the named error and just under passes.
3. **PATH-wrapper EPUBCheck test** (003/009 residual): unit test with a fake
   `epubcheck` wrapper script on a temp PATH proving discovery tier 3 and the shared
   output parser work.
4. **Format drift**: run `ruff format` on `tests/test_kepub.py` (the one
   pre-existing unformatted spot), separate commit.
5. **Housekeeping commit**: commit the coordinator's tracked-file edits currently
   dirty in the tree: `docs/ARCHITECTURE.md` (I3/I4/I5 roadmap update) and
   `docs/ITERATION-3.md` (new), plus `evals/results-*.json` refreshed once from a
   final green run, as `i4: docs and results housekeeping`. Read both docs first;
   commit them as-is, they are the coordinator's content.
6. Full gate: ruff, mypy, unittest, evals (E1-E20), corpus draft chain AND
   `check --release` AND `check --visual` all green.

## Scope

**In scope**: `quoin/assemble.py` (divider marking only), `quoin/check.py`
(ink floor), `tests/`, `evals/results-*.json`, `tests/test_kepub.py` formatting,
`docs/ARCHITECTURE.md` + `docs/ITERATION-3.md` (commit-only, no content edits),
`plans/README.md`.
**Out of scope**: corpus content, thresholds beyond the divider floor, new features.

## STOP conditions

- The divider marking cannot avoid touching non-divider bytes.
- Any gate that was green goes red for a reason unrelated to your change.

## Done criteria

- [ ] `check --visual` on corpus/vol2: every row PASS
- [ ] Full gate green; tree clean except untracked corpus/plans-docs convention files
- [ ] `plans/README.md` updated with row 014 DONE and any baseline-hash note
