# Skills

Skills are filesystem artifacts that hold procedural knowledge — BABOK
techniques, project patterns, recipes for specific situations. The agent
loads them **progressively** to minimize context usage.

## Progressive disclosure

Skills are surfaced to the LLM at three levels:

| Level | What the agent sees | Tool |
|-------|-------------------|------|
| 0 | Name, category, description | `skill_list` |
| 1 | Full SKILL.md body | `skill_view <name>` |
| 2 | Individual reference/template/example files | `skill_view <name> --file <f>` |

This approach keeps the context window lean — the agent only pulls in full
skill content when it decides a skill is relevant.

## Skill locations

Skills are discovered from three locations, in increasing precedence:

1. **Bundled** (`<repo>/skills/`) — shipped with Praxis
2. **User** (`~/.praxis/skills/`) — installed by the user
3. **Engagement** (`<engagement>/.praxis/skills/`) — engagement-specific

Higher precedence shadows lower with the same name.

## Activation filters

A skill is considered "active" when:

- `status` is `published` (not `draft`)
- All `requires_toolsets` are currently enabled
- None of `fallback_for_toolsets` are currently enabled
- All `required_engagement_fields` are populated

This means skills can be context-sensitive — e.g., a manual Jira skill
only appears when the Jira integration is disabled.

## Draft-then-promote lifecycle

When the agent creates or patches a skill via `skill_manage`, the result
is always a **draft** in the engagement scope. Drafts are hidden from
the default skill list. A human must explicitly promote them via:

```
praxis skill promote <name>
```

This ensures human oversight over procedural knowledge changes.

## Key design decisions

- Skills **never call the LLM** — they are passive knowledge artifacts
- The agent can create/edit skills, but only as drafts
- `human_curated: true` skills retain that flag when patched by the agent,
  but flip to `status: draft` until a human re-promotes
- Skill names are restricted to `[a-z0-9-]+` to prevent path traversal
