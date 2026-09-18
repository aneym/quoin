# Plan 005: Media pipeline and donated verify checks

> **Executor instructions**: Follow step by step; verify each step. On any STOP
> condition, stop and report. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- quoin/`
> Plans 001-004 land first, so quoin/ WILL have changed; the excerpts here describe
> commit `0203c4b` behavior. Re-read the touched modules before editing and treat the
> tests from 001/002 as the authority on current behavior.

## Status

- **Priority**: P1 · **Effort**: L · **Risk**: MED (touches normalize/fetch/assemble/check)
- **Depends on**: 001, 002, 003
- **Category**: direction (iteration-2 feature)
- **Planned at**: commit `0203c4b`, 2026-08-29

## Why this matters

Iteration 1 ships text-only web/file sources (remote images dropped) and copies EPUB
chapter images without collision safety. The canonical vol-2 worker found by manual
inspection of 49 pages: a cross-chapter image filename collision showing the wrong
figure, publisher figures with alt="", and a JPEG served from a .png URL failing the
media-type rule. Full media support with mechanical checks is what "full service EPUB"
means, and every check added here replaces a page-by-page human inspection.

## Current state (at 0203c4b)

- `quoin/fetch.py` — epub sources: copies chapter files verbatim, copies referenced
  images; web sources: extracts article; file sources: normalized like web since
  `0203c4b`, remote images DROPPED with a build-record note.
- `quoin/assemble.py` — packages normalized xhtml + any copied chapter media; cover
  generated via Pillow (portable resolver after plan 003).
- `quoin/check.py` — rows: mimetype, spine, word_counts, contamination, privacy,
  epubcheck, determinism (+ release gates). No image checks.
- Full donated-check specification: `docs/SPEC-M2-NOTES.md` (read it now — it is part
  of this plan's contract; the ink-ratio check listed there is DEFERRED, see scope).

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Unit tests | `python3 -m unittest discover -s tests` | pass |
| Evals | `python3 evals/run_evals.py --iteration 2` | `all_pass: true` (incl. new E14+) |
| Corpus | `cd corpus/vol2 && PYTHONPATH=.. python3 -m quoin fetch && python3 -m quoin build --draft && python3 -m quoin check` | all PASS |

## Scope

**In scope**: `quoin/fetch.py`, `quoin/normalize.py`, `quoin/assemble.py`,
`quoin/check.py`, `quoin/schemas/manifest.schema.json` (new optional per-source
`images` policy + `alt_overrides`), `tests/` extensions, `evals/fixtures/furniture/`
extensions, `evals/run_evals.py` (new evals).
**Out of scope**: ink-ratio blank-page rendering (needs a browser renderer; deferred
to the visual-QA iteration), kepub/device profiles (iteration 3), any cover redesign,
`corpus/vol2/blocks/`.

## Steps

### Step 1: Namespaced media and correct in-archive matching

All packaged media paths become `media/<source_id>/<original-basename>`; rewrite refs
during normalization. Two sources with the same basename can no longer collide.

Audit CORRECTNESS-03 (verified at `fetch.py:58-82`) is fixed here too:
- `fetch.py:66-70` computes a base-relative `archive_name` per `<img>` and then never
  uses it; matching falls back to `endswith(basename)` taking `candidates[0]`
  (`fetch.py:71,74`), so same-named images in different archive dirs embed the wrong
  file. Use the computed `archive_name` for an exact match first; basename fallback
  only when exact misses, recorded as a note.
- A remote/hotlinked `<img src="https://...">` inside an epub chapter currently
  raises and aborts the whole fetch (`fetch.py:72-73`); route it through step 2's
  snapshot download instead (or drop with a per-image note when offline).
- `normalize.validate_xhtml()` exists and is never called (confirmed by grep): call
  it on every normalized document immediately after writing, so malformed output
  fails at fetch time with the source id, not later inside EPUBCheck.
- While in the file, replace the inline `__import__("re")` calls at `fetch.py:60-64`
  with a normal top-level import (mechanical cleanup).

Unit test: two synthetic epub chapters, same image basename, different bytes → both
packaged, each xhtml references its own; a chapter with a hotlinked image no longer
aborts the fetch.

**Verify**: new unit tests pass.

### Step 2: Remote image snapshot for web/file sources

At fetch time, download each `<img>`'s remote URL into
`sources/media/<source_id>/`, recording url/bytes/sha256 in `sources/records.json`
(this is the "snapshot" rights dimension: record it). `--offline` uses only existing
snapshots. Images that fail to download are dropped with a per-image note in the
record (current behavior, now per-image). Rewrite refs to the namespaced packaged
path.

**Verify**: furniture fixture gains a fake "remote" image served from a local file://
fixture or pre-seeded snapshot; eval asserts it is packaged and referenced.

### Step 3: Magic-byte sniffing

Sniff every image's real type (jpeg/png/gif/svg/webp) from magic bytes; declare and
name the packaged file by sniffed type regardless of URL extension; record
mismatches. SVG passes through only if well-formed XML, else dropped with note.

**Verify**: unit test with a JPEG bytes blob named `x.png` → packaged as jpeg,
mismatch recorded.

### Step 4: Ornamental and alt policy checks (new check rows)

Per docs/SPEC-M2-NOTES.md: reject/drop images under 120px on either edge or under
2.5KB as ornamental (drop at normalize with note, not a check failure); new check
rows: `alt_text` (every non-cover img has alt of ≥ 8 chars, satisfied from source or
manifest `alt_overrides[basename]`, else FAIL listing offenders), `image_integrity`
(every packaged image hash equals its snapshot/source hash; every referenced image
packaged; nothing packaged but cover unreferenced), `links` (every internal href,
resolved against ITS OWN document's directory inside the zip, is a real entry).

**Verify**: corpus/vol2 chain → new rows appear; expect `alt_text` to FAIL honestly
on publisher alt="" figures → add `alt_overrides` entries to
`corpus/vol2/manifest.json` for the Moesta/Enns/Block figures (this file edit is
explicitly permitted here, keep it minimal and factual: describe the figure).

### Step 5: Evals

E14 media namespacing+integrity over the extended furniture book; E15 alt/sniffing
policy. Wire per docs/SPEC-M2-NOTES.md items 1-3, 6, 7, 9.

**Verify**: `python3 evals/run_evals.py --iteration 2` → all evals PASS.

## Test plan

Extend `tests/test_normalize.py` (image ref rewriting, ornamental threshold) and add
`tests/test_media.py` (sniffing, namespacing, integrity helpers). Model layout on
plan 001's file.

## Done criteria

- [ ] All three command groups green, including new check rows on corpus/vol2
- [ ] Recall-ordering and intro-run adjacency checks from SPEC-M2-NOTES implemented
      as check rows that SKIP cleanly when the manifest declares no prompts /
      single-author sources only
- [ ] `docs/SPEC-M2-NOTES.md` items each marked DONE or explicitly deferred in a new
      "status" line per item
- [ ] `plans/README.md` updated

## STOP conditions

- Word-count invariance breaks after image work (images must never change text
  counts) — report, do not adjust expected counts.
- Enns/Block/Moesta image extraction surfaces DRM or encrypted resources.
- The alt_overrides edit to corpus manifest balloons past ~15 entries.

## Maintenance notes

Ink-ratio and device visual QA build on this in iteration 3 with a real renderer
(ego/argent); keep check rows machine-readable so that layer just adds rows.
