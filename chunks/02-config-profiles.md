# Chunk 02 — Configuration & Profiles

**Phase:** Foundations | **Estimated effort:** 3–4 hours | **Dependencies:** 01

---

## Context

Praxis runs in two scopes simultaneously: a **profile** (user identity, scoped
to `~/.praxis/profiles/<name>/`) and an **engagement** (a project the analyst
is working on, scoped to `<engagement>/.praxis/`). Both have configuration.
Both must be discoverable, validated, and isolated.

This chunk builds the config system and the profile machinery. After this
chunk, `praxis init` creates an engagement directory, `praxis profile create`
creates a profile, and configuration is layered correctly: defaults → user
config → engagement config → env vars → CLI flags.

---

## Scope

### Configuration model

Build typed Pydantic v2 models for all configuration. v1 settings:

- **GlobalConfig** — applies across all engagements for a profile
  - `default_profile: str = "default"`
  - `log_level: LogLevel = LogLevel.INFO`
  - `default_model_alias: str | None = None`
  - `audit_log_path: Path | None` — defaults to `~/.praxis/audit.jsonl`
- **ProfileConfig** — per-profile settings
  - `name: str`
  - `display_name: str | None`
  - `model_aliases: dict[str, ModelConfig]` — named LLM presets
  - `default_model_alias: str = "default"`
- **ModelConfig** — one LLM target preset
  - `provider: Literal["anthropic", "openai", "openrouter", "openai_compat"]`
  - `model: str`
  - `base_url: HttpUrl | None`
  - `api_key_env: str` — name of env var holding the key
  - `extra_headers: dict[str, str] = {}`
  - `timeout_s: int = 120`
- **EngagementConfig** — per-engagement settings
  - `name: str`
  - `methodology: Literal["agile", "scrum", "kanban", "waterfall", "hybrid", "none"] = "none"`
  - `model_alias: str | None` — overrides profile default
  - `integrations: dict[str, IntegrationConfig] = {}`
  - `wake_cycle: WakeCycleConfig`
- **IntegrationConfig** — one integration's enable/disable + connection settings (see chunk 14 for full integrations; this chunk just defines the shape)
  - `enabled: bool = false`
  - `kind: Literal["jira", "confluence", "imap", "smtp", "webhook"]`
  - `settings: dict[str, str] = {}` — kind-specific
- **WakeCycleConfig** — orchestrator timing
  - `mode: Literal["manual", "scheduled", "event_driven", "mixed"] = "manual"`
  - `interval_minutes: int = 15`
  - `quiet_hours: tuple[int, int] | None = None`

All in `src/praxis/config/models.py`.

### Config loader

`src/praxis/config/loader.py` exposes:

```python
def load_global_config(home: Path | None = None) -> GlobalConfig: ...
def load_profile(name: str, home: Path | None = None) -> ProfileConfig: ...
def load_engagement_config(path: Path) -> EngagementConfig: ...
def resolve_model_config(profile: ProfileConfig, engagement: EngagementConfig | None,
                        cli_alias: str | None = None) -> ModelConfig: ...
```

Resolution order (lowest to highest precedence):
1. Defaults baked into Pydantic models
2. `~/.praxis/config.yaml` for global, `~/.praxis/profiles/<name>/profile.yaml` for profile
3. `<engagement>/.praxis/config.yaml` for engagement
4. Environment variables prefixed `PRAXIS_*` (e.g. `PRAXIS_LOG_LEVEL`)
5. CLI flags (passed in by caller)

If a YAML file is malformed or doesn't validate against its model, raise
`ConfigError` with the validation details.

### Engagement and profile lifecycle

`src/praxis/config/profiles.py`:

```python
def create_profile(name: str, home: Path | None = None) -> ProfileConfig: ...
def list_profiles(home: Path | None = None) -> list[str]: ...
def delete_profile(name: str, home: Path | None = None, *, force: bool = False) -> None: ...
def get_active_profile_name(home: Path | None = None) -> str: ...  # from PRAXIS_PROFILE or default
```

`src/praxis/config/engagement.py`:

```python
def init_engagement(path: Path, name: str, *, methodology: str = "none") -> EngagementConfig: ...
def find_engagement(start: Path) -> Path | None:  # walk up looking for .praxis/
    ...
def is_engagement(path: Path) -> bool: ...
```

`init_engagement` creates the full directory layout from `PROJECT.md`:

```
<path>/.praxis/
├── config.yaml           # EngagementConfig
├── engagement/
│   ├── glossary.yaml
│   ├── stakeholders.yaml
│   ├── decisions/        (empty dir)
│   ├── open-questions.yaml
│   ├── assumptions-and-constraints.yaml
│   ├── system-landscape.yaml
│   ├── timeline.yaml
│   ├── risks.yaml
│   └── lessons-learned.md
├── artifacts/
│   ├── stories/
│   ├── specs/
│   ├── models/
│   ├── matrices/
│   └── reports/
├── state/                # SQLite + audit log; populated by chunk 3
└── skills/               # engagement-specific skills
```

