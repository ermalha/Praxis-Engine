# Chunk 15 — Starter Skill Library

**Phase:** Real-World Surface | **Estimated effort:** 5–6 hours | **Dependencies:** 01–14

---

## Context

Skills are how the agent encodes BA expertise. Without a starter library, every
new engagement starts cold. This chunk delivers **12 production-grade starter
skills** covering the BABOK essentials, bundled with Praxis at install time.

These are **content-heavy, code-light**. The skill loader (chunk 6) does all
the work; this chunk just authors high-quality SKILL.md files.

---

## Scope

### The 12 starter skills

Each lives in `skills/<category>/<name>/`. Categories follow chunk-6's layout.

#### Elicitation (`skills/elicitation/`)

1. **interview-preparation** — preparing for a stakeholder interview: research, agenda, question types (open/closed/probing), recording, transcript handling, follow-ups
2. **stakeholder-analysis** — identifying, classifying (RACI / Salience / Influence-Interest), and tracking stakeholders; output is a populated stakeholder map

#### Analysis (`skills/analysis/`)

3. **gap-analysis** — current state vs. desired state, structured gap identification, prioritization, output template
4. **process-modeling-bpmn** — drawing BPMN process models in text/Mermaid; conventions for swimlanes, gateways, events, message flows; pitfalls

#### Modeling (`skills/modeling/`)

5. **decision-matrix-construction** — defining options and criteria, weighting, scoring methods (weighted sum, AHP-lite), sensitivity check, output template
6. **raci-construction** — building a RACI from a process or scope statement, conflict checks (single A, no orphan tasks)

#### Requirements (`skills/requirements/`)

7. **invest-story-writing** — drafting and refining user stories that satisfy INVEST (Independent, Negotiable, Valuable, Estimable, Small, Testable)
8. **acceptance-criteria-gwt** — writing Given-When-Then acceptance criteria; one scenario per behavior; data tables; common smells
9. **requirements-traceability-matrix** — linking business need → feature → story → test; maintaining the matrix; orphan and over-coverage checks

#### Decision (`skills/decision/`)

10. **adr-authoring** — Architecture Decision Records: context, decision, consequences, alternatives; ADR numbering; superseding ADRs

#### Communication (`skills/communication/`)

11. **status-report** — writing weekly/monthly status reports: progress, plan, blockers, asks, RAID; tone calibrated to audience

#### Governance (`skills/governance/`)

12. **risk-register-entry** — adding a risk: likelihood/impact/qualifier, mitigation type, owner, review cadence; common BA risk patterns

### Skill quality bar

Each SKILL.md must:

- Be ≥ 300 words and ≤ 1500 words for the body (level-1 content)
- Have at least one concrete worked example
- List at least three pitfalls
- Have a verification section ("how do I know I did this well?")
- Reference the BABOK technique it derives from (where applicable) without copying text
- Include a `templates/` subfolder with at least one output template (e.g., a markdown skeleton for the deliverable)

For the more procedural ones (story-writing, GWT, ADR), include 2–3
contrasting examples (good / weak) in `examples/`.

### Frontmatter conventions

All starter skills:

```yaml
---
name: <slug>
category: <category>
description: <one-line>
when_to_use: |
  <multi-line>
requires_toolsets: []
fallback_for_toolsets: []
required_engagement_fields: [...]   # e.g. [stakeholders] for those that need it
human_curated: true
status: published
schema_version: 1
---
```

Some skills will have `required_engagement_fields`:
- `interview-preparation` → `[stakeholders]`
- `stakeholder-analysis` → `[]` (it can populate stakeholders from scratch)
- `requirements-traceability-matrix` → `[]`
- others → `[]` by default

### Bundling

The skills folder lives at the repo root (`<repo>/skills/`). The chunk-6
loader's "bundled" path resolves to `praxis.skills` package data — wire this
via Hatch's `[tool.hatch.build.targets.wheel.force-include]` so skills are
shipped in the wheel.

Update `pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel.force-include]
"skills" = "praxis/_bundled_skills"
```

The skill loader then locates them via `importlib.resources` from
`praxis._bundled_skills`.

### Integration test for the skill library

Sanity-check that all 12 load and validate:

```python
def test_all_starter_skills_load_and_validate(tmp_engagement):
    skills = SkillRegistry(tmp_engagement).list()
    names = {s.frontmatter.name for s in skills}
    expected = {
        "interview-preparation", "stakeholder-analysis",
        "gap-analysis", "process-modeling-bpmn",
        "decision-matrix-construction", "raci-construction",
        "invest-story-writing", "acceptance-criteria-gwt",
        "requirements-traceability-matrix",
        "adr-authoring", "status-report", "risk-register-entry",
    }
    assert expected.issubset(names)
    for s in skills:
        if s.source == "bundled":
            assert s.frontmatter.status == "published"
            assert s.frontmatter.human_curated is True
            assert len(s.body) >= 300
```

---

## Deliverables

- 12 skill folders under `skills/<category>/<name>/`, each containing:
  - `SKILL.md` (frontmatter + body)
  - `templates/` with at least one template file
  - `examples/` for procedural skills (story, GWT, ADR — minimum)
- Bundling wired in `pyproject.toml` (Hatch `force-include`)
- Loader update to use `importlib.resources` for bundled skills
- `tests/integration/test_chunk_15.py` validating all 12 load
- `docs/reference/starter-skills.md` — index with descriptions and when to use each
- Update `chunks/STATUS.md` — final box checked
- Update top-level `README.md` to mention the bundled skill library

---

## Acceptance test

```bash
uv pip install -e .
uv run python -c "
from praxis.skills.loader import load_bundled_skills
skills = load_bundled_skills()
print(f'loaded {len(skills)} bundled skills')
assert len(skills) >= 12
"
uv run praxis skill list
# Output shows all 12 starter skills, status=published
```

Plus the integration test passes.

---

## Explicit non-goals

- No content beyond the 12 named skills (community contribution path)
- No skill versioning / migration logic — `schema_version: 1` for all
- No automated linting of SKILL.md content beyond frontmatter validation

---

## Notes

- These skills are the agent's working manual. Quality matters more than quantity.
- Write them as if for a junior BA: opinionated, concrete, with examples.
- Avoid copying BABOK text directly. Reference and rephrase.
- Templates should be drop-in usable — the agent often outputs an instance of
  the template after running the skill.
- The skill body should describe the procedure clearly enough that a different
  LLM (cheaper / open-source) can execute it, since users may run with various models.

---

## Definition of done

- All 12 skills written, validated, bundled
- Acceptance test passes
- All chunks 1–15 complete; `chunks/STATUS.md` shows full ✅ row
- Tagged release `v0.1.0` ready
