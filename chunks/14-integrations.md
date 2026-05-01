# Chunk 14 — Integrations Bundle

**Phase:** Real-World Surface | **Estimated effort:** 6–7 hours | **Dependencies:** 01–13

---

## Context

Praxis is fully functional with no external integrations (P12). This chunk
adds the optional connectors that make it more powerful: Jira, Confluence,
IMAP/SMTP for email, generic webhooks, and the browser harness symlink.

**Hard rule:** every integration must degrade gracefully when not configured.
The agent must never blow up because an integration is missing — it falls back
to local file artifacts and human work-items.

---

## Scope

### Integration framework (`src/praxis/integrations/`)

```python
class Integration(ABC):
    name: str
    kind: str  # "jira", "confluence", etc.

    def __init__(self, config: IntegrationConfig): ...
    def health_check(self) -> HealthResult: ...
    def is_enabled(self) -> bool: ...
```

A registry pattern parallel to tools:

```python
def register_integration(cls: type[Integration]) -> type[Integration]: ...
def get_integration(kind: str, config: IntegrationConfig) -> Integration: ...
```

Each integration self-registers and is lazy-loaded. Optional dependencies
(e.g., `atlassian-python-api`) are imported at first use, not at startup.

### Jira integration (`src/praxis/integrations/jira/`)

- Auth via API token from env var (config holds the env var name)
- Read tools (toolset="jira"):
  - `jira_search_issues(jql, limit=20)`
  - `jira_get_issue(key)`
  - `jira_list_projects()`
  - `jira_get_sprint_issues(sprint_id)`
- Write tools (dangerous=True):
  - `jira_create_issue(project, summary, description, issuetype, ...)`
  - `jira_update_issue(key, fields)`
  - `jira_add_comment(key, body)`
  - `jira_transition_issue(key, transition_id)`
- Sync helper: when the agent drafts a user story locally
  (`<engagement>/.praxis/artifacts/stories/<id>.md`) and Jira is connected,
  it can offer to sync to Jira (always producing a SEND_MESSAGE / human
  commit work-item — agent never writes to Jira without commit).

### Confluence integration (`src/praxis/integrations/confluence/`)

- Read tools:
  - `confluence_search(cql, limit=10)`
  - `confluence_get_page(space, title | id)`
- Write tools (dangerous=True):
  - `confluence_create_page(space, title, body, parent_id)`
  - `confluence_update_page(id, body)`

Same sync-helper pattern as Jira.

### Email integration (`src/praxis/integrations/email/`)

Two complementary connectors:

- **IMAP inbox watcher** (read):
  - On wake cycle, fetch new messages since last check
  - Parse: from, to, subject, body, date, message-id, in-reply-to
  - For each message, attempt to match against open SEND_MESSAGE work-items
    (matching by recipient + recent send date)
  - On match: surface a candidate "answer" to the agent for processing
    — the agent decides if the reply answers the original question, and if so
    proposes updating the OpenQuestion (still requires human commit)
- **SMTP send** (write, dangerous=True):
  - `email_send(to, subject, body, cc=None, in_reply_to=None)`
  - Used after a human commits a SEND_MESSAGE work-item where the channel is email

Configuration: server, port, TLS, username, password env var.

### Generic webhook receiver (`src/praxis/integrations/webhook/`)

Lightweight HTTP endpoint (FastAPI optional dep, only imported if webhooks enabled).

- `praxis webhook serve --port 8765` runs the receiver
- Each registered webhook is a path + secret token + handler kind
- On receipt: validate token, parse payload, persist to
  `<engagement>/.praxis/state/inbox/webhook/<timestamp>.json`, emit
  `inbox.webhook_received` audit event, and trigger an `INBOX_EVENT` wake.

This is how external systems (CI, monitoring, SaaS callbacks) feed events
into Praxis without polling.

### Browser harness symlink (`src/praxis/integrations/browser/`)

A small post-install helper:

- `praxis browser install` — clones `browser-use/browser-harness` to
  `~/.praxis/browser-harness/` (or a configurable path) and symlinks the
  SKILL.md, interaction-skills, and domain-skills into the user's
  `~/.praxis/skills/` directory (Hermes pattern).
- `praxis browser doctor` — verifies the symlinks, daemon connectivity, etc.
- Document the workflow: this gives Praxis CDP-level browser automation by
  delegating to the agent's terminal tool, exactly as Hermes does.

No deep integration code — just the install helper and docs.

### Integration configuration

In `EngagementConfig.integrations`:

