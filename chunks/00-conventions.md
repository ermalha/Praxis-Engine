# Chunk 00 — Cross-Cutting Conventions

> **Always-on context.** Read this before any chunk. It defines patterns
> Claude Code follows everywhere so chunks compose cleanly.

---

## 1. Module structure pattern

Every subsystem under `src/praxis/` follows this internal shape:

```
praxis/<subsystem>/
├── __init__.py          # public API: re-exports of types and functions
├── models.py            # Pydantic models / typed dataclasses
├── errors.py            # subsystem-specific exceptions (subclassing PraxisError)
├── <core_modules>.py    # logic
└── _internal.py         # private helpers (underscore prefix; not re-exported)
```

`__init__.py` is the only file other modules import from. Internal modules
import from each other freely; external imports cross only through `__init__`.

This means: **a chunk should never break another subsystem's tests** as long as
it preserves the public API in `__init__.py`.

---

## 2. Pydantic-first data discipline

- **Every persisted thing is a Pydantic v2 model.** No raw dicts saved to disk.
- Models live in `<subsystem>/models.py`.
- Use `model_config = ConfigDict(extra="forbid")` on all models.
- Datetime fields use `datetime` with timezone awareness (UTC).
- Enums for fixed sets of values (use `StrEnum` from Python 3.11+ stdlib).
- Models are versioned via a `schema_version: Literal[1]` field. When the
  schema changes, bump the literal and add a migration in `praxis/storage/migrations/`.

Example:

```python
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Literal

class Stakeholder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    id: str
    name: str
    role: str
    expertise: list[str] = []
    decision_authority: list[str] = []
    contact_preference: ContactChannel
    created_at: datetime
    updated_at: datetime
```

---

## 3. Error handling

Single base exception, subclassed per subsystem:

```python
# src/praxis/errors.py
class PraxisError(Exception):
    """Base for all Praxis errors."""

class ConfigError(PraxisError): ...
class StorageError(PraxisError): ...
class TransportError(PraxisError): ...
class ToolError(PraxisError): ...
class SkillError(PraxisError): ...
class EngagementError(PraxisError): ...
class WorkqueueError(PraxisError): ...
class SufficiencyError(PraxisError): ...
```

Rules:

- **Never raise bare `Exception` or `RuntimeError`.**
- **Never silently swallow.** If you catch, log + re-raise or convert.
- **No string-matching on error messages.** Use exception types or attributes.
- All errors carry a `details: dict` attribute for structured context.

---

## 4. Logging & audit

Two distinct log streams:

**Application logs** (debug, info, warn, error) — `structlog` to stderr by default,
optionally to `~/.praxis/logs/praxis.log`. Used for diagnostics.

**Audit log** (immutable record of state changes and decisions) — `structlog` to
JSONL files. Two destinations, written in parallel:
- `~/.praxis/audit.jsonl` (global)
- `<engagement>/.praxis/state/audit.jsonl` (per-engagement)

Audit event schema:

```python
class AuditEvent(BaseModel):
    schema_version: Literal[1] = 1
    event_id: str            # UUID
    timestamp: datetime      # UTC
    profile: str
    engagement: str | None
    actor: Literal["agent", "human", "system"]
    component: str           # subsystem name
    event_type: str          # e.g. "artifact.created", "workitem.committed"
    subject_id: str | None   # ID of the thing affected
    payload: dict            # event-specific data
    correlation_id: str | None  # for tracing related events
```

Every state change in any subsystem emits exactly one audit event. The audit
writer is a single function: `praxis.audit.emit(event_type, **payload)`.

---

## 5. Async vs sync

- **Default sync.** Most code is synchronous. Easier to test, easier to reason about.
- **Async only for I/O-bound concurrency at boundaries:**
  - LLM transport (streaming)
  - HTTP integration calls when fan-out is needed
  - Watchers (file, webhook, IMAP)
- **Never mix.** A subsystem is either sync or async, not both. The orchestrator
  bridges with `anyio` if needed.

---

## 6. CLI patterns

All CLI commands live under `src/praxis/cli/`. Use `typer` with subcommands:

```
praxis init                  # initialize an engagement
praxis run                   # start the orchestrator (TUI)
praxis ask "..."             # one-shot question
praxis queue                 # view work-queue
praxis queue commit <id>     # commit a work-item
praxis skill list / view / install
praxis engagement glossary add/list/view
praxis profile create/use/list
praxis audit tail
praxis doctor                # diagnose config & connectivity
```

Conventions:
- Every command has `--help` with examples
- Every command supports `--profile <name>` and `--engagement <path>` (or honors `cwd`)
- Every command supports `--json` for machine-readable output
- Errors exit with non-zero status and write to stderr

