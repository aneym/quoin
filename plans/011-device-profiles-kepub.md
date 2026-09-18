# Plan 011: Device CSS profile and kepub output

> **Executor instructions**: Follow step by step; verify each step. STOP conditions
> are binding. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0f91f6d..HEAD -- quoin/` — this plan
> was stamped after iteration 2 closed; on drift, re-read live code first.

## Status

- **Priority**: P1 · **Effort**: M · **Risk**: MED (touches packaged bytes; the
  baseline EPUB output must stay byte-identical when no profile flag is passed)
- **Depends on**: none (iteration 3 opener)
- **Category**: direction (iteration-3 feature)
- **Planned at**: commit `0f91f6d`, 2026-08-29

## Why this matters

"Full support on all EPUB devices" (owner directive) means the same book must render
correctly in Apple Books, KOReader, Kobo, and BOOX readers. Kobo devices ignore much
of standard EPUB CSS unless the file is a kepub (span-wrapped text nodes enable Kobo's
reading engine: page stats, highlights, faster pagination). The CSS itself must avoid
constructs e-ink engines mishandle.

## Current state

- `quoin/assemble.py` — one CSS literal (`CSS`), one output path, no profiles.
- Owner devices to serve: Apple Books (visual QA baseline), BOOX (Android/KOReader
  family), Kobo. The canon pipeline ships sidecars for KOReader already
  (`/Users/aneyman/artifacts/reading-packets/boox-koreader-sidecars/` exists as
  prior art you may read, read-only).
- kepub algorithm reference: each block-level text element's text nodes get wrapped
  in `<span class="koboSpan" id="kobo.N.M">` (N = paragraph counter, M = segment
  counter); file renamed `.kepub.epub`; everything else unchanged. Study
  https://pgaskin.net/kepubify/ semantics from the code's perspective only if
  offline docs exist; otherwise implement the span-wrapping rule as stated and
  validate with EPUBCheck (spans are valid XHTML; EPUBCheck must stay 0/0/0).

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Tests | `.venv/bin/python -m unittest discover -s tests` | pass |
| Lint/type | `.venv/bin/python -m ruff check . && .venv/bin/python -m mypy quoin` | clean |
| Evals | `.venv/bin/python evals/run_evals.py --iteration 3` | `all_pass: true` |
| Corpus | draft chain in corpus/vol2 | all rows PASS, determinism hash UNCHANGED from `df281e14…` for the default profile |

## Scope

**In scope**: `quoin/assemble.py`, `quoin/cli.py` (`build --profile kepub`),
`quoin/check.py` (check accepts the kepub artifact), CSS review for e-ink safety,
`tests/test_kepub.py` (create), one eval (E19: kepub build of the furniture book
passes EPUBCheck and every koboSpan id is unique/sequential).
**Out of scope**: visual rendering QA (plan 012), corpus manifest, any change to the
DEFAULT profile's bytes (hard gate: default determinism hash unchanged).

## Steps

1. CSS audit for e-ink: replace any viewport units, avoid `position:fixed`, ensure
   page-break properties use both `page-break-*` and `break-*` forms. Only make
   changes that keep the default hash IDENTICAL — if a CSS fix would change bytes,
   STOP and report the proposed diff instead (the owner must approve a
   hash-breaking change).
2. `build --profile kepub` → `out/<slug>.kepub.epub`: post-process each spine
   xhtml with koboSpan wrapping (parser-based, never regex over raw markup; reuse
   the normalize.py parsing utilities), leave sources' text bytes otherwise
   untouched, record the profile + its own determinism hash in build-record.json.
3. `quoin check --profile kepub` runs the full row set against the kepub artifact
   (word counts must still match: spans add no text).
4. Tests + eval E19; full gate.

## Done criteria

- [ ] Default-profile corpus hash still `df281e14…`
- [ ] kepub artifact: EPUBCheck 0/0/0, word counts identical, unique sequential span ids
- [ ] Full gate green; `plans/README.md` updated

## STOP conditions

- Any default-profile byte change (report the diff, do not commit it).
- koboSpan wrapping breaks EPUBCheck on real corpus content.

## Maintenance notes

Plan 012's renderer QA should screenshot BOTH profiles. A future `--profile` for
fixed-layout or large-print composes the same way.
