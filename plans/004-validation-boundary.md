# Plan 004: One validation boundary with actionable errors

> **Executor instructions**: Follow step by step; verify each step. On any STOP
> condition, stop and report. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- quoin/manifest.py quoin/cli.py`
> On mismatch with the excerpts below, STOP.

## Status

- **Priority**: P1 · **Effort**: M · **Risk**: MED (stricter validation may reject
  previously-accepted sloppy manifests; that is intended, but the real corpus must
  stay green)
- **Depends on**: none (001 recommended first for the tests/ dir)
- **Category**: dx + tests
- **Planned at**: commit `0203c4b`, 2026-08-29

## Why this matters

`manifest.load` checks only file presence and top-level keys, so a typo in a nested
field surfaces later as a bare `KeyError` in whatever stage consumed it, and the
packaged JSON schemas (`quoin/schemas/*.schema.json`) are decoration nobody enforces.
The CLI then collapses everything to `quoin <cmd> failed: <exc>`. For a tool whose
users are agents, precise machine-readable complaints are the difference between
self-correction and a stuck loop.

## Current state

- `quoin/manifest.py:16-30` (verified): presence check → tomllib/json load →
  top-level `required` set check → `format_version` check. Nothing nested.
- `quoin/cli.py:70-72` (verified):

      except Exception as exc:
          print(f"quoin {args.command} failed: {exc}", file=sys.stderr)
          return 1

- Reproduced UX: `quoin fetch` in an empty dir prints
  `quoin fetch failed: book.toml and manifest.json are required` — does not say "this
  is not a book directory" or suggest `quoin init`.
- `quoin/schemas/manifest.schema.json` and `block.schema.json` exist and are packaged
  (`pyproject.toml [tool.setuptools.package-data]`), unused at runtime.
- Constraint: stdlib only — do NOT add the `jsonschema` package.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Unit tests | `python3 -m unittest discover -s tests` | pass |
| Evals | `python3 evals/run_evals.py --iteration 2` | `all_pass: true` |
| Corpus | `cd corpus/vol2 && PYTHONPATH=.. python3 -m quoin fetch` | succeeds |

## Scope

**In scope**: `quoin/manifest.py`, `quoin/cli.py`, `quoin/blocks.py` (block-file
validation reuse), `tests/test_manifest.py` (create).
**Out of scope**: schema FILE contents (extend only if a field the code reads is
missing from the schema — then update both together), `corpus/vol2/manifest.json`
(must pass unmodified; if it does not, STOP).

## Steps

### Step 1: Structural validator

Add to `manifest.py` a small stdlib walker `validate(manifest) -> list[str]` driven
by the packaged `manifest.schema.json` subset actually used: types, required keys,
enums (`type` in web|epub|file; `kind` in title_deck|introduction|interlude|cover_copy),
and referential integrity (every `movements[].items[].ref` names an existing
`source:<id>`/`block:<id>`; no duplicate ids; every `epub` source has
`chapter_locator`; every `web` source has a `locator` URL). Each complaint is one
line: `manifest.json: sources[2].chapter_locator must be a list of strings`.
`load()` raises `ManifestError` with all complaints joined by newlines.

**Verify**: `python3 -m unittest tests.test_manifest -v` (written in step 3) → pass.

### Step 2: Error taxonomy in the CLI

- Not a book dir (both files absent): message says exactly that and suggests
  `quoin init <dir>` or cd-ing into a book directory.
- Malformed TOML/JSON: name the file and re-raise the parser's line/column info.
- `ManifestError`/`QuoinError`: print message only, exit 1 (no traceback).
- Any OTHER exception: print `quoin <cmd> crashed (bug): <exc>` plus the last 3
  traceback frames, exit 2 — so agent callers can distinguish user error (1) from
  compiler bug (2).

**Verify**: empty dir → `python3 -m quoin fetch` mentions `quoin init`, exit 1;
`echo '{' > manifest.json; touch book.toml` → message names manifest.json with a
position, exit 1.

### Step 3: Tests

`tests/test_manifest.py`: malformed TOML, malformed JSON, each missing top-level
field, wrong nested types (sources as dict, chapter_locator as string), unknown ref,
duplicate source id, epub without chapter_locator, valid manifest passes (use a
trimmed copy of the furniture fixture manifest inline). Assert exact one-line
complaint substrings and exit codes via `subprocess` for the CLI taxonomy cases.

**Verify**: `python3 -m unittest discover -s tests` → all pass.

### Step 4: Corpus and evals stay green

**Verify**: corpus fetch command above succeeds; evals `all_pass: true`.

## Done criteria

- [ ] All commands in "Commands you will need" green
- [ ] Empty-dir UX mentions `quoin init`; crash vs user-error exit codes differ (2 vs 1)
- [ ] `corpus/vol2/manifest.json` passes validation UNMODIFIED
- [ ] `plans/README.md` updated

## STOP conditions

- `corpus/vol2/manifest.json` fails a validation rule you believe is correct: report
  the rule and the manifest line instead of loosening the rule or editing the corpus.
- Enforcing a schema field reveals the schema file disagrees with what code consumes.

## Maintenance notes

`blocks.py` should call the same validator family for block JSON (plan 006 tests it).
When manifest format_version 2 arrives, version-gate the walker rather than mutating
v1 rules.
