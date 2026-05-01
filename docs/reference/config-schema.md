# Configuration Schema Reference

All configuration is expressed as Pydantic v2 models with `extra="forbid"`.

## GlobalConfig

Stored in `~/.praxis/config.yaml`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `schema_version` | `Literal[1]` | `1` | Schema version for migrations |
| `default_profile` | `str` | `"default"` | Active profile name |
| `log_level` | `LogLevel` | `"info"` | One of: debug, info, warning, error |
| `default_model_alias` | `str \| None` | `None` | Global default model alias |
| `audit_log_path` | `Path \| None` | `None` | Custom audit log path (defaults to `~/.praxis/audit.jsonl`) |

## ProfileConfig

Stored in `~/.praxis/profiles/<name>/profile.yaml`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `schema_version` | `Literal[1]` | `1` | Schema version |
| `name` | `str` | required | Profile name (`[a-z0-9_-]+`) |
| `display_name` | `str \| None` | `None` | Human-readable label |
| `model_aliases` | `dict[str, ModelConfig]` | `{}` | Named LLM presets |
| `default_model_alias` | `str` | `"default"` | Which alias to use by default |

## ModelConfig

Nested inside `ProfileConfig.model_aliases`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `schema_version` | `Literal[1]` | `1` | Schema version |
| `provider` | `Provider` | required | One of: anthropic, openai, openrouter, openai_compat |
| `model` | `str` | required | Model identifier (e.g. `claude-sonnet-4-20250514`) |
| `base_url` | `HttpUrl \| None` | `None` | Custom API base URL |
| `api_key_env` | `str` | required | Env var name holding the API key |
| `extra_headers` | `dict[str, str]` | `{}` | Additional HTTP headers |
| `timeout_s` | `int` | `120` | Request timeout in seconds |

## EngagementConfig

Stored in `<project>/.praxis/config.yaml`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `schema_version` | `Literal[1]` | `1` | Schema version |
| `name` | `str` | required | Human-readable engagement name |
| `methodology` | `Methodology` | `"none"` | One of: agile, scrum, kanban, waterfall, hybrid, none |
| `model_alias` | `str \| None` | `None` | Override profile's default model alias |
| `integrations` | `dict[str, IntegrationConfig]` | `{}` | Integration settings |
| `wake_cycle` | `WakeCycleConfig` | (defaults) | Orchestrator timing |

## WakeCycleConfig

Nested inside `EngagementConfig.wake_cycle`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `schema_version` | `Literal[1]` | `1` | Schema version |
| `mode` | `WakeCycleMode` | `"manual"` | One of: manual, scheduled, event_driven, mixed |
| `interval_minutes` | `int` | `15` | Wake interval for scheduled mode |
| `quiet_hours` | `tuple[int, int] \| None` | `None` | Hours during which agent won't wake (start, end) |

## IntegrationConfig

Nested inside `EngagementConfig.integrations`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `schema_version` | `Literal[1]` | `1` | Schema version |
| `enabled` | `bool` | `false` | Whether this integration is active |
| `kind` | `IntegrationKind` | required | One of: jira, confluence, imap, smtp, webhook |
| `settings` | `dict[str, str]` | `{}` | Kind-specific connection settings |

## Enums

### LogLevel
`debug`, `info`, `warning`, `error`

### Methodology
`agile`, `scrum`, `kanban`, `waterfall`, `hybrid`, `none`

### Provider
`anthropic`, `openai`, `openrouter`, `openai_compat`

### WakeCycleMode
`manual`, `scheduled`, `event_driven`, `mixed`

### IntegrationKind
`jira`, `confluence`, `imap`, `smtp`, `webhook`
