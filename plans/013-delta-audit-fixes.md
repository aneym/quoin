# Plan 013: Fix the three delta-audit findings

> **Executor instructions**: Follow step by step; verify each step. STOP conditions
> are binding. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0f91f6d..HEAD -- quoin/ tests/ evals/`
> Plan 011 (kepub) lands before this; re-read live code where it drifted.

## Status

- **Priority**: P1 · **Effort**: S · **Risk**: MED (013-2 changes check() semantics)
- **Depends on**: 011 (file overlap only)
- **Category**: bug (post-iteration-2 delta audit, all three reproduced end-to-end)
- **Planned at**: commit `0f91f6d`, 2026-08-29

## Why this matters

The delta audit reproduced three defects introduced or exposed by iteration 2, two of
which quietly defeat release gates: an alt override authored exactly per the
documented convention is never applied yet the alt gate passes, and `quoin check
--release` can bless a stale EPUB whose sources changed after the last build. The
third makes the most common user mistake print "crashed (bug)" with a traceback.

## Findings to fix (verify each repro yourself before changing code)

1. **alt_overrides key mismatch.** `quoin/fetch.py:152` and `:297` resolve overrides
   by original `<img src>` string; `quoin/check.py:198-199` reads them by packaged
   basename (the documented convention, used by the furniture fixture). Repro: build
   the furniture fixture; the overridden image ships `alt=""` while the release
   alt_text row reads clean. Fix: both resolvers use `stored_name` as the key.
   Extend `tests/test_media.py` to assert the PACKAGED alt attribute value, and
   tighten eval E15 to read the attribute, not just the row's pass flag.
2. **check() validates a stale artifact.** `quoin/check.py:111-112` rebuilds only
   when the EPUB is absent. Repro: build draft, tamper a normalized source, run
   `check --release`: privacy/contamination read clean off the old zip. Fix: call
   `build(root, draft=not release)` unconditionally at the top of `check()` (build
   is cache-gated, so unchanged inputs cost ~nothing). First grep
   `tests/test_release_gates.py` and `evals/run_evals.py` for tests that pre-seed
   `out/<slug>.epub` relying on skip-if-exists; adapt them honestly (give them a
   real buildable book) rather than special-casing check().
3. **Incomplete QuoinError migration.** `quoin/blocks.py:110` raises plain
   ValueError for a missing block, so a bare `quoin build` (which is release mode:
   no `--release` flag exists, only `--draft`) exits 2 with a traceback. Fix: raise
   `QuoinError` there; update `tests/test_release_gates.py::test_missing_block_in_release_build_is_hard_error`
   to assert QuoinError/exit 1; sweep fetch.py's remaining plain
   ValueError/FileNotFoundError raise sites for user-error cases into QuoinError in
   the same pass (crash-worthy internal errors stay plain).

## Commands

Full gate via `.venv/bin/python`: ruff check, ruff format --check, mypy quoin,
unittest discover, `evals/run_evals.py --iteration 3`, corpus/vol2 draft chain (all
rows PASS, default determinism hash `df281e14…` unchanged — none of these fixes may
alter packaged bytes for unchanged inputs; fix 1 changes furniture-fixture bytes
only, where the override now actually applies).

## Scope

**In scope**: `quoin/fetch.py`, `quoin/check.py`, `quoin/blocks.py`, `quoin/cli.py`
(only if the exit taxonomy needs a touch), `tests/test_media.py`,
`tests/test_release_gates.py`, `evals/run_evals.py` (E15 tightening), README row.
**Out of scope**: corpus/, fixtures/sample manifest, plan-011's kepub code paths
beyond mechanical merge, any new check rows.

## Done criteria

- [ ] All three repros now fail before the fix and pass after (state each in closeout)
- [ ] Furniture fixture ships the override's alt text in the packaged EPUB
- [ ] Tampered-source repro: `check --release` rebuilds and fails the tampered row
- [ ] Bare `quoin build` with a missing block: clean one-line error, exit 1
- [ ] Full gate green; corpus default hash unchanged
- [ ] `plans/README.md` updated

## STOP conditions

- Unconditional rebuild in check() breaks the eval harness in a way that needs more
  than giving tests real buildable books.
- Any corpus/vol2 row changes state other than staying PASS.

## Maintenance notes

E15's tightened assertion is the pattern: evals must read the artifact, not the
checker's opinion of the artifact, wherever both exist.
