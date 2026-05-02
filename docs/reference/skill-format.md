# Skill Format Reference

## Directory structure

```
skills/<category>/<name>/
├── SKILL.md           # required — frontmatter + body
���── references/        # optional supporting docs
├── templates/         # optional output templates
└── examples/          # optional worked examples
```

## SKILL.md frontmatter

The frontmatter is a YAML block delimited by `---`:

```yaml
---
name: invest-story-writing
category: requirements
description: Write user stories that satisfy INVEST criteria.
when_to_use: |
  When drafting or refining user stories from features or epics.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---
```

### Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | `str` | yes | — | Unique name, must match `[a-z0-9-]+` |
| `category` | `str` | yes | — | Grouping key, must match `[a-z0-9_-]+` |
| `description` | `str` | yes | — | Short description shown at level 0 |
| `when_to_use` | `str` | no | `""` | Guidance for when to apply this skill |
| `requires_toolsets` | `list[str]` | no | `[]` | Skill only active if all listed toolsets are enabled |
| `fallback_for_toolsets` | `list[str]` | no | `[]` | Skill only active if none of these are enabled |
| `required_engagement_fields` | `list[str]` | no | `[]` | Skill only active if all listed fields are populated |
| `human_curated` | `bool` | no | `true` | Whether a human wrote/maintains this skill |
| `status` | `"draft" \| "published"` | no | `"published"` | Only published skills appear in default listings |
| `schema_version` | `Literal[1]` | no | `1` | Schema version for future migrations |

## Body

The body is plain Markdown following the frontmatter. Recommended sections:

- **Procedure** — step-by-step instructions
- **Pitfalls** — common mistakes to avoid
- **Verification** — how to check the output
- **Examples** — inline examples (or reference `examples/`)

## Activation rules

A skill is "active" when all of these hold:

1. `status == "published"`
2. `requires_toolsets ⊆ enabled_toolsets`
3. `fallback_for_toolsets ∩ enabled_toolsets == ∅`
4. `required_engagement_fields` are all populated

### Example: fallback skill

```yaml
fallback_for_toolsets: [jira]
```

This skill only appears when the Jira integration is **not** enabled —
useful for providing a manual alternative.

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `references/` | Supporting documents, standards, guidelines |
| `templates/` | Output templates the agent can fill in |
| `examples/` | Worked examples showing the skill in action |

Files in these directories are accessible via `skill_view <name> --file <filename>`.
