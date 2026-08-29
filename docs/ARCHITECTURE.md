# quoin architecture

Start with the public [README](../README.md) for installation, the quick start, and CLI use.

quoin ("coin"): a deterministic book compiler with agent-shaped sockets. Agents set the
type; quoin locks the book. This repo is the Python reference implementation whose JSON
contracts must stabilize before any Rust port.

## The two layers

1. **Deterministic compiler.** manifest → fetch/normalize sources → assemble EPUB3 →
   check. Byte-identical output from identical inputs. Every stage timed, hashed,
   content-addressed-cached, written to build-record.json. The compiler never calls a
   model.
2. **Agent layer.** The manifest declares authored-block slots (intros, interludes,
   title deck, cover copy). `quoin blocks --missing` emits machine-readable work orders
   (brief + evidence paths + output schema + gates). Any agent harness, or a human with
   an editor, writes `blocks/*.json`. `quoin check` is the referee.

The wedge is the seam itself: skills/guidance for agents and a CLI that enforce each
other. The guidance pack (AGENTS.md, per-kind briefs, the editorial gates) ships in the
scaffold, so `quoin init` makes any agent session productive with zero orchestration
framework.

## Editorial system (from the aneym volume canon, generalized)

- Source prose is never touched. Verbatim word counts are a build gate.
- Two-pass writing: draft for meaning, style-pass separately; the style pass records a
  findings diff sidecar. A clean mechanical scan is not a pass.
- Grounding: every factual claim in an authored block carries a quoted evidence line.
- Stage test: material must serve the volume's governing question now; good-but-later
  goes to reserve.
- Rights ledger per source: access, snapshot, extraction, reproduction, distribution.
  Draft gates and release gates differ.

## Iteration plan (owner-directed, 2026-08-29)

Rebuild "aneym vol. 2: the first paid deployment" with the CLI five times, running the
eval suite each time and folding an /improve review between iterations.

- **I1** Port the proven speed-lab pipeline into the `quoin` package; evals green on the
  sample corpus; first vol-2 build.
- **I2** Media and rendering: cover images, in-book images, color handling, CSS that
  renders correctly across Apple Books, KOReader, Kobo, Kindle-adjacent, BOOX.
- **I3** Ingestion robustness: article extraction quality, chapter-locator verification
  reports, embed/iframe/footnote handling, kepub output profile.
- **I4** DX: error messages, `quoin doctor`, work-order ergonomics, docs, the skill pack.
- **I5** Hardening: eval suite completeness, release gates, final report.

## Layout

    quoin/            the package (CLI: python -m quoin / console script)
    docs/             architecture, specs, iteration reports
    corpus/vol2/      the vol-2 eval corpus (fetched raw sources, locator maps)
    evals/            eval harness + per-iteration results JSON
    scaffold/         what `quoin init` copies: AGENTS.md, briefs, book.toml template
