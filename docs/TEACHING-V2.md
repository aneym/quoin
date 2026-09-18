# Version 2 teaching content

Quoin 0.3 accepts both manifest versions. Version 1 retains its existing content kinds and package bytes. Version 2 adds `lesson`, `exercise`, `answer`, and `debrief` without changing what an introduction or interlude means. No old edition is migrated automatically.

Each version-2 block declares `editorial_ref`, a stable locator for its canonical editorial record. The edition release pipeline must resolve that locator and verify writing, rights, source and review evidence. Quoin cannot infer editorial approval from a nonempty locator.

Exercises declare a safe `recall_group`. Answers declare the same group and an `answers` list of exercise ids. Every exercise has exactly one answer, and every exercise in a group precedes every answer in that group. Each block is referenced exactly once. Each becomes its own XHTML spine document. Teaching headings are compiler furniture; authored HTML stays verbatim.

Optional `contributors` contains person ids on the first and later appearances. An introduction declares `introduces`. Exactly one contiguous introduction run must immediately precede each first appearance. Duplicate or unused declared introductions fail. Declarations must cover actual mentions; the editorial checker must audit this against the prose.

Blocks may declare `figures`: `{id,path,sha256,alt,caption}`. IDs are globally unique. Paths stay inside the book, including after symlink resolution. PNG/JPEG bytes must decode, match the extension and match the declared hash. The compiler packages them, adds alt text and captions, and includes file bytes in the cache key. Reflowable CSS scales figures and wraps code. Inline images, scripts, forms, hidden answers and style-based reveals are refused in version-2 authored HTML. Version 2 requires an explicit designed PNG cover. Optional `series` produces EPUB collection metadata.

Migration is deliberately explicit and idempotent: create a NEW book directory, copy approved source and block bytes, set `format_version` to 2, add `editorial_ref` to each block and contributor/recall/figure declarations where applicable, then validate before building. Reapplying these assignments has no effect. Never run this recipe on a released edition. Existing version-1 files need no edits.

Run `python -m unittest tests.test_teaching -v` and `python -m unittest discover -s tests -q`. Teaching tests build actual ZIP/EPUB output, verify source byte compatibility, ordering failures, cover requirement, local-media fidelity and cache invalidation. Full EPUBCheck and two-reader visual QA remain required on release bytes. A generated test fixture is not release evidence for a real book.
