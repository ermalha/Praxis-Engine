# Optional Integrations — Graceful Degradation

## Principle

Every integration in Praxis is **optional by design**. The agent must never
crash because an integration is missing, misconfigured, or temporarily
unavailable. Instead, it falls back to:

- Local file artifacts (stories, specs, reports)
- Human work-items in the queue
- Manual processes documented in the engagement model

## How it works

1. **Config-driven enablement** — Each integration has `enabled: true/false`
   in the engagement's `config.yaml`. When disabled, no tools are offered
   to the agent and no health checks run.

2. **Lazy-loaded dependencies** — Optional packages (`atlassian-python-api`,
   `imap-tools`, `fastapi`) are imported only at first use. Missing packages
   produce a clear error message, not a cryptic ImportError at startup.

3. **Toolset filtering** — The agent's tool list is filtered by enabled
   integrations. A disabled Jira integration means no `jira_*` tools appear.

4. **Health checks** — `praxis integrations status` shows which integrations
   are healthy, degraded, or unreachable.

## Supported integrations

| Kind       | Purpose                      | Optional dep            |
|------------|------------------------------|-------------------------|
| jira       | Issue tracking               | atlassian-python-api    |
| confluence | Wiki/documentation           | atlassian-python-api    |
| imap       | Inbox monitoring             | imap-tools              |
| smtp       | Outbound email               | (stdlib)                |
| webhook    | Inbound events from services | fastapi + uvicorn       |

## Adding a new integration

1. Create a package under `src/praxis/integrations/<name>/`
2. Implement the `Integration` ABC with a `health_check()` method
3. Decorate with `@register_integration`
4. Add tools using the `@tool()` decorator with your toolset name
5. Add the optional dep to `pyproject.toml`
6. Document in `docs/how-to/connect-<name>.md`
