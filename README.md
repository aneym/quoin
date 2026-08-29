# Quoin

Quoin compiles source material and short authored passages into an EPUB 3 book. Its deterministic compiler fetches, normalizes, assembles, and checks the book without calling a language model. A separate agent layer describes each passage through JSON work orders, so a person or any agent harness can fill the declared slots.

## Requirements

- Python 3.12 or newer
- Pillow 10 or newer, installed with the package
- A TrueType or OpenType font for generated covers
- Java 11 or newer
- EPUBCheck from the [official releases](https://github.com/w3c/epubcheck/releases)

After you download EPUBCheck, set its path in `book.toml`:

```toml
epubcheck_jar = "/path/to/epubcheck.jar"
```

You can instead export the path for your shell:

```sh
export QUOIN_EPUBCHECK_JAR=/path/to/epubcheck.jar
```

Quoin finds a cover font in this order:

1. `cover_font` in `book.toml`
2. `QUOIN_COVER_FONT`
3. common system locations for DejaVu Sans, Helvetica, Arial, or Liberation Sans

Quoin finds EPUBCheck in this order:

1. `epubcheck_jar` in `book.toml`
2. `QUOIN_EPUBCHECK_JAR`
3. an `epubcheck` command on `PATH`

Run `quoin doctor` inside a book directory to see which tools and paths Quoin resolved.

## Install

Clone this repository, then install it in editable mode:

```sh
python3 -m pip install -e .
```

This adds the `quoin` command. You can also run the CLI as `python3 -m quoin` when the package is on `PYTHONPATH`.

## Quick start

The example uses Project Gutenberg's public-domain edition of the United States Declaration of Independence.

```sh
quoin init qsr
cd qsr
cat > manifest.json <<'JSON'
{
  "format_version": 1,
  "slug": "declaration-sample",
  "title": "Declaration sample",
  "brand": "Quoin",
  "language": "en",
  "governing_question": "What claims does the declaration make?",
  "privacy": {"forbidden_terms": []},
  "sources": [
    {
      "id": "declaration",
      "type": "web",
      "title": "The Declaration of Independence",
      "locator": "https://www.gutenberg.org/files/1/1-h/1-h.htm",
      "rights": {"access": "public domain"}
    }
  ],
  "movements": [
    {
      "id": "one",
      "title": "The text",
      "items": [
        {"ref": "block:introduction"},
        {"ref": "source:declaration"}
      ]
    }
  ],
  "blocks": [
    {
      "id": "introduction",
      "kind": "introduction",
      "brief": "Introduce the document and the question it asks.",
      "evidence": ["sources/normalized/declaration.xhtml"]
    }
  ]
}
JSON
quoin fetch
quoin blocks --missing --json
quoin build --draft
quoin check
```

The draft build writes `out/declaration-sample.epub`. It contains a placeholder for the missing introduction. The final command checks package structure, source word counts, privacy terms, EPUBCheck output, and byte-for-byte determinism.

After the first fetch, `quoin fetch --offline` rebuilds normalized sources from saved raw input without a network request.

## The agent loop

`quoin blocks --missing --json` emits one work order for each unfinished block. A work order includes the brief, evidence paths, output schemas, examples, file destinations, and gates.

Write the authored passage to `blocks/<block-id>.json`. Write the style review to `blocks/<block-id>.stylepass.json`. The scaffolded `AGENTS.md` and files under `briefs/` define the full contract.

Use `quoin check` while drafting. Use `quoin build` without `--draft`, then `quoin check --release`, before distribution. Release checks reject placeholders, missing style-review sidecars, and unsupported claims.

## Build guarantees

Quoin keeps normalized source prose separate from authored blocks. The checker compares packaged source word counts with the fetch records, scans for known page furniture, and checks forbidden privacy terms.

Identical inputs produce a byte-identical EPUB. Each build records stage timing, input hashes, and cache hits in `out/build-record.json`. Changes to the manifest, source records, normalized files, authored blocks, cover input, compiler version, or build mode invalidate the relevant cache entry.

## Rights records

Each source may carry a `rights` object in `manifest.json`. Fetch records preserve that declaration beside the source hash and stored path. Quoin records the stated rights; it does not grant rights or turn private material into distributable material.

Draft builds can include material that is valid for private review. Release checks apply the stricter publication gates. The publisher remains responsible for permission to reproduce and distribute every source.

License: not yet chosen.

Repository: not yet published.

## Troubleshooting

Start with:

```sh
quoin doctor
```

A failing `epubcheck` row means EPUBCheck reported an error or could not be found. Set `epubcheck_jar` or `QUOIN_EPUBCHECK_JAR`, or install an `epubcheck` command on `PATH`.

A failing `word_counts` row means packaged source text differs from the recorded normalized source. Run `quoin fetch`, rebuild, and inspect the named source.

A failing `contamination` row names navigation, subscription, or other page furniture that reached the book. Fix the source extraction before release.

A failing `determinism` row means the rebuilt EPUB has a different hash. Inspect `out/build-record.json` and check whether every build input is declared.

## Development

Run the unit tests and iteration evals from the repository root:

```sh
python3 -m unittest discover -s tests
python3 evals/run_evals.py --iteration 2
```

See [the architecture notes](docs/ARCHITECTURE.md) for the compiler layers, repository layout, and roadmap.
