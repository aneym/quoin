# Plan 009: Root README for external users

> **Executor instructions**: Follow step by step; verify each step. STOP conditions
> are binding. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- quoin/cli.py quoin/check.py quoin/assemble.py`
> The README documents live behavior; write it against HEAD, not against this plan.

## Status

- **Priority**: P3 · **Effort**: S · **Risk**: LOW
- **Depends on**: 003 (documents the discovery order it introduces)
- **Category**: docs
- **Planned at**: commit `0203c4b`, 2026-08-29

## Why this matters

The repo entry points are internal iteration docs tied to a private corpus; the
package metadata declares no README, license, or URLs. An external visitor cannot
install, build a first book, or learn the guarantees. The README is also the public
statement of the wedge: a deterministic compiler whose authored slots any agent
harness fills through `quoin blocks --json`.

## Current state

- No `README.md` at repo root. `docs/ARCHITECTURE.md` is internal (owner paths,
  iteration plan). `pyproject.toml` has no `readme`, `license`, `urls` keys.
- Working commands to document (verify each against HEAD before writing): init,
  fetch (`--offline`), blocks (`--missing`, `--json`), build (`--draft`), check
  (`--release`), doctor.

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Quick-start dry run | follow your own README quick start verbatim in `/tmp/qsr` | a built sample EPUB, check PASS |
| Evals | `python3 evals/run_evals.py --iteration 2` | `all_pass: true` |

## Scope

**In scope**: `README.md` (create), `pyproject.toml` (`readme`, `urls`; ADD NO
license field — licensing is undecided, see STOP), one line in
`docs/ARCHITECTURE.md` pointing at the README.
**Out of scope**: choosing a license (owner decision; write "License: not yet
chosen"), publishing anywhere, changing CLI behavior.

## Steps

1. Write `README.md` (~120 lines): what quoin is (three sentences, the two-layer
   design); requirements (python ≥3.12, Pillow, java + EPUBCheck with the plan-003
   resolution order); install (`pip install -e .`); quick start (init → edit
   manifest → fetch → blocks → build --draft → check) with a minimal manifest
   example using one public-domain web page; the agent loop (work orders, block +
   sidecar JSON, release gates); guarantees (verbatim source text, byte-identical
   builds, timed hashed build records); the rights ledger stance (private drafts vs
   release gates, the tool records rather than launders rights); troubleshooting
   (doctor, common check FAIL rows); development (unittest, evals, ruff/mypy if plan
   008 landed); roadmap pointer to docs/ARCHITECTURE.md.
   Prose rules: plain concrete language, no em dashes, no promotional adjectives,
   no "not just X but Y".
2. Execute your own quick start verbatim in a clean temp dir.
   **Verify**: it completes with check PASS; fix the README (not the reader) where it
   failed.
3. Wire `readme = "README.md"` in pyproject.
   **Verify**: `python3 -m pip install -e . --dry-run` (or a build) accepts metadata.

## Done criteria

- [ ] Quick start reproduced verbatim by you in a clean dir
- [ ] `grep -c aneyman README.md` → 0; no private paths anywhere in it
- [ ] Evals still green; `plans/README.md` updated

## STOP conditions

- The quick start cannot work without a machine-specific path (means plan 003 is
  incomplete — report, do not paper over with a private path).
- You feel the need to state a license: that decision is the owner's.

## Maintenance notes

CI should eventually run the quick start (plan 008's workflow can add it as a job
once EPUBCheck discovery is portable everywhere).
