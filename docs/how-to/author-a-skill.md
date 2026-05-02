# How to Author a Skill

## Quick start

1. Scaffold a new skill:

```bash
praxis skill new my-technique --category requirements --engagement ./my-project
```

2. Edit the generated `SKILL.md`:

```bash
$EDITOR my-project/.praxis/skills/requirements/my-technique/SKILL.md
```

3. Review the draft:

```bash
praxis skill view my-technique --engagement ./my-project
```

4. Promote to published:

```bash
praxis skill promote my-technique --engagement ./my-project
```

## Writing the SKILL.md

Start with the frontmatter:

```yaml
---
name: my-technique
category: requirements
description: A one-line summary for the agent's skill list.
when_to_use: |
  Describe the situations where this skill applies.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: draft
schema_version: 1
---
```

Then write the body in Markdown:

```markdown
# My Technique

## Procedure

1. First step...
2. Second step...

## Pitfalls

- Common mistake to avoid...

## Verification

- How to check the output is correct...
```

## Adding supporting files

Place additional files in subdirectories:

```
my-technique/
├── SKILL.md
├── references/
│   └── standard.md      # Reference documents
├── templates/
│   └── output.md        # Output templates
└── examples/
    └── sample.md        # Worked examples
```

The agent can access these via `skill_view my-technique --file standard.md`.

## Installing a skill globally

To make a skill available across all engagements:

```bash
praxis skill install ./path/to/my-technique
```

This copies the skill directory to `~/.praxis/skills/`.

## Tips

- Keep skill names lowercase with hyphens: `invest-story-writing`
- Use `requires_toolsets` to link skills to integrations
- Use `fallback_for_toolsets` for manual alternatives to automated tools
- Use `required_engagement_fields` to hide skills until relevant data exists
