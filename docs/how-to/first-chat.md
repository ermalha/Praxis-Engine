# Your First Chat with Praxis

## Prerequisites

1. An initialized engagement: `praxis init --name "My Project"`
2. A configured profile with a model alias (see `docs/concepts/profiles-and-engagements.md`)

## Starting a chat

```bash
praxis chat
```

This opens an interactive REPL. The agent has access to all engagement tools
and can read/write the engagement model.

## Example session

```
> Add "invoice" to the glossary as "A request for payment for goods or services"
⚙ glossary_add_term ✓
Added 'invoice' to the glossary.

> Who are our stakeholders?
No stakeholders registered yet.

> Add Maria L. as Finance Manager with expertise in accounts payable
⚙ stakeholder_add ✓
Added stakeholder 'Maria L.' [maria-l-abc12345].

> /sessions
  [active] a1b2c3d4e5f6…
```

## Slash commands

| Command | Description |
|---------|-------------|
| `/exit` | End session and quit |
| `/new` | Start a new session |
| `/sessions` | List recent sessions |
| `/skills` | List active skills |
| `/tools` | List available tools |
| `/help` | Show help |

## CLI options

```bash
praxis chat --profile work --model fast --engagement ./my-project
```

- `--profile` — which config profile to use (default: "default")
- `--model` — model alias from the profile
- `--engagement` — path to engagement directory (auto-detected from CWD)

## Session management

```bash
praxis sessions list          # List recent sessions
praxis sessions show <id>     # Show messages from a session
```

Session IDs can be abbreviated — use just the first few characters.

## Dangerous tools

Tools that modify the engagement model (like `glossary_add_term`,
`stakeholder_add`, `write_file`) are marked as dangerous and require
your approval before execution. You'll see a prompt:

```
Tool: glossary_add_term (dangerous)
  Add a term to the engagement glossary.
  term: invoice
  definition: A request for payment
[a]pprove / [r]eject (a):
```
