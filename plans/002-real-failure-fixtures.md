# Plan 002: Eval fixtures from the real failure classes

> **Executor instructions**: Follow step by step; verify each step. On any STOP
> condition, stop and report. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- evals/ quoin/`
> Compare "Current state" against live code on any mismatch; mismatch on
> `evals/run_evals.py` structure is a STOP.

## Status

- **Priority**: P1 · **Effort**: M · **Risk**: LOW
- **Depends on**: plans/001-normalize-characterization-tests.md
- **Category**: tests
- **Planned at**: commit `0203c4b`, 2026-08-29

## Why this matters

The only eval fixture (`evals/fixtures/sample/`) is one well-formed mkdocs-style page
plus one EPUB chapter. Every ingestion bug that reached the real vol-2 build (unquoted
attributes, surviving furniture, un-normalized `file` sources, dangling cross-document
links) passes through territory the fixture never exercises, so "all evals green" says
little about ingestion. This plan adds a second fixture book that encodes each shipped
failure class as a minimal synthetic source, making regressions visible in the harness
that gates every iteration.

## Current state

- `evals/fixtures/sample/` — fixture book: `book.toml`, `manifest.json` (a `web` and
  an `epub` source, 2 block slots), `sources/raw/kanekar.html`, a small fixture EPUB.
- `evals/run_evals.py` (94 lines) — copies the fixture to a temp dir, runs
  fetch/build/check offline, asserts E1–E10, writes `evals/results-i<N>.json`.
- Rights rule: fixtures must be SYNTHETIC (authored for this repo), never copied
  article text. A paragraph of lorem-style original prose per source is fine.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Evals | `cd /Volumes/StudioExt/repos/quoin && python3 evals/run_evals.py --iteration 2` | `all_pass: true`, E1–E13 listed |
| Unit tests | `python3 -m unittest discover -s tests` | pass |

## Scope

**In scope**: `evals/fixtures/furniture/**` (create), `evals/run_evals.py` (extend).
**Out of scope**: `quoin/` modules (if a new fixture FAILS the current compiler, see
STOP conditions), `evals/fixtures/sample/` (leave the baseline untouched), `corpus/`.

## Git workflow

One commit on `main`: `i2: add furniture fixture book and evals E11-E13`. Do not push.

## Steps

### Step 1: Author the furniture fixture book

Create `evals/fixtures/furniture/` mirroring `sample/`'s layout with three sources:

- `web` source `mkdocs-ugly`: raw HTML with unquoted attributes, md-content__button
  edit/view anchors with inline SVG, headerlink pilcrows, an admonition div, and a
  trailing `<h2>Comments</h2>` — around 150 words of original synthetic prose.
- `file` source `newsletter-frag`: a fragment with `<picture>` missing `img`,
  `<button>` inside `<a>`, inline `<svg>`, a remote `https://example.invalid/x.png`
  image, and a fragment-only `<a href="#foo">` — around 100 words.
- `epub` source `mini-book`: reuse or extend the existing fixture EPUB with a chapter
  whose HTML contains a cross-document `<a href="other-chapter.xhtml">` pointing
  outside the extracted set.

Manifest: one movement referencing all three sources and one interlude block slot
(leave the block missing; draft mode must placeholder it). Record each source's
expected post-normalization word count in the manifest under a fixture-only key
`expected_words` per source (the harness reads it in step 2).

**Verify**: `cd <temp copy> && PYTHONPATH=/Volumes/StudioExt/repos/quoin python3 -m quoin fetch --offline` (run via the harness in step 2 if fetch lacks a standalone offline flag for file fixtures) → completes, `sources/records.json` lists 3 sources.

### Step 2: Extend the harness

In `evals/run_evals.py`, after the existing E1–E10 over `sample/`, run the same
offline loop over `furniture/` and add:

- E11: build+check over the furniture book ends with `epubcheck` PASS and
  `contamination` PASS (proves the mkdocs/substack classes stay fixed).
- E12: packaged word counts equal the manifest's `expected_words` (proves furniture
  removal does not eat prose and prose is not silently truncated).
- E13: the packaged XHTML for `mini-book` contains no `href` to `other-chapter.xhtml`
  and the anchor's text is still present (proves dangling-link handling).

Keep result-file shape unchanged apart from the three new eval rows.

**Verify**: `python3 evals/run_evals.py --iteration 2` → E1–E13 all PASS,
`all_pass: true`.

## Test plan

The evals are the tests. Additionally assert in E11's detail string which furniture
markers were checked, so a future failure names the class.

## Done criteria

- [ ] `python3 evals/run_evals.py --iteration 2` → 13 evals, `all_pass: true`
- [ ] `evals/fixtures/furniture/` contains no text copied from any real publication
- [ ] `python3 -m unittest discover -s tests` still exits 0
- [ ] `plans/README.md` row updated

## STOP conditions

- A furniture fixture makes the CURRENT compiler fail (fatal or check FAIL): that is
  a live bug, not a fixture problem. Report the failing class with the eval output;
  do not patch `quoin/` here.
- `run_evals.py` has been restructured away from the copy-fixture-to-tempdir shape.

## Maintenance notes

Every future shipped ingestion bug gets a minimal synthetic source added to the
furniture book in the same commit as its fix. The canon vol-2 worker's donated checks
(plans/005) will extend this book with image-class fixtures.
