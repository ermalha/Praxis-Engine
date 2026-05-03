# Setup Webhooks

## Overview

The webhook receiver lets external systems (CI, monitoring, SaaS) push
events into Praxis without polling. Each webhook path has a secret token
for HMAC-SHA256 validation.

## Configuration

Add to your engagement's `.praxis/config.yaml`:

```yaml
integrations:
  webhook:
    enabled: true
    kind: webhook
    settings:
      port: "8765"
      paths: '[{"path": "/jira-events", "secret_env": "PRAXIS_JIRA_WEBHOOK_SECRET", "kind": "jira_webhook"}, {"path": "/ci-events", "secret_env": "PRAXIS_CI_SECRET", "kind": "ci_webhook"}]'
```

Set secrets:

```bash
export PRAXIS_JIRA_WEBHOOK_SECRET="your-webhook-secret"
export PRAXIS_CI_SECRET="your-ci-secret"
```

## Start the server

```bash
praxis webhook serve --port 8765
```

## How events are processed

1. External system POSTs JSON to the configured path
2. Receiver validates the `X-Hub-Signature-256` header (if secret configured)
3. Payload is persisted to `<engagement>/.praxis/state/inbox/webhook/<timestamp>.json`
4. Audit event `inbox.webhook_received` is emitted
5. An `INBOX_EVENT` wake trigger fires on the next orchestrator cycle

## Requirements

```bash
pip install praxis-ba[webhook]
```

This installs `fastapi` and `uvicorn`.

## Testing locally

```bash
curl -X POST http://localhost:8765/ci-events \
  -H "Content-Type: application/json" \
  -d '{"build": "passed", "commit": "abc123"}'
```
