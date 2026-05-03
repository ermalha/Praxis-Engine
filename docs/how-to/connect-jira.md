# Connect Jira

## Prerequisites

- A Jira Cloud or Server instance
- An API token (generate at https://id.atlassian.com/manage/api-tokens)

## Configuration

Add to your engagement's `.praxis/config.yaml`:

```yaml
integrations:
  jira:
    enabled: true
    kind: jira
    settings:
      base_url: https://your-org.atlassian.net
      email_env: JIRA_EMAIL
      token_env: JIRA_TOKEN
      default_project: BA
```

Set environment variables:

```bash
export JIRA_EMAIL="you@company.com"
export JIRA_TOKEN="your-api-token"
```

## Verify

```bash
praxis integrations test jira
```

## Available tools

When Jira is enabled, the agent gains:

- `jira_search_issues` — JQL search
- `jira_get_issue` — Fetch by key
- `jira_list_projects` — List accessible projects
- `jira_get_sprint_issues` — Sprint backlog
- `jira_create_issue` (requires approval)
- `jira_update_issue` (requires approval)
- `jira_add_comment` (requires approval)
- `jira_transition_issue` (requires approval)

## Sync workflow

1. Agent drafts a story locally in `.praxis/artifacts/stories/`
2. When ready, agent creates a SEND_MESSAGE work-item proposing Jira sync
3. Human commits the work-item
4. Agent creates the Jira issue and updates the local file with the Jira key
