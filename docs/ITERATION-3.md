# Iteration 3 report (2026-08-29)

## Scope executed

Plans 011, 012, 013 plus the vision alt-text pass. Rebuild #4 achieved the first
fully release-green vol-2 build.

- **011 kepub + e-ink CSS**: `--profile kepub` output with parser-based koboSpan
  wrapping (18 tests, E19). Its STOP fired on real corpus content: whitespace-only
  text nodes inside ol/ul produced invalid spans; fixed to match upstream kepubify
  behavior. Default-profile hash held during the plan; the two e-ink CSS fixes it
  reported (legacy page-break fallback, viewport-unit swap) were applied under a
  coordinator ruling in 013 as a deliberate one-time baseline move.
- **Delta audit** (Sonnet, scope = everything i2 changed): three HIGH-confidence
  reproduced findings, all fixed in **013**: alt_overrides keyed differently in
  fetch vs check (the accessibility gate was passing while overrides never applied),
  check() validating stale artifacts (release PASS on tampered sources), and an
  incomplete QuoinError migration (missing block reported as a crash). E15 tightened
  to read the artifact, not the checker's opinion.
- **Vision alt pass**: a 5-agent workflow read all 33 corpus figures (73 s) and
  authored real descriptions; merged into the manifest as alt_overrides, waivers
  removed. Release-mode alt_text now passes on merit.
- **012 rendered visual QA**: `check --visual` renders every spine page through a
  discovered renderer (agent-browser here; optional, SKIP with remediation when
  absent) and applies the donated 0.2% ink-ratio rule. Its honest finding: three
  movement divider pages measure ~0.18% by design; ruled in plan 014 as a
  divider-aware floor rather than a threshold tune.

## Boundary numbers

- Release-mode vol-2 chain (fetch offline, build, 16-row release check): **3.57 s**,
  every row PASS including alt_text clean, placeholders none, stylepass all present,
  claims all non-empty. EPUBCheck 0/0/0. Determinism `a2931dc2…` (release artifact).
- Full gate at close: ruff + mypy clean, 99 unit tests, evals E1-E20 all pass.
- Default-profile baseline moved once, recorded: `df281e14…` → `b0cfdb60…`
  (e-ink CSS only, verified across two cold rebuilds).

## Carried to iteration 4 (plan 014)

Divider ink floor, size-cap boundary test, PATH-wrapper EPUBCheck test, one
formatting drift, docs/results housekeeping. Iteration 5 then runs the final sweep,
rebuild #5, and the productization report.
