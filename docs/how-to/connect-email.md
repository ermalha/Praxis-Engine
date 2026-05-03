# Connect Email (IMAP + SMTP)

## Prerequisites

- An IMAP-enabled mailbox for receiving
- SMTP access for sending
- App password if using Gmail (not your regular password)

## Configuration

Add to your engagement's `.praxis/config.yaml`:

```yaml
integrations:
  email:
    enabled: true
    kind: imap
    settings:
      host: imap.gmail.com
      port: "993"
      tls: "true"
      user_env: PRAXIS_IMAP_USER
      password_env: PRAXIS_IMAP_PASSWORD
      mailbox: INBOX
      poll_interval_seconds: "300"
  smtp:
    enabled: true
    kind: smtp
    settings:
      host: smtp.gmail.com
      port: "587"
      tls: "true"
      user_env: PRAXIS_SMTP_USER
      password_env: PRAXIS_SMTP_PASSWORD
      from_addr: praxis@yourcompany.com
```

Set environment variables:

```bash
export PRAXIS_IMAP_USER="praxis@yourcompany.com"
export PRAXIS_IMAP_PASSWORD="app-password-here"
export PRAXIS_SMTP_USER="praxis@yourcompany.com"
export PRAXIS_SMTP_PASSWORD="app-password-here"
```

## Verify

```bash
praxis integrations test imap
praxis integrations test smtp
```

## Usage

### One-shot poll

```bash
praxis email poll
```

### Orchestrator integration

When running with `praxis run`, the orchestrator polls IMAP on each
wake cycle and matches incoming replies to SEND_MESSAGE work-items.

### Reply matching

The matcher links incoming emails to completed SEND_MESSAGE work-items by
checking if the sender matches the work-item's recipient field.
