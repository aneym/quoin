# Iteration 2 seed notes (media and rendering)

Collected 2026-08-29 while iteration 1 was closing. Fold into the I2 spec.

## Eval cases donated by the canonical vol-2 worker's manual render pass

Each of these was found by a human-style page inspection; quoin must catch all three
mechanically so nobody inspects 49 pages again.

1. Cross-source image filename collision: two extracted chapters both carried an image
   with the same basename; the second overwrote the first and a Block chapter showed the
   other chapter's flowchart. Fix: namespace media per source id. Check: every packaged
   image's hash equals the hash of the file its source referenced.
   - Status: DONE (plan 005). `sources/media/<source_id>/` namespacing in fetch.py;
     `image_integrity` check row in check.py verifies packaged bytes against each
     source's `index.json` hash.
2. Empty alt attributes on book figures shipped as alt="". Check: images need alt text;
   a slot-declared caption/alt table or a recorded waiver per image.
   - Status: DONE (plan 005). `alt_text` check row requires >= 8 chars, satisfied by
     the packaged alt or by manifest `source.alt_overrides[packaged basename]`. The
     original per-image `alt_overrides` edit hit plan 005's own STOP condition (29
     real publisher alt="" figures across moesta-ch2/enns-qualifying/enns-value/
     enns-closing, past the ~15-entry ceiling); team-lead ruled that 29 filler
     descriptions would be worse than an honest gap, so plan 005 shipped a
     source-level `images.alt_policy: "waived"` (with `reason`) instead. The check
     honors a waiver in draft mode only (row PASS, detail names the waived sources);
     `--release` ignores it and fails `alt_text` on the same 29 offenders, correctly,
     since real alt text is a release requirement. corpus/vol2's four affected
     sources now carry the waiver with reason "publisher EPUB ships alt=''; real
     descriptions queued for the visual-QA iteration" — real authoring is iteration-3
     work via a vision-capable agent, not plan 005's.
3. Media-type mismatch: a JPEG served from a .png URL failed the EPUB media-type rule.
   Fix: sniff magic bytes on fetch, name and declare by sniffed type, record mismatches.
   - Status: DONE (plan 005). `sniff_image_type` in normalize.py, declared-vs-sniffed
     mismatch notes in fetch.py's `_classify_and_store`, `MEDIA_MIME` used for the
     packaged manifest entry in assemble.py. Covered by
     `SniffMismatchIntegrationTests` and eval E15.

## Second donation from the canon worker (its verify_vol2.py, 2026-08-29 15:35)

Nine more checks, each earned by a caught bug; port into `quoin check`:

1. Empty-ish alt, not just missing alt: publisher EPUBs ship alt="". Assert minimum
   length, exclude the cover. (Nine real figures shipped alt="" past a presence check.)
   - Status: DONE (plan 005). See item 2 of the first donation above; corpus/vol2's
     actual count is 29, not 9 — resolved with a draft-only source-level waiver
     rather than per-image overrides (STOP ruling), real authoring deferred to i3.
2. Ornamental image rejection: drop caps and section rules extract as real images and
   render as specks. Reject under 120px on either edge or under 2.5KB.
   - Status: DONE (plan 005, landed with the normalize.py media helpers before the
     check-row work). `is_ornamental()` in normalize.py; `OrnamentalTests` in
     tests/test_media.py.
3. Byte-identity of source bodies against the frozen extraction, re-hashed from the
   shipped archive per piece, never from builder memory.
   - Status: DONE (iteration 1, unchanged by plan 005). `word_counts_check` in
     check.py already re-reads each source's markup from the shipped zip archive
     (`archive.read(...)`) and recomputes the word count from that, never from an
     in-memory value carried over from the build.
4. Recall ordering: max(prompt spine index) < min(review spine index) per movement;
   prompt order equals source order volume-wide.
   - Status: DEFERRED (plan 005). Implemented as a forward-compatible `recall_ordering`
     check row that SKIPs: the manifest schema has no "prompt"/"review" item kind
     (movement items only support `ref: "(source|block):..."`), so there is nothing
     to order yet. The row is written to start enforcing automatically once such an
     item kind exists.
5. Intro-run adjacency for multi-author sources: check the contiguous intro run against
   declared author order, not single-page adjacency.
   - Status: DEFERRED (plan 005). Implemented as a forward-compatible
     `intro_run_adjacency` check row that SKIPs: sources have no `author` field
     (single brand-level attribution only), so there is no author order to check.
6. Orphan and unreferenced images, both directions (cover exempt).
   - Status: DONE (plan 005). `image_integrity` check row checks both directions
     under `OEBPS/text/media/`; the cover lives at `OEBPS/images/cover.png`, outside
     that scan, so it is exempt by construction.
7. Internal link resolution: normalize each href against its own document's directory
   and require a real zip entry (resolving against CWD produced 30 false failures).
   - Status: DONE (plan 005). `links` check row resolves every non-external href
     against `PurePosixPath(document).parent` via `os.path.normpath`, never CWD.
8. Blank-page detection by ink ratio: render each spine doc, flag under 0.2% dark
   pixels; catches a stylesheet that failed to load.
   - Status: OUT OF SCOPE for plan 005 (explicitly deferred in the plan's own Scope
     section to the visual-QA iteration; needs a browser/rendering dependency this
     plan does not add).
9. Media-type sniffing by magic bytes (already planned; confirmed by their JPEG-at-.png).
   - Status: DONE (plan 005). Same mechanism as item 3 of the first donation above.

Process check for the two-pass tooling: the meaning-preservation comparator needs a
declaration parser (reasoning inline, multiple tokens per reason) and
possessive/inflection normalization in the name set; without them it produced 12 false
failures, all declared edits.

## Carry-over from iteration 1 shortcuts

- Web/file sources currently drop remote images entirely; I2 downloads them at fetch
  time (recorded in the rights ledger as snapshot), embeds them namespaced, and
  regenerates verbatim word counts unaffected.
- EPUB sources copy chapter media; verify refs after packaging.
- Section-level locators: canon scoped Enns to Objective+Framework+Summary subsections
  inside chapter files. I2/I3 adds `section_locator` (heading-anchored contiguous
  ranges inside a content file) with extraction notes rendered on the piece's first
  page, mirroring what the canon worker shipped by hand.
- Device profiles: CSS verified on Apple Books, KOReader, Kobo (kepub output), BOOX;
  cover sizes; color vs grayscale image handling.
