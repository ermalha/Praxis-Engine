# Praxis stability + versioning policy

Effective from **v1.0.0** (2026-05-24).

Praxis follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).
This document spells out **what counts as public** (and therefore
covered by SemVer guarantees), what doesn't, and how deprecations
work.

---

## What's public

The following surfaces are stable. Breaking changes here require a
**major** version bump and a deprecation window (see below).

| Surface | Stability guarantee |
|---|---|
| **CLI subcommands + flags** | `praxis ask`, `praxis chat`, `praxis check`, `praxis elicit`, `praxis artifact generate`, `praxis init`, `praxis status`, `praxis wake`, `praxis run`, `praxis tui`, `praxis doctor`, `praxis export`, `praxis engagement <entity> *`, `praxis queue *`, `praxis profile *` and their flags. Removing a flag or subcommand is breaking. Adding new flags / new subcommands is **not** breaking provided defaults preserve prior behaviour. |
| **CLI JSON output** | Any `--json` output shape (top-level keys + types). Adding new keys is **not** breaking; removing or retyping is. |
| **On-disk engagement file formats** | `.praxis/config.yaml`, `.praxis/engagement/*.yaml`, `.praxis/engagement/decisions/*.md` schemas. New optional fields are **not** breaking; removing or retyping existing fields is. Forward-compatible schema migrations are versioned via the existing `schema_version` field on Pydantic models. |
| **State files** | Sufficiency-report JSON (`.praxis/state/sufficiency-reports/*.json`), wake-report JSON (`.praxis/state/wake-reports/*.json`), audit JSONL (`.praxis/state/audit.jsonl`), work-queue items in SQLite. Same additive rule. |
| **Evidence-bundle MANIFEST.json** | `schema_version`, `praxis_version`, `engagement_name`, `generated_at`, `files: [{path, sha256, size_bytes}]`. New keys at any level are **not** breaking; renaming or retyping is. |
| **Environment-variable surface** | `PRAXIS_HOME`, `PRAXIS_DEBUG`, `PRAXIS_PII_GUARD`, `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` (and any other `*_API_KEY` env vars referenced by profiles). Renaming or removing one is breaking. |
| **Python package re-exports** | The top-level `praxis/__init__.py` exports (currently `PraxisError`, `__version__`). |

## What's **not** public

The following are internal and may change in any minor release without
notice:

- Module-internal classes / functions whose name begins with `_`.
- Cross-subsystem internals — anything imported from a subsystem's
  non-`__init__.py` module (e.g. `praxis.engagement.repos.assumptions`)
  is internal. Stick to subsystem package APIs.
- The `chunks/`, `docs/concepts/`, `scripts/` directories.
- SQLite schema beyond the documented public columns (we may add
  columns / indexes without notice; we won't break documented ones).
- The exact wording of LLM prompts, log messages, or notification
  copy.
- Test fixtures (`tests/conftest.py`, `tests/integration/_tui_seed.py`).

## Deprecation policy

When we need to remove or rename a public surface:

1. **Announce in v1.x** with a CHANGELOG note + a runtime warning where
   the old surface is used (CLI flags emit a `stderr` deprecation
   warning; deprecated env vars are still honoured for one release).
2. **Remove in v1.(x+1)** at the earliest. CLI-level changes get one
   minor-version notice; on-disk file-format changes get at least two.
3. **Migration paths** are documented in the CHANGELOG entry that
   introduces the deprecation.

We will not break a public surface in a patch release (v1.x.y → v1.x.z).

## Supported Python versions

v1.x supports **Python 3.11, 3.12, and 3.13** on Linux + macOS. CI
runs the full matrix on every push. Windows is best-effort (the
package is pure Python and likely works; we don't test it routinely).

Dropping a Python minor version requires a major release.

## Versioning of the `__version__` string

`praxis.__version__` matches the `pyproject.toml` `version` field
exactly. Both are bumped in the same release commit. The string is
read at runtime by `praxis version` and the evidence-bundle
`MANIFEST.json`.

## Pre-release labels

We use the standard SemVer pre-release suffixes:

- `1.0.0a1` — alpha, breaking changes expected.
- `1.0.0b1` — beta, feature-complete but rough edges expected.
- `1.0.0rc1` — release candidate, no expected changes besides bugfixes.

No alphas or betas were shipped for v1.0.0 — the v0.1.0 → v0.4.0
sequence served that role.

---

## Reporting a regression

If you depend on a documented public surface and a future release
breaks it, please open an issue with:

1. The surface you depended on (specific CLI invocation / file path /
   env var / etc).
2. The version that worked + the version that doesn't.
3. A minimal reproduction.

We will treat any documented public-surface break as a bug to be
fixed in the next patch release.
