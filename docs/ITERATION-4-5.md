# Iterations 4 and 5 report (2026-08-29)

## Iteration 4 (plan 014, commits 28a6ec9..1328449)

- Divider-aware ink floor with ZERO byte change: dividers identified from the spine's
  existing kind=="movement" field at check time; `check --visual` now passes all 26
  corpus pages honestly ("22 >= 0.2% dark, 4 divider pages >= 0.05% dark") and its
  pass message reports both floors (the executor caught its own hardcoded-message
  honesty gap and fixed it in-scope).
- Residual tests closed: fetch 20 MB boundary (both sides), real-executable
  PATH-wrapper EPUBCheck discovery + parser test. 105 unit tests total.
- Formatting drift fixed; docs and eval results committed as housekeeping.

## Iteration 5: final sweep and rebuild #5

Full clean cold chain (normalized sources and outputs wiped, rebuilt from raw
sources and owned EPUBs): fetch --offline → build → check --release → check --visual
→ build --profile kepub → check --profile kepub, **13.87 s wall total**. Both
artifacts produced (3.0 MB epub + 3.0 MB kepub), every gate green, release
determinism `a2931dc2…` stable.

## The five vol-2 rebuilds

| # | What | Wall | Result |
|---|---|---|---|
| 1 | Draft, placeholder blocks (M1 CLI) | ~2 s | Exposed 4 normalization bugs (1 fatal) |
| 2 | Draft with 11 authored blocks | ~2 s | First fully green draft check |
| 3 | I2 boundary cold rebuild | 2.51 s | 14 rows green, hash stable through lint sweep |
| 4 | First release-mode build (vision alt text merged) | 3.57 s | All 16 release rows green |
| 5 | Full clean cold, all profiles and gates | 13.87 s | Release + visual + kepub all green |

Authored content cost once: 11 blocks by 22 agents in 3m34s (draft + separate style
pass), 33 figure alts by 5 vision agents in 73 s. Everything else is deterministic
and cached.

## Loop verdict

The iteration protocol held: /improve audits produced 19 vetted findings across two
passes, every one either fixed with a repro or explicitly rejected with a reason;
executor STOP conditions fired six times, all legitimate plan defects or real
findings, each resolved by a coordinator ruling recorded in plans/README.md; the
determinism baseline moved exactly once, deliberately, for the e-ink CSS fix. Two
machine-wide volume outages interrupted work; both times every agent held state
cleanly and resumed from artifacts.

Adoption is already ahead of the roadmap: a machine-wide `quoin` skill and a uv-tool
editable install (`~/.local/bin/quoin`) appeared from outside this loop, meaning any
agent session on this machine can now run the compile loop from the skill alone.

## What iteration 6+ would hold (not scheduled)

Rust port once the JSON contracts survive vol-3 unchanged; license decision (owner);
recall-prompt and multi-author manifest concepts; device-lab visual QA beyond
ink-ratio (real Kobo/BOOX renders); publishing the repo (README ships URL-less until
then).