```yaml
integrations:
  jira:
    enabled: true
    kind: jira
    settings:
      base_url: https://example.atlassian.net
      email_env: JIRA_EMAIL
      token_env: JIRA_TOKEN
      default_project: BA
  confluence:
    enabled: false
    kind: confluence
    settings: {}
  email:
    enabled: true
    kind: imap
    settings:
      host: imap.gmail.com
      port: 993
      tls: true
      user_env: PRAXIS_IMAP_USER
      password_env: PRAXIS_IMAP_PASSWORD
      mailbox: INBOX
      poll_interval_seconds: 300
  smtp:
    enabled: true
    kind: smtp
    settings: { ... }
  webhook:
    enabled: true
    kind: webhook
    settings:
      port: 8765
      paths:
        - path: /jira-events
          secret_env: PRAXIS_JIRA_WEBHOOK_SECRET
          kind: jira_webhook
```

When `enabled: false`, the integration is not loaded, no tools registered,
no health-check.

### CLI

```
praxis integrations status            # health-check all enabled
praxis integrations enable <kind>     # opens YAML in $EDITOR with template
praxis integrations test <kind>       # dry-run a connectivity test
praxis browser install / doctor
praxis webhook serve [--port N]
praxis email poll                     # one-shot inbox check (else triggered by orchestrator)
```

---

## Deliverables

- `src/praxis/integrations/` — framework, jira, confluence, email, webhook, browser
- New optional deps: `atlassian-python-api`, `imap-tools`, `fastapi`, `uvicorn`,
  added under `[project.optional-dependencies]` extras (`jira`, `confluence`, `email`, `webhook`)
- All tools registered, all CLI commands wired
- Inbox watcher integrated with chunk-12 wake cycle
- Stub Jira + Confluence test fixtures using `respx` against their REST API mocks
- Tests:
  - Each integration's tool surface, mocked
  - Graceful degradation: when integration is disabled, tools are not registered
    and the agent's tool list omits them
  - Inbox watcher correctly matches replies to SEND_MESSAGE work-items
  - Webhook receives, validates token, persists, triggers wake
  - Browser install helper creates expected symlinks (in `tmp_path`)
- `tests/integration/test_chunk_14.py` — full flow: agent drafts a story locally,
  human commits Jira sync, Jira issue created (mocked), local story updated with Jira key
- `docs/how-to/connect-jira.md`, `connect-confluence.md`, `connect-email.md`,
  `connect-browser-harness.md`, `setup-webhooks.md`
- `docs/concepts/optional-integrations.md` — the graceful-degradation principle
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_jira_integration_is_optional(tmp_engagement_no_jira):
    # integration disabled in config
    tools = make_tool_registry_for(tmp_engagement_no_jira).list()
    names = {t.name for t in tools}
    assert "jira_create_issue" not in names
    # agent runs without Jira just fine — drafts a story locally
    ...
    story_path = tmp_engagement_no_jira / ".praxis/artifacts/stories/BA-001.md"
    assert story_path.exists()

def test_jira_sync_when_enabled(respx_mock, tmp_engagement_with_jira):
    respx_mock.post(re.compile(r"https://example\.atlassian\.net/rest/api/3/issue")).mock(
        return_value=Response(201, json={"key": "BA-42"})
    )
    # agent has draft locally; we commit a sync work-item
    item = WorkItem(type=WorkItemType.EXECUTE_IN_SYSTEM, ...)
    runner.invoke(app, ["queue", "commit", item.id, "--note", "synced"])
    issue = JiraClient(...).get("BA-42")
    assert issue["key"] == "BA-42"
```

---

## Explicit non-goals

- No Slack/Teams integration in v1 (community contribution path)
- No GitHub/GitLab integration in v1
- No requirements management tools (DOORS, etc.) in v1
- No ITSM tools (ServiceNow, etc.) in v1

---

## Notes

- Each integration is its own subpackage so it's clearly removable. A user
  who only wants email + browser shouldn't need Jira deps installed.
- All write operations through integrations are `dangerous=True`. No exceptions.
- Polling intervals are configurable; default to 5 minutes for inbox, never
  less than 60 seconds.
- The browser-harness install helper documents that browser-use is a separate
  project and links to its repo and license. Don't bundle it.
- For local dev, prefer test fixtures over real API calls. The CI never hits
  real Jira/Confluence/email servers.

---

## Definition of done

- All deliverables present
- All integrations enable/disable cleanly via config
- Acceptance test passes (mocked external services)
- Manual smoke test against a real Jira instance (developer's responsibility, not CI)
- `pytest`, `ruff`, `mypy` green (mypy may be relaxed on integrations as per
  chunk 1 mypy config)
- `chunks/STATUS.md` updated
