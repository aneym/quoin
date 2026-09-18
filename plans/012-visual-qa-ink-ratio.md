# Plan 012: Rendered visual QA and ink-ratio check

> **Executor instructions**: Follow step by step; verify each step. STOP conditions
> are binding. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0f91f6d..HEAD -- quoin/ evals/`

## Status

- **Priority**: P2 · **Effort**: M · **Risk**: LOW (additive check, release-gated)
- **Depends on**: 011 (screenshots cover both profiles)
- **Category**: tests (the canon worker's donated check #8)
- **Planned at**: commit `0f91f6d`, 2026-08-29

## Why this matters

The canonical vol-2 build caught a broken-stylesheet class of bug only by a human
inspecting 49 rendered pages. The donated fix: render each spine document and flag
pages under 0.2% dark pixels (blank or unstyled). This is the last donated check not
yet mechanical, and it is the foundation the iteration-3 alt-authoring pass reuses
(the same rendering loop yields the images a vision agent describes).

## Current state

- No renderer dependency exists and none may enter the runtime deps. The renderer is
  an OPTIONAL tool discovered at runtime: `quoin check --visual` uses the first of
  `book.toml render_command`, env `QUOIN_RENDER_CMD`, or a discovered
  `agent-browser` binary (present on this machine) to rasterize each spine xhtml to
  PNG in a temp dir. Absent renderer → the row reports SKIP with remediation, never
  FAIL.
- agent-browser usage shape (verify with `agent-browser --help` before coding):
  `agent-browser --session <fresh id> set viewport 1264 1680 1`, `open file://<path>`,
  `screenshot <out.png>`, `close`. Use an isolated session id per run; never the
  default shared session.

## Commands

Full gate as in plan 011 plus: `cd corpus/vol2 && PYTHONPATH=... python3 -m quoin check --visual` → `ink_ratio` row runs, all pages ≥ 0.2% dark pixels.

## Scope

**In scope**: `quoin/check.py` (`--visual` flag + `ink_ratio` row), `quoin/cli.py`,
Pillow-based dark-pixel measurement, `tests/test_ink_ratio.py` (measurement math on
synthetic PNGs only; no renderer in unit tests), eval E20 (SKIP-path: harness runs
without a renderer configured and asserts the row SKIPs cleanly).
**Out of scope**: adding any runtime dependency; CI rendering (CI keeps SKIP);
corpus manifest.

## Steps

1. Measurement function: PNG → fraction of pixels darker than 50% gray; unit-test on
   generated images (all-white → 0, text-like synthetic → above threshold).
2. Renderer discovery + per-page loop + row wiring (`ink_ratio` lists offending
   pages by spine position and file, or SKIP detail naming the config knobs).
3. Run against corpus/vol2 with agent-browser; fix nothing content-side — if a real
   page fails, report it (that is the check working).
4. Tests, E20, full gate.

## Done criteria

- [ ] `check --visual` on corpus/vol2 renders all 26 spine docs and every page passes
- [ ] Without a renderer: row SKIPs with remediation text; evals green in CI-shape
- [ ] Full gate green; README row updated

## STOP conditions

- agent-browser cannot render local file:// xhtml with the book's relative CSS
  (report what it needs — packaging pages standalone is a design change).
- Any real corpus page genuinely under threshold (report as a finding, do not tune
  the threshold to pass).

## Maintenance notes

The rendering loop's PNGs are exactly what the alt-authoring vision pass consumes;
keep the temp-dir layout stable (`<tmp>/<spine-index>-<slug>.png`).
