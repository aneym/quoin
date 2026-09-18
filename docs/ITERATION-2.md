# Iteration 2 report (2026-08-29)

## Scope executed

All ten plans in `plans/` landed (001-010), driven by an /improve audit (two audit
agents, 16 vetted findings, 0 rejected as false; one duplicate). Commits `5b3764d`
through `0f91f6d`, 15 `i2:` commits.

What the compiler gained:
- Characterization tests over the source-fidelity boundary (normalize.py), then a
  furniture fixture book encoding every real shipped failure class (E11-E13).
- Portability: font + EPUBCheck resolution orders, zero machine-specific paths,
  proven by a README quick start executed in a clean directory against a Gutenberg
  source.
- One validation boundary: nested manifest validation with named-field complaints,
  user-error exit 1 vs compiler-bug exit 2.
- Media pipeline: per-source namespaced images, magic-byte sniffing, ornamental
  rejection, remote-image snapshots, alt policy (draft waivers, release enforcement),
  image integrity + in-archive link resolution rows; 6 of the canon worker's 9
  donated checks DONE, 2 forward-compatible SKIPs, ink-ratio deferred to visual QA.
- Security: id charset gates, path containment (file/cover confined; absolute epub
  locators deliberately allowed and recorded as external inputs), fetch timeout and
  20 MB cap, complete cache keys (code version + cover image).
- Release gates proven by failing inputs (E16-E18 + 7-test failure matrix), which
  caught and fixed a real hole: an empty claims array passed the claims gate.
- The agent contract pack: work orders now carry block + stylepass schemas, valid
  examples, output paths, and check commands; 79-line AGENTS.md in every scaffold.
- ruff + mypy + CI; mypy caught a live crash (`<div class>` valueless attribute).

## Boundary verification (rebuild #3 of 5)

- Cold vol-2 rebuild from the committed tree: fetch --offline + build + full check in
  2.51 s wall; 14 check rows PASS; EPUBCheck 0/0/0.
- Determinism hash `df281e14…` UNCHANGED across the entire iteration including the
  ruff-format sweep, which is the strongest evidence the format/lint pass changed no
  output bytes.
- Full gate: ruff check clean, ruff format --check clean (47 files), mypy clean
  (12 files), 72 unit tests, evals E1-E18 all PASS.

## Process notes

- Volume outage mid-iteration: macOS revoked external-volume access machine-wide for
  ~25 minutes; all executors held correctly (one had deleted the offline fetch cache
  moments before, recovered it byte-identically from checked-in raws). A background
  watch resumed the loop automatically when access returned.
- Executor STOP conditions fired four times, all legitimate plan defects
  (undefined QuoinError owner, two scope omissions, the alt_overrides ceiling); each
  produced a coordinator ruling and a plan amendment rather than improvisation.
- The sol-seat implementers stall after each message batch (one work unit per nudge);
  Sonnet-pinned general-purpose agents ran plans 002/005/006/007/008 straight
  through. Seat choice matters more than plan quality for uninterrupted execution.

## Carried to iteration 3

- Real alt text for the 29 waived publisher figures via a vision-capable agent.
- Ink-ratio blank-page detection (needs a renderer), device CSS profiles, kepub
  output.
- Size-cap boundary unit test (010 residual), live PATH-wrapper EPUBCheck test.
- Recall-prompt and multi-author manifest concepts if vol-3 wants them.
