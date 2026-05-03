# Using the TUI

The TUI is the analyst's daily home — a terminal-based workspace that
surfaces the work-queue, engagement data, conversation, and audit trail.

## Launching

```bash
praxis tui
```

Or specify a starting screen:

```bash
praxis tui --screen conversation
```

## Screens

| Key | Screen | Description |
|-----|--------|-------------|
| `1` | Queue | Prioritized work-items with detail pane |
| `2` | Chat | Conversation with the agent |
| `3` | Engagement | Browse stakeholders, glossary, questions, risks |
| `4` | Audit | Live tail of audit events |

## Global keys

| Key | Action |
|-----|--------|
| `q` | Quit |
| `?` | Show help overlay |
| `r` | Refresh current screen |
| `w` | Trigger a manual wake cycle |

## Work-queue actions

When viewing the queue, select an item and use:

| Key | Action |
|-----|--------|
| Arrow keys | Navigate items |
| `Enter` | Start an item (mark as in-progress) |

## Running with the orchestrator

For continuous operation, run the orchestrator in one terminal and the
TUI in another:

```bash
# Terminal 1
praxis run

# Terminal 2
praxis tui
```

The TUI picks up changes made by the orchestrator automatically.
