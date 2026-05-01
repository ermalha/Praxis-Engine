# Chunk 06 — Skill System

**Phase:** Agent Core | **Estimated effort:** 4–5 hours | **Dependencies:** 01–05

---

## Context

Skills are filesystem artifacts that hold procedural knowledge — BABOK techniques,
project patterns, recipes for specific situations. The agent loads them
**progressively**: it sees titles + descriptions at level 0 (cheap), full
SKILL.md content at level 1 (`skill_view`), and individual reference files at
level 2 (`skill_view <name> <file>`). It can also create and amend skills via
`skill_manage` — but with a **draft-then-promote** lifecycle (P1: human-gated).

This chunk delivers the skill format, loader, registry, and the three tools
(`skill_list`, `skill_view`, `skill_manage`).

---

## Scope

### Skill format

Each skill is a directory:

```
skills/<category>/<name>/
├── SKILL.md           # required, frontmatter + body
├── references/        # optional supporting docs
├── templates/         # optional output templates
└── examples/          # optional worked examples
```

`SKILL.md` frontmatter (validated by Pydantic):

```yaml
---
name: invest-story-writing
category: requirements
description: Write user stories that satisfy INVEST criteria.
when_to_use: |
  When drafting or refining user stories from features or epics.
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: []   # e.g. ["stakeholders", "glossary"]
human_curated: true              # vs auto-generated
status: published                # draft | published
schema_version: 1
---
```

Body is plain Markdown describing: when to use, the procedure, pitfalls,
verification, examples, references.

### Loading & locations (`src/praxis/skills/loader.py`)

Skills are discovered from these locations, in increasing precedence:

1. Bundled (`<repo>/skills/`) — published with Praxis
2. User (`~/.praxis/skills/`) — installed by the user
3. Engagement (`<engagement>/.praxis/skills/`) — engagement-specific

Higher precedence shadows lower with the same name. Conflict logged at INFO.

`load_skills(profile, engagement) -> list[Skill]` returns the merged set.

A `Skill` model:

```python
class Skill(BaseModel):
    frontmatter: SkillFrontmatter
    body: str
    path: Path
    references: list[Path]
    templates: list[Path]
    examples: list[Path]
    source: Literal["bundled", "user", "engagement"]
```

### Registry (`src/praxis/skills/registry.py`)

Caches loaded skills per engagement. Reloads on file changes (mtime check at
each `list()`).

```python
class SkillRegistry:
    def list(self, *, only_active: bool = True) -> list[Skill]: ...
    def get(self, name: str) -> Skill | None: ...
    def get_file(self, name: str, file: str) -> str: ...
```

`only_active` filters by:
- `requires_toolsets` ⊆ enabled toolsets
- `fallback_for_toolsets` ∩ enabled toolsets == ∅
- `required_engagement_fields` all populated
- `status == "published"` (drafts are hidden from default `list`)

### Progressive disclosure tools (registered in chunk-5 registry)

```python
@tool(name="skill_list", description="List available skills (level 0).", toolset="skills")
def skill_list(ctx, category: str | None = None) -> ToolResult:
    """Returns name, category, description for active skills."""

@tool(name="skill_view", description="Read a skill's full content (level 1).", toolset="skills")
def skill_view(ctx, name: str, file: str | None = None) -> ToolResult:
    """If file is None, return SKILL.md body. Otherwise return the named ref/template/example."""

@tool(name="skill_manage", description="Create/patch/edit/delete a skill.",
      toolset="skills", dangerous=True)
def skill_manage(ctx,
                 action: Literal["create", "patch", "edit", "delete"],
                 name: str,
                 category: str | None = None,
                 description: str | None = None,
                 body: str | None = None,
                 patch: str | None = None) -> ToolResult:
    """All writes go to engagement-scoped skills/ as status=draft.
       Promotion to published is human-only via `praxis skill promote <name>`."""
```

