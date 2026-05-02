---
name: echo-skill
category: _test
description: A minimal test skill that echoes back its input.
when_to_use: |
  Used only in automated tests to verify the skill loading pipeline.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []
human_curated: true
status: published
schema_version: 1
---

# Echo Skill

This is a minimal skill used for testing the skill subsystem.

## Procedure

1. Read the input provided by the user.
2. Echo it back verbatim.

## Verification

- The output matches the input exactly.
