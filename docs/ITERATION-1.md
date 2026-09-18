# Iteration 1 report (2026-08-29)

## What ran

- M1 package implemented (5 commits, `8248e70..2ecbc39`), all 10 evals green,
  independently re-run by the coordinator before acceptance.
- vol-2 build #1 (draft, placeholder blocks): 3.0 MB EPUB, 26 spine entries, 64,296
  source words byte-verified, deterministic. Exposed 4 normalization bugs:
  RSC-016 fatal from mkdocs unquoted attributes (liu), web furniture surviving
  extraction (edit buttons, headerlinks, trailing Comments heading), file-type sources
  not normalized at all (Substack furniture, remote images, 10 epubcheck errors), one
  dangling cross-document link (enns-closing).
- 11 authored blocks written by a 22-agent workflow (draft pass + separate style pass
  per block), 3m34s wall, 0 errors, all hygiene scans clean, stylepass sidecars with
  grounded claims recorded.
- vol-2 build #2 (blocks in): `quoin check` all PASS including EPUBCheck 0/0/0,
  contamination, privacy, determinism. Placeholder count in packaged EPUB: 0.

## Timings

| Step | Wall |
|---|---|
| CLI implementation (implementer seat) | ~25 min |
| 11 authored blocks (22 agents, pipelined) | 3m 34s |
| vol-2 fetch (9 sources, 3 owned EPUBs + web) | seconds |
| assemble | 119 ms cold, cached warm |
| full check incl. EPUBCheck | ~8 s |

## Closed at iteration boundary

- Normalization fixes committed as `0203c4b`; coordinator wiped `sources/normalized/`
  and the cache and reproduced the full green check table from the committed tree,
  EPUB SHA `3babc9ac…` matching the implementer's report. Iteration 1 accepted.
- Liu word count 1003 → 1002 explained: the trailing "Comments" heading was furniture,
  not article text. All other sources byte-stable.
- Prose spot-check (coordinator, read-aloud): interlude-m2 and intro-enns pass; honest
  cautions present (Enns sells the training; buyer translation required). Full 11-block
  review belongs to Alex on the draft EPUB.
- Iteration 2 scope is seeded in SPEC-M2-NOTES.md (media namespacing, alt text,
  media-type sniffing, remote image embedding, section_locator, device profiles), with
  three eval cases donated by the canonical vol-2 worker's manual render pass.
