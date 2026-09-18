# Plan 010: Safe ids and complete cache keys

> **Executor instructions**: Follow step by step; verify each step. STOP conditions
> are binding. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- quoin/manifest.py quoin/fetch.py quoin/assemble.py`
> Plan 004 lands before this and reshapes manifest validation; build on its
> `validate()` walker, and re-read live code where these excerpts have drifted.

## Status

- **Priority**: P1 · **Effort**: S · **Risk**: LOW
- **Depends on**: 004
- **Category**: security + bug
- **Planned at**: commit `0203c4b`, 2026-08-29 (from the correctness/security audit)

## Why this matters

Source and block ids from `manifest.json` are used verbatim as path components in at
least six sites (fetch raw paths, normalized paths, block file paths, packaged media
dirs). An id like `../../../../tmp/x` makes `quoin fetch` write downloaded bytes to an
attacker-chosen path, or embed an arbitrary local file into the book. Anyone building
a shared or downloaded manifest is exposed. Separately, the assemble cache key omits
two real inputs: the `cover_image` file (read at `assemble.py:104-105`, absent from
the `inputs` list at `assemble.py:127`) and the compiler's own version, so a cover
swap or a quoin upgrade can serve a stale EPUB as a cache hit.

## Current state (verified at 0203c4b)

- `quoin/fetch.py:18-20` — `_raw_path` interpolates `source['id']` into a path.
- `quoin/fetch.py:35-37` — writes network bytes to a path containing the raw id.
- `quoin/assemble.py:104-106` — reads `book["cover_image"]` relative to root, not
  validated to stay inside root, and packages it.
- `quoin/assemble.py:125-127` — `inputs` hash list: book.toml, manifest.json,
  records.json, normalized sources, block files, draft flag. No cover_image, no code
  version.

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Unit tests | `python3 -m unittest discover -s tests` | pass |
| Evals | `python3 evals/run_evals.py --iteration 2` | `all_pass: true` |
| Corpus | `cd corpus/vol2 && PYTHONPATH=.. python3 -m quoin build --draft && python3 -m quoin check` | all PASS |

## Scope

**In scope**: `quoin/manifest.py` (extend plan 004's validator), `quoin/assemble.py`
(cache inputs; cover_image containment), `quoin/fetch.py` (containment assertion as
defense in depth; timeout/size cap), `quoin/check.py` (step 2c per-check error
isolation), `quoin/__init__.py` (a `__version__` string if absent), `pyproject.toml`
(version bump to 0.2.0 only), `tests/test_manifest.py` and `tests/test_portability.py`
extensions. (Scope amended by coordinator 2026-08-29 to match steps 2c and 3.)
**Out of scope**: URL scheme allow-listing and fetch size limits (raise as a finding
if you notice them missing, do not implement here), `corpus/`.

## Steps

1. Id charset gate in the manifest validator: every `sources[].id` and `blocks[].id`
   must match `^[a-z0-9][a-z0-9_-]{0,63}$`; complaint names the offending id and
   index. Same gate for `slug`.
   **Verify**: unit test with `"id": "../evil"` → ManifestError naming `sources[0].id`.
2. Containment helper `inside(root, path)` (resolve and require `root` as ancestor);
   apply to `cover_image`, `raw_file`, and `file`-type locators when resolving.
   IMPORTANT nuance (verified against the real corpus): `epub`-type locators MUST
   remain allowed to be absolute paths outside the book dir — pointing at owned
   library books is the primary use case (`corpus/vol2` points at
   `/Volumes/Media500/...`). Instead of confining them, record each external epub
   locator's resolved path and sha256 in `sources/records.json` as a declared
   external input, and fix the `file` branch's ordering bug at `fetch.py:104-105`
   (currently `read_bytes()` runs before the `relative_to(root)` check, so escape
   attempts crash after the read instead of being prevented).
   **Verify**: unit test with `cover_image = "../../x.png"` → error naming the key;
   unit test with a `file` locator of `"../outside.html"` → refused BEFORE any read;
   corpus/vol2 fetch (absolute epub locators) still succeeds.
2b. Fetch hardening (audit CORRECTNESS-04): `urllib.request.urlopen(request,
   timeout=30)` at `fetch.py:32`, and stream-read with a 20 MB cap raising a named
   error beyond it.
   **Verify**: unit test monkeypatching urlopen confirms timeout is passed.
2c. Check robustness (audit CORRECTNESS-05, verified at `check.py:51-80`): narrow the
   single try/except so each check row fails independently with its own detail, and
   add a validator rule that every source id is referenced by exactly one movement
   item (unreferenced source currently raises KeyError at `check.py:64` and collapses
   all package checks into one "package" FAIL row).
   **Verify**: unit test with an unreferenced source → ManifestError at load, and a
   corrupted-zip check run still reports per-row results for rows it could compute.
3. Cache-key completeness: add to the assemble `inputs` dict the resolved
   cover_image file hash (when set) and `quoin.__version__` (add `__version__ =
   "0.2.0"` to `quoin/__init__.py`, matching pyproject, and bump pyproject to 0.2.0).
   **Verify**: build corpus twice → second is cache_hit; touch a temp book's cover
   image → cache miss; assert via a unit test on the inputs-building function if it
   is factored out, else via the eval-style temp book.
4. Full regression: three command groups above.

## Done criteria

- [ ] Traversal ids and escaping cover_image rejected with named-field errors
- [ ] `python3 -c "import quoin; print(quoin.__version__)"` → `0.2.0`
- [ ] Corpus warm rebuild still cache-hits; cover-image change misses
- [ ] All three command groups green; `plans/README.md` updated

## STOP conditions

- Plan 004's validator did not land or has a different extension point than expected.
- Any real corpus id fails the charset (report; do not widen the charset silently).

## Maintenance notes

When plan 005 adds snapshot media, its per-image paths must go through the same
containment helper, and new cache-relevant inputs (fonts landed in 003, media in 005)
must be added to the inputs dict in the same commit that reads them.
