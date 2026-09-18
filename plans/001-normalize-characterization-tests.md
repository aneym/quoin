# Plan 001: Characterization tests for normalize.py

> **Executor instructions**: Follow this plan step by step. Run every verification
> command and confirm the expected result before moving on. If anything under "STOP
> conditions" occurs, stop and report — do not improvise. When done, update this
> plan's row in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- quoin/normalize.py tests/`
> If `quoin/normalize.py` changed since `0203c4b`, compare the symbol list below
> against the live file before proceeding; on a mismatch, STOP.

## Status

- **Priority**: P1 · **Effort**: M · **Risk**: LOW
- **Depends on**: none
- **Category**: tests
- **Planned at**: commit `0203c4b`, 2026-08-29

## Why this matters

`quoin/normalize.py` (139 lines) is the source-fidelity boundary: it turns fetched
web pages, file fragments, and EPUB chapters into packaged XHTML while promising that
visible source text is never altered. It has already shipped one EPUBCheck fatal
(unquoted mkdocs attributes) and three furniture classes to a real book, fixed in an
83-line change with no targeted tests. Today only the end-to-end evals observe it, so
a regression cannot be localized. These tests freeze current behavior before plan 005
modifies this module for media handling.

## Current state

- `quoin/normalize.py` — the module under test. Public symbols used elsewhere
  (verified via `quoin/check.py:17` imports): `CONTAMINATION`, `body_inner`,
  `word_count`; plus the extraction entry points used by `quoin/fetch.py` (open the
  file and enumerate; expect an article extractor and a stateful `XHTMLCleaner`).
- There is no `tests/` directory. The only harness is `evals/run_evals.py`
  (end-to-end over a fixture book).
- Runtime deps are stdlib + Pillow. Do not add pytest; use `unittest`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Run new tests | `cd /Volumes/StudioExt/repos/quoin && python3 -m unittest discover -s tests -v` | all pass, exit 0 |
| Regression guard | `python3 evals/run_evals.py --iteration 2` | `all_pass: true` |

## Scope

**In scope**: `tests/__init__.py`, `tests/test_normalize.py` (create both).
**Out of scope**: any file under `quoin/` (this plan changes zero compiler behavior),
`corpus/`, `evals/fixtures/`.

## Git workflow

Branch: work directly on `main` (repo convention so far). One commit:
`i2: add normalize characterization tests`. Do not push.

## Steps

### Step 1: Read the module and list its public surface

Read `quoin/normalize.py` fully. In the test file's docstring, record the function
and class names you found, so the next reader sees what was frozen.

**Verify**: `python3 -c "import quoin.normalize as n; print([x for x in dir(n) if not x.startswith('_')])"` → prints the symbols you listed.

### Step 2: Write table-driven characterization cases

Create `tests/test_normalize.py` with inline HTML string fixtures (no files) covering
at minimum, one test per row:

1. mkdocs page with UNQUOTED attributes (`<a href=https://x rel=edit>`) → output is
   well-formed XML (assert `xml.etree.ElementTree.fromstring` parses the output
   wrapped in a root element) and the edit-button anchor is gone.
2. mkdocs `headerlink` pilcrow anchors inside headings → removed, heading text kept.
3. Trailing `<h2>Comments</h2>` section → removed; a mid-article heading named
   "Comments policy" in a paragraph context is NOT removed if current behavior keeps
   it (record whichever current behavior is — this is characterization).
4. Substack furniture: `<picture>` without `img`, `<button>` inside `<a>`, inline
   `<svg>`, remote `<img src="https://substackcdn.com/...">` → all absent from output.
5. Cross-document link `<a href="part0037.xhtml">x</a>` when the target set does not
   include it → link dropped or unwrapped, the anchor TEXT preserved.
6. Entity handling: `&amp;`, `&#8217;`, `&nbsp;` survive round-trip with identical
   visible text.
7. Visible-text preservation: for a clean article fixture, the whitespace-normalized
   text content before and after normalization is identical.
8. `word_count` stability: equal counts for the same content with different
   inter-tag whitespace.
9. Malformed nesting (`<p><div>x</div></p>`) → output still parses as XML.
10. `CONTAMINATION` list: each term present in a furniture fixture is caught by
    whatever scan helper the module exposes; article prose containing the word
    "subscribe" mid-sentence is treated per current behavior (record it).
11. Script/style stripping: `<script>`/`<style>` bodies never appear in output text.
12. An empty/whitespace-only input → no exception; record the current return shape.

Where current behavior is surprising but not clearly a shipped-fatal-class bug, LOCK
it with a comment `# characterization: current behavior, revisit in plan 005`. If a
case exposes a genuine defect (output fails XML parse, or visible text is lost), mark
that single test `@unittest.expectedFailure` with a one-line comment and list it in
your closeout — do not fix the module in this plan.

**Verify**: `python3 -m unittest discover -s tests -v` → ≥12 tests, all pass
(expectedFailures count as pass).

### Step 3: Guard the eval suite still passes

**Verify**: `python3 evals/run_evals.py --iteration 2` → `all_pass: true`.

## Test plan

This plan IS the test plan; there is no existing unit test to model after. Keep one
test method per case, named `test_<case>`, with the fixture string local to it.

## Done criteria

- [ ] `python3 -m unittest discover -s tests` exits 0 with ≥12 tests
- [ ] `git status --short` shows only `tests/` additions (plus plans/README.md row)
- [ ] `python3 evals/run_evals.py --iteration 2` prints `all_pass: true`
- [ ] Any expectedFailure cases are listed in the closeout with one line each

## STOP conditions

- `quoin/normalize.py` lacks a distinct article-extraction entry point or cleaner
  class (module was restructured since `0203c4b`).
- More than 2 cases come out `expectedFailure` — that means current behavior is
  broken enough that plan 005 must be re-scoped; report instead of proceeding.

## Maintenance notes

Plan 005 (media) edits normalize.py next; these tests are its safety net. When 005
adds image handling, extend this file rather than starting another.