YAML files start as empty-but-valid documents (e.g., `glossary.yaml` is `{terms: []}`).

### CLI commands

Add to `src/praxis/cli/`:

```
praxis init [path] [--name NAME] [--methodology M]
praxis profile create <name>
praxis profile list
praxis profile use <name>
praxis profile delete <name> [--force]
praxis config show [--profile P] [--engagement E]
```

`praxis config show` prints the resolved effective config (Rich table or JSON
with `--json`).

### Audit emission

Every state change emits an audit event. For this chunk that means:

- `profile.created`
- `profile.deleted`
- `engagement.initialized`

Use a stub audit emitter for now: write JSONL line to `~/.praxis/audit.jsonl`.
A proper structured audit subsystem comes in chunk 3, but the API
`praxis.audit.emit(event_type, **payload)` should already exist as a thin
function so config code doesn't need to change later.

---

## Deliverables

- `src/praxis/config/__init__.py` — public API
- `src/praxis/config/models.py` — Pydantic models (see Scope)
- `src/praxis/config/loader.py` — load/resolve functions
- `src/praxis/config/profiles.py` — profile lifecycle
- `src/praxis/config/engagement.py` — engagement lifecycle
- `src/praxis/audit/__init__.py` — stub `emit()` function (full subsystem in chunk 3)
- `src/praxis/cli/init.py`, `profile.py`, `config.py` — typer command groups
- Wire commands into root `app` in `src/praxis/cli/__init__.py`
- `tests/unit/test_config_models.py`
- `tests/unit/test_config_loader.py`
- `tests/unit/test_profiles.py`
- `tests/unit/test_engagement_lifecycle.py`
- `tests/integration/test_chunk_02.py` — end-to-end CLI flow
- Update `tests/conftest.py` with `tmp_home` and `tmp_engagement` fixtures
- `docs/concepts/profiles-and-engagements.md` — explain the model
- `docs/reference/config-schema.md` — reference for all settings
- Update `chunks/STATUS.md`

---

## Acceptance test

`tests/integration/test_chunk_02.py` exercises this end-to-end:

```python
def test_full_profile_and_engagement_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    home = tmp_path / ".praxis"

    # 1. Create profile
    runner.invoke(app, ["profile", "create", "alice"])
    assert (home / "profiles" / "alice" / "profile.yaml").exists()

    # 2. List profiles includes alice
    result = runner.invoke(app, ["profile", "list", "--json"])
    assert "alice" in result.stdout

    # 3. Init engagement
    eng = tmp_path / "myproj"
    eng.mkdir()
    runner.invoke(app, ["init", str(eng), "--name", "Demo Project"])
    assert (eng / ".praxis" / "config.yaml").exists()
    assert (eng / ".praxis" / "engagement" / "glossary.yaml").exists()

    # 4. Resolved config picks up engagement
    result = runner.invoke(app, ["config", "show",
                                 "--profile", "alice",
                                 "--engagement", str(eng), "--json"])
    cfg = json.loads(result.stdout)
    assert cfg["engagement"]["name"] == "Demo Project"

    # 5. Audit log has events
    audit = (home / "audit.jsonl").read_text().splitlines()
    types = [json.loads(line)["event_type"] for line in audit]
    assert "profile.created" in types
    assert "engagement.initialized" in types
```

Plus: `pytest`, `ruff check`, `mypy src/praxis` all pass.

---

## Explicit non-goals

- No actual LLM calls (chunk 4)
- No SQLite (chunk 3)
- No real audit subsystem — just the stub `emit()` writing JSONL
- No engagement model loaders (chunk 7) — just the empty file scaffolds
- No actual integration logic (chunk 14)
- No TUI

---

## Notes

- `find_engagement` walks up the directory tree looking for a `.praxis/`
  directory, similar to how git finds `.git/`. This means `praxis run` works
  from any subdirectory of the engagement root.
- Profile names are restricted to `[a-z0-9_-]+`. Validate on creation.
- When deleting a profile, refuse if it's the active one and `--force` not
  passed. Active profile = `PRAXIS_PROFILE` env var or `default_profile` from global.
- Atomic file writes: every YAML write goes to `<file>.tmp`, fsync, rename.
- All env-var-derived secrets (`api_key_env`) are *names*, not values. The
  config never holds the secret itself.

---

## Definition of done

- All deliverables present
- Acceptance test passes
- `pytest`, `ruff`, `mypy` green
- Docs updated
- `chunks/STATUS.md` updated
- Commits: one or more, conventional commit messages
