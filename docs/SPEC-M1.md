# M1 spec: the quoin package, iteration 1

Deliverable: a working `quoin` CLI in this repo, ported and generalized from the proven
prototype at `/Users/aneyman/artifacts/reading-packets/speed-lab/speedlab_build.py`
(read it first; its stage/cache/build-record/check structure is the model). Python
3.12+, stdlib + Pillow only. EPUBCheck jar is external: config key `epubcheck_jar` in
book.toml, defaulting to
`/Users/aneyman/artifacts/reading-packets/build/epubcheck-5.3.0/epubcheck.jar`.

## Package

`pyproject.toml` with console script `quoin`; also runnable as `python -m quoin`.
Modules kept small: `cli.py`, `manifest.py`, `fetch.py`, `normalize.py`, `blocks.py`,
`assemble.py`, `check.py`, `record.py`, `scaffold.py`. No network libraries: urllib.

## Commands

- `quoin init <dir>` — scaffold: `book.toml`, `manifest.json` (commented example),
  `blocks/`, `sources/`, and the agents pack copied from `scaffold/` (AGENTS.md +
  `briefs/<kind>.md`). Idempotent, refuses to overwrite non-empty files.
- `quoin fetch` — resolve every manifest source:
  - `type: web`: GET with recorded UA, save raw bytes, record url/date/bytes/sha256/
    http_status in `sources/records.json`, then extract the article body to
    `sources/normalized/<id>.xhtml` (strip nav/header/footer/script/subscribe/comment
    furniture; never alter article text nodes). Already-fetched raw files are reused
    (content-addressed) — support `--offline` which errors on any missing raw file.
  - `type: epub`: local path + `chapter_locator` (explicit content-file list or glob,
    in spine order); concatenate verbatim to `sources/normalized/<id>.xhtml`; images
    referenced by the chapter are copied to `sources/normalized/<id>_media/` and their
    refs rewritten relatively (do NOT drop images in quoin — that was a sample-only
    shortcut).
  - Record per-source word counts; later stages must reproduce them exactly.
- `quoin blocks [--missing] [--json]` — list block slots from the manifest with status
  (present/missing/invalid). `--json` emits work orders: `{block_id, kind, brief,
  evidence, schema, gates, output_path}`. Brief text comes from the manifest block
  declaration plus the per-kind brief in the agents pack.
- `quoin build [--draft]` — assemble EPUB3 to `out/<slug>.epub`:
  cover (Pillow typographic default from title/brand; or `cover_image` path from
  book.toml), title page, then movements exactly as the manifest orders items
  (block refs and source refs interleaved), attribution page generated from source
  records. Missing blocks: visible TODO placeholder pages in `--draft`, hard error
  otherwise. Deterministic zip (fixed timestamps, mimetype first, stored). Stages
  timed + hashed into `out/build-record.json` with cache in `out/cache.json`.
- `quoin check [--release]` — epubcheck (0/0/0 required), mimetype/spine assertions,
  packaged-EPUB word counts equal fetch records, contamination scan on source pieces,
  privacy scan (terms list from book.toml `[privacy] forbidden_terms`), determinism
  double-build compare. `--release` additionally requires: no placeholders, every
  authored block has a `.stylepass.json` sidecar, every claims[] entry non-empty.
  Machine-readable: `out/check-results.json` plus human table; exit non-zero on failure.
- `quoin doctor` — verify python/Pillow/java/epubcheck and print versions.

## Contracts (write these as JSON Schema files in `quoin/schemas/`, version field `1`)

- `manifest.schema.json`: `{format_version, slug, title, brand, language,
  governing_question, privacy:{forbidden_terms[]}, sources:[{id, type: web|epub|file,
  locator, chapter_locator?, rights?{...}}], movements:[{id, title, items:[{ref:
  "source:<id>"|"block:<id>"}]}], blocks:[{id, kind: title_deck|introduction|interlude|
  cover_copy, brief, evidence[]}]}`
- `block.schema.json`: `{block_id, kind, title, html}` (+ optional sidecar
  `<id>.stylepass.json`: `{block_id, changed, findings[], claims:[{claim, support}]}`).
- `record.schema.json` for build-record.json.

## Scaffold agents pack (`scaffold/`)

- `AGENTS.md`: the loop for an agent inside a quoin book dir: `quoin blocks --missing
  --json` → for each work order, draft-for-meaning then style-pass-separately (two
  different agent invocations when the harness allows), write the block JSON + stylepass
  sidecar → `quoin check`. Carries the editorial contract: plain concrete prose, no em
  dashes, no puffery, claims quote evidence lines, read-aloud judgment before declaring
  a block clean, source prose untouchable.
- `briefs/introduction.md`, `briefs/interlude.md`, `briefs/title_deck.md`: the per-kind
  contracts (adapted from the aneym rules: an introduction says who the person is and
  why the piece is worth reading, never summarizes the piece, never lists prestige
  affiliations, surname when pronouns unstated; an interlude orients a movement and
  never answers its question).

## Eval harness

`evals/run_evals.py --iteration N`: copies `evals/fixtures/sample/` (build it from the
speed-lab inputs: the LEGO essay raw HTML from `corpus/vol2/raw/kanekar-lego-raw.html`
+ Moesta ch2 from the library EPUB) into a temp dir, then runs the full loop offline
and asserts:

  E1 determinism (two builds byte-identical)      E6 contamination scan clean
  E2 epubcheck 0/0/0                              E7 privacy scan clean
  E3 verbatim word counts                         E8 work orders validate against schema
  E4 draft build succeeds with blocks missing     E9 cold build < 10 s
  E5 warm rebuild cache hits                      E10 `quoin doctor` exit 0

Writes `evals/results-i<N>.json` `{iteration, timestamp, evals:{id:{pass, detail,
ms}}, all_pass}`. M1 acceptance: `python3 evals/run_evals.py --iteration 1` all green,
plus `pip install -e .` making `quoin` invocable.

## Rules

- Read the prototype; keep its proven check logic, generalize paths/config.
- Never modify anything under `/Users/aneyman/artifacts/` or the Calibre library.
- Deterministic everywhere: no wall-clock in output except ISO timestamps inside
  build-record (excluded from determinism compare).
- Commit in THIS repo only, small commits per module, messages `m1: <what>`.
- Any prose you write (docs, briefs, errors): plain concrete language, no em dashes,
  no promotional adjectives, no "not just X but Y".