`skill_manage` is `dangerous=True` because it writes engagement state. Drafts
go to `<engagement>/.praxis/skills/<category>/<name>/SKILL.md` with
`status: draft`.

### CLI additions

- `praxis skill list [--all] [--category C]`
- `praxis skill view <name> [--file F]`
- `praxis skill promote <name>` — flips `status: draft → published` after diff display + confirm
- `praxis skill diff <name>` — show the agent's proposed changes vs current published
- `praxis skill install <path-or-url>` — copy a skill folder to `~/.praxis/skills/`
- `praxis skill new <name> --category C` — scaffold a draft skill

### Audit events

- `skill.viewed` (low-noise; sample 1-in-N if needed)
- `skill.created`
- `skill.patched`
- `skill.deleted`
- `skill.promoted`

---

## Deliverables

- `src/praxis/skills/` — models, loader, registry, manage helpers
- Three tool functions registered into the chunk-5 registry
- CLI: `praxis skill list / view / promote / diff / install / new`
- Tests:
  - Frontmatter validation (good and bad)
  - Loader merges bundled + user + engagement, precedence correct
  - Conditional activation (requires/fallback toolsets, required fields)
  - `skill_view` returns body, individual files
  - `skill_manage create` writes draft to engagement scope
  - `skill_manage patch` applies a unified diff
  - `skill promote` flips status, refuses if `human_curated=false` is being kept
  - mtime-based reload picks up filesystem changes
- `tests/integration/test_chunk_06.py` — full flow: agent calls skill_list → skill_view → skill_manage create draft → human promotes
- One bundled skill for testing: `skills/_test/echo-skill/SKILL.md`
- `docs/concepts/skills.md`, `docs/reference/skill-format.md`, `docs/how-to/author-a-skill.md`
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_skill_lifecycle(tmp_engagement):
    # 1. List initially shows only the bundled echo-skill
    skills = SkillRegistry(tmp_engagement).list()
    assert any(s.frontmatter.name == "echo-skill" for s in skills)

    # 2. Agent (via tool) creates a draft
    ctx = make_test_context(tmp_engagement)
    res = skill_manage(ctx, action="create", name="my-pattern",
                       category="requirements",
                       description="A test pattern",
                       body="# My Pattern\n\nProcedure...")
    assert "draft" in res.content.lower()
    draft_path = tmp_engagement / ".praxis" / "skills" / "requirements" / "my-pattern" / "SKILL.md"
    assert draft_path.exists()

    # 3. Default list does not include drafts
    skills = SkillRegistry(tmp_engagement).list()
    assert not any(s.frontmatter.name == "my-pattern" for s in skills)

    # 4. List with all=true shows it
    skills = SkillRegistry(tmp_engagement).list(only_active=False)
    assert any(s.frontmatter.name == "my-pattern" for s in skills)

    # 5. Promote
    runner.invoke(app, ["skill", "promote", "my-pattern", "--engagement", str(tmp_engagement), "-y"])
    skills = SkillRegistry(tmp_engagement).list()
    assert any(s.frontmatter.name == "my-pattern" for s in skills)
```

---

## Explicit non-goals

- No starter library content (chunk 15)
- No agent autonomously promoting drafts — only humans via CLI
- No skill versioning beyond `schema_version` field

---

## Notes

- Skills go via the chunk-5 registry; this chunk wires the three tools in.
- `skill_manage edit` opens `$EDITOR` on the SKILL.md (or returns content if
  no editor). Useful in CLI; not callable by the LLM (only `create` and `patch` are).
- Restrict `skill_manage`'s `name` to `[a-z0-9-]+` to avoid path traversal.
- The `requires_toolsets` / `fallback_for_toolsets` mechanism is taken directly
  from Hermes; document the behavior with examples.
- `human_curated: true` skills, when patched by the agent, stay `human_curated: true`
  but flip to `status: draft` until a human re-promotes.

---

## Definition of done

- All deliverables present
- Acceptance test passes
- `pytest`, `ruff`, `mypy` green
- `chunks/STATUS.md` updated
