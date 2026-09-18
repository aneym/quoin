# Plan 003: Portable defaults: font and EPUBCheck discovery

> **Executor instructions**: Follow step by step; verify each step. On any STOP
> condition, stop and report. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- quoin/assemble.py quoin/check.py quoin/scaffold.py scaffold/`
> On mismatch with the excerpts below, STOP.

## Status

- **Priority**: P1 · **Effort**: M · **Risk**: MED (cover bytes change once; EPUB SHA
  in existing build records will differ after this lands — that is expected)
- **Depends on**: none
- **Category**: tech-debt
- **Planned at**: commit `0203c4b`, 2026-08-29

## Why this matters

Two machine-specific absolute paths make the compiler unusable off this Mac and
undermine the determinism story. The cover font is read from the host OS, so the same
inputs produce different bytes on different machines, and `quoin init` bakes a private
`/Users/aneyman/...` EPUBCheck path into every new book. Fixing both is a prerequisite
for the open-source direction and for honest cross-machine determinism.

## Current state

- `quoin/assemble.py:31-38` (verified excerpt):

      def _cover(title: str, brand: str) -> bytes:
          image = Image.new("RGB", (1600, 2560), "#171a1d")
          draw = ImageDraw.Draw(image)
          font_path = "/System/Library/Fonts/Helvetica.ttc"
          title_font = ImageFont.truetype(font_path, 116, index=0)

- `quoin/check.py:21-22` (verified excerpt):

      def epubcheck_jar(book: dict) -> Path:
          return Path(book.get("epubcheck_jar", "/Users/aneyman/artifacts/reading-packets/build/epubcheck-5.3.0/epubcheck-5.3.0/epubcheck.jar"))

- `scaffold/book.toml` — one line containing that same private jar path; copied
  verbatim by `quoin init`.
- Build records hash stage inputs; the font file is currently NOT a recorded input.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Evals | `python3 evals/run_evals.py --iteration 2` | `all_pass: true` |
| Unit tests | `python3 -m unittest discover -s tests` | pass |
| Real corpus | `cd corpus/vol2 && PYTHONPATH=.. python3 -m quoin build --draft && python3 -m quoin check` | all check rows PASS |
| Doctor | in a book dir: `python3 -m quoin doctor` | names font + jar resolution |

## Scope

**In scope**: `quoin/assemble.py`, `quoin/check.py`, `quoin/scaffold.py`,
`scaffold/book.toml`, `quoin/record.py` (font hash as recorded input), `tests/test_portability.py` (create), `evals/` only if a path assumption leaks there,
`quoin/errors.py` (create: `class QuoinError(Exception)` and `class ManifestError(QuoinError)`),
plus the one-line changes in `quoin/manifest.py` and any importer needed to re-home
the existing `ManifestError` onto that shared base (coordinator ruling, 2026-08-29;
this errors module is the taxonomy plan 004 builds on).
**Out of scope**: `corpus/vol2/book.toml` edits beyond what step 4 says; any CSS or
cover layout redesign; bundling a font binary into git (licensing review is not in
this plan's scope — use resolution order instead).

## Steps

### Step 1: Font resolution order

In `assemble.py`, replace the hardcoded path with a resolver:

1. `book.toml` key `cover_font` (absolute path) if set;
2. env `QUOIN_COVER_FONT`;
3. first hit in a small candidate list covering macOS
   (`/System/Library/Fonts/Helvetica.ttc`), common Linux
   (`/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`), and Windows
   (`C:/Windows/Fonts/arial.ttf`);
4. otherwise raise a `QuoinError` naming the key, the env var, and one download hint.

Hash the resolved font file into the assemble stage's `input_sha256s` as key
`cover_font`, so determinism claims are scoped to identical font inputs and a font
swap invalidates the cache instead of silently changing bytes.

**Verify**: `cd corpus/vol2 && python3 -m quoin build --draft` (PYTHONPATH set) →
build succeeds; `python3 -c "import json;print('cover_font' in json.load(open('out/build-record.json'))['stages']['assemble']['input_sha256s'])"` → `True`.

### Step 2: EPUBCheck resolution order

In `check.py`: `book.toml` `epubcheck_jar` → env `QUOIN_EPUBCHECK_JAR` → `shutil.which("epubcheck")`
(invoke the wrapper instead of `java -jar` when found) → error naming all three with
install guidance. Remove the private default entirely.

**Verify**: in a temp book dir with no `epubcheck_jar` key and the env var unset and
no `epubcheck` on PATH, `python3 -m quoin check` → exit 1 with a message naming
`epubcheck_jar`, `QUOIN_EPUBCHECK_JAR`, and `which epubcheck`.

### Step 3: Scaffold and doctor

`scaffold/book.toml`: replace the private path with a commented example
(`# epubcheck_jar = "/path/to/epubcheck.jar"`). `doctor` prints which font and which
jar resolved and via which of the three routes, or the remediation line.

**Verify**: `python3 -m quoin init /tmp/qi3 && grep -c aneyman /tmp/qi3/book.toml` → `0`.

### Step 4: Keep the real corpus green

`corpus/vol2/book.toml` already pins `epubcheck_jar` explicitly; leave it. Set
nothing else. Run the full corpus chain.

**Verify**: `cd corpus/vol2 && python3 -m quoin build --draft && python3 -m quoin check` → all rows PASS.

## Test plan

`tests/test_portability.py`: unit-test both resolvers with monkeypatched candidates
(tmp files standing in for fonts/jars): config wins over env, env over discovery,
error message names all routes. Model the file layout after `tests/test_normalize.py`
from plan 001.

## Done criteria

- [ ] `grep -rn "aneyman" quoin/ scaffold/` → no matches
- [ ] `grep -rn "Helvetica.ttc" quoin/ | grep -v candidate` → no hardcoded sole path
- [ ] evals `all_pass: true`; corpus/vol2 check all PASS
- [ ] unit tests pass; `plans/README.md` updated

## STOP conditions

- Pillow cannot load any candidate font on this machine (would break the only
  working environment) — report before changing defaults.
- The `epubcheck` PATH wrapper produces output the parser cannot read — keep jar mode
  and report.

## Maintenance notes

When a bundled-font decision is made later (licensing), it slots in as resolution
step 2.5 without changing this order. Plan 009's README documents this resolution
order; keep them in sync.
