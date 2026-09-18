# Plan 008: Lint, typecheck, and CI wiring

> **Executor instructions**: Follow step by step; verify each step. STOP conditions
> are binding. Update `plans/README.md` when done.
>
> **Drift check (run first)**: `git diff --stat 0203c4b..HEAD -- pyproject.toml`

## Status

- **Priority**: P2 · **Effort**: M · **Risk**: LOW
- **Depends on**: 001 (tests/ exists)
- **Category**: dx
- **Planned at**: commit `0203c4b`, 2026-08-29

## Why this matters

A typed Python codebase with zero static checks: no lint, no typecheck, no formatter
config, no CI. Contributors (and executor agents) get their first feedback only from
the end-to-end eval. Cheap static gates catch the class of bug (wrong attribute,
unreachable branch, shadowed name) that otherwise costs a full build cycle.

## Current state

- `pyproject.toml` — packaging + Pillow only; no tool config sections.
- No `.github/`, no pre-commit config. Repo hosts locally (no remote yet); CI file
  still lands now so publishing later is turnkey.

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Lint | `python3 -m ruff check .` | exit 0 |
| Format check | `python3 -m ruff format --check .` | exit 0 |
| Typecheck | `python3 -m mypy quoin` | exit 0 |
| Tests | `python3 -m unittest discover -s tests` | pass |
| Evals | `python3 evals/run_evals.py --iteration 2` | `all_pass: true` |

## Scope

**In scope**: `pyproject.toml` ([tool.ruff], [tool.mypy], dev extra
`[project.optional-dependencies] dev = ["ruff", "mypy"]`), `.github/workflows/ci.yml`,
mechanical fixes across `quoin/` and `evals/` that lint/typecheck demand,
`docs/` only for a one-line dev-setup note.
**Out of scope**: behavior changes (if a mypy fix would change runtime behavior,
STOP), formatting churn beyond `ruff format` output, adding runtime dependencies.

## Steps

1. Add ruff (line-length 100, default rules + isort) and mypy (python_version 3.12,
   `strict = false` to start, `disallow_untyped_defs = false`, escalate later) config;
   add the dev extra. Install with `python3 -m pip install --user ruff mypy` if
   missing (report if the environment forbids installs — STOP condition).
2. Run `ruff format .` once, then fix `ruff check` and `mypy quoin` findings
   mechanically. Each fix that is not purely mechanical gets one closeout line.
3. `ci.yml`: matrix python 3.12/3.13, steps: install `-e .[dev]`, ruff check, ruff
   format --check, mypy, unittest. The eval job runs separately, allowed to skip when
   java/EPUBCheck are absent (detect and `exit 0` with a notice) so CI stays honest
   off this machine until plan 003's discovery lands everywhere.
4. Full local gate: all five commands above green.

## Done criteria

- [ ] All five commands green locally
- [ ] `git log` shows one formatting commit separate from fix commits
- [ ] No behavior change: evals `all_pass: true` and corpus/vol2 check still PASS
- [ ] `plans/README.md` updated

## STOP conditions

- The environment blocks installing ruff/mypy.
- A typecheck fix requires changing runtime logic (report the site instead).

## Maintenance notes

Escalate mypy strictness one module at a time in later iterations; normalize.py first
since it carries the fidelity contract.
