# Connect Confluence

## Prerequisites

- A Confluence Cloud or Server instance
- An API token (same Atlassian token as Jira)

## Configuration

Add to your engagement's `.praxis/config.yaml`:

```yaml
integrations:
  confluence:
    enabled: true
    kind: confluence
    settings:
      base_url: https://your-org.atlassian.net
      email_env: CONFLUENCE_EMAIL
      token_env: CONFLUENCE_TOKEN
```

Set environment variables:

```bash
export CONFLUENCE_EMAIL="you@company.com"
export CONFLUENCE_TOKEN="your-api-token"
```

## Verify

```bash
praxis integrations test confluence
```

## Available tools

- `confluence_search` — CQL search across spaces
- `confluence_get_page` — Fetch by ID or space+title
- `confluence_create_page` (requires approval)
- `confluence_update_page` (requires approval)