---

## 7. TUI patterns

The TUI is the analyst's daily home. Built with `textual`:

- **Single app** with multiple screens: WorkQueue, EngagementBrowser, Conversation, AuditTrail
- Keybindings follow modal/vim conventions where reasonable
- Every screen has a help overlay (`?`)
- All TUI actions emit audit events identical to CLI actions (no hidden mutations)

The TUI is added in chunk 13 — earlier chunks must function fully via CLI alone.

---

## 8. Tool contract

Every tool follows this pattern:

```python
from praxis.tools import tool, ToolResult, ToolContext

@tool(
    name="search_glossary",
    description="Search the engagement glossary for a term or definition.",
    toolset="engagement",
    dangerous=False,
)
def search_glossary(ctx: ToolContext, query: str) -> ToolResult:
    """Look up domain terms in the engagement glossary."""
    ...
    return ToolResult(content="...", data={"matches": [...]})
```

Rules:
- Decorator-registered (Hermes pattern)
- `ToolContext` carries profile, engagement, audit emitter, config
- `ToolResult` always typed: `content` (str for LLM) + optional `data` (dict for programs)
- `dangerous=True` triggers approval gate before execution
- Tools never call LLM transport directly (that's the agent's job)

---

## 9. Skill contract

Skills are filesystem artifacts loaded by the skill registry:

```
skills/<category>/<name>/
├── SKILL.md           # frontmatter + procedure
├── references/        # optional supporting docs
├── templates/         # optional output templates
└── examples/          # optional worked examples
```

SKILL.md frontmatter:

```yaml
---
name: invest-story-writing
category: requirements
description: Write user stories that satisfy INVEST criteria.
when_to_use: |
  When drafting or refining user stories from features or epics.
requires_toolsets: []          # optional: skill only loads if these are available
fallback_for_toolsets: []      # optional: skill only loads if these are NOT available
required_engagement_fields: [] # e.g. [stakeholders, glossary]
human_curated: true            # vs auto-generated by agent
schema_version: 1
---
```

Body is plain Markdown: when to use, procedure, pitfalls, verification, examples.

---

## 10. Storage layout & schemas

### SQLite — `<engagement>/.praxis/state/praxis.db`

Tables (created in chunk 3):

- `sessions(id, parent_id, profile, started_at, ended_at, summary)`
- `messages(id, session_id, turn, role, content, tool_calls, created_at)`
- `messages_fts` — FTS5 virtual table over `messages.content`
- `workitems(id, type, status, priority, payload_json, created_at, updated_at, ...)`
- `audit(id, timestamp, ...)` — local mirror of audit.jsonl for fast querying

### Files — engagement model

Each engagement file is a single YAML or Markdown document with frontmatter,
loaded via the typed loader in `praxis/engagement/`. Schema validation on load.

Atomic writes: write to `.tmp`, fsync, rename.

---

## 11. Test patterns

- Unit tests in `tests/unit/test_<module>.py`, mirroring `src/praxis/` structure
- Integration tests in `tests/integration/test_<chunk_name>.py`, one per chunk
- e2e tests in `tests/e2e/` exercise full flows (added later chunks)
- Use `respx` to mock HTTP; never hit real APIs
- Use `tmp_path` fixture for filesystem isolation
- Common fixtures in `tests/conftest.py`:
  - `tmp_engagement` — fresh engagement directory
  - `tmp_profile` — fresh profile directory
  - `mock_llm` — recorded LLM responses
  - `audit_capture` — capture audit events for assertions

Every chunk's acceptance test is runnable as:
```
pytest tests/integration/test_chunk_NN.py -v
```

---

## 12. Naming

- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE`
- Pydantic models: `PascalCase`, ending with what they represent (`Stakeholder`, not `StakeholderModel`)
- Test files: `test_<module>.py`
- Test functions: `test_<behavior>` (descriptive, not `test_function_name`)

---

## 13. Imports

- Standard library → third-party → first-party (`praxis.*`) → relative
- Always absolute for `praxis.*` imports across subsystems
- Relative imports only within a single subsystem

---

## 14. Forbidden patterns

- `print()` in library code (`src/praxis/`)
- Bare `except:` clauses
- `eval()` / `exec()` outside of explicitly-sandboxed tool execution
- Mutable default arguments
- Module-level side effects beyond imports and decorators
- Direct dict access for config — always go through Pydantic models
- `os.path` — use `pathlib.Path`
- `requests` — use `httpx`
- `json.dumps` for persistence — use Pydantic `.model_dump_json()`

---

## 15. When in doubt

- Check `PROJECT.md` for principles
- Check this file for patterns
- Check the chunk brief for scope
- If still ambiguous: **stop and ask the human**, do not guess
