# Chunk 07 — Engagement Model API

**Phase:** Agent Core | **Estimated effort:** 5–6 hours | **Dependencies:** 01–06

---

## Context

The engagement model is Praxis's structured memory: typed CRUD over the
glossary, stakeholders, decisions, open questions, system landscape, timeline,
risks, and assumptions/constraints. Every read and every write goes through
this layer, with validation and audit events.

This chunk replaces the empty-file scaffolds from chunk 02 with real, typed
APIs and the tools the agent will use to read and modify the engagement model.

---

## Scope

### Pydantic models (`src/praxis/engagement/models.py`)

For each engagement model component, define one or more Pydantic models. v1
models (keep them small and extensible — add fields later as needed):

```python
class GlossaryTerm(BaseModel):
    term: str
    definition: str
    synonyms: list[str] = []
    notes: str | None = None
    sources: list[str] = []
    created_at: datetime
    updated_at: datetime

class Glossary(BaseModel):
    schema_version: Literal[1] = 1
    terms: list[GlossaryTerm] = []

class ContactChannel(StrEnum):
    EMAIL = "email"
    TEAMS = "teams"
    SLACK = "slack"
    PHONE = "phone"
    IN_PERSON = "in_person"
    OTHER = "other"

class Stakeholder(BaseModel):
    id: str
    name: str
    role: str
    organization: str | None = None
    expertise: list[str] = []
    decision_authority: list[str] = []          # what they can decide
    consult_on: list[str] = []                  # what they should be consulted on
    contact_preference: ContactChannel = ContactChannel.EMAIL
    contact_handle: str | None = None           # email/slack id/etc
    notes: str | None = None
    influence: Literal["low", "medium", "high"] = "medium"
    interest: Literal["low", "medium", "high"] = "medium"
    created_at: datetime
    updated_at: datetime

class StakeholderMap(BaseModel):
    schema_version: Literal[1] = 1
    stakeholders: list[Stakeholder] = []

class Decision(BaseModel):
    id: str                   # ADR-style: e.g. "ADR-2026-05-01-auth-protocol"
    title: str
    status: Literal["proposed", "accepted", "deprecated", "superseded"]
    context: str
    decision: str
    consequences: str
    alternatives: list[str] = []
    superseded_by: str | None = None
    decided_by: list[str] = []  # stakeholder ids
    created_at: datetime
    updated_at: datetime

class OpenQuestion(BaseModel):
    id: str
    question: str
    why_it_matters: str
    candidate_answerers: list[str] = []   # stakeholder ids
    status: Literal["open", "asked", "answered", "withdrawn"] = "open"
    answer: str | None = None
    blocks: list[str] = []                # work-item ids or artifact ids that depend on this
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    asked_at: datetime | None = None
    answered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

class OpenQuestions(BaseModel):
    schema_version: Literal[1] = 1
    questions: list[OpenQuestion] = []

class System(BaseModel):
    id: str
    name: str
    kind: str                          # e.g. "web app", "API", "DB", "queue"
    owner: str | None = None           # stakeholder id
    status: Literal["live", "planned", "deprecated", "retired"] = "live"
    description: str | None = None
    tech_stack: list[str] = []
    integrations_with: list[str] = []  # other system ids
    notes: str | None = None
    created_at: datetime
    updated_at: datetime

class SystemLandscape(BaseModel):
    schema_version: Literal[1] = 1
    systems: list[System] = []

class Risk(BaseModel):
    id: str
    title: str
    description: str
    likelihood: Literal["low", "medium", "high"]
    impact: Literal["low", "medium", "high"]
    mitigation: str | None = None
    owner: str | None = None
    status: Literal["open", "mitigated", "accepted", "transferred", "closed"] = "open"
    created_at: datetime
    updated_at: datetime

class RiskRegister(BaseModel):
    schema_version: Literal[1] = 1
    risks: list[Risk] = []

class Assumption(BaseModel):
    id: str
    statement: str
    rationale: str | None = None
    validated: bool = False
    validation_method: str | None = None
    invalidated_at: datetime | None = None
    created_at: datetime

class Constraint(BaseModel):
    id: str
    statement: str
    source: str | None = None
    type: Literal["technical", "regulatory", "business", "schedule", "budget", "other"]
    created_at: datetime

class AssumptionsAndConstraints(BaseModel):
    schema_version: Literal[1] = 1
    assumptions: list[Assumption] = []
    constraints: list[Constraint] = []

class Milestone(BaseModel):
    id: str
    title: str
    target_date: date
    status: Literal["future", "in_progress", "achieved", "missed", "cancelled"] = "future"
    notes: str | None = None

class Timeline(BaseModel):
    schema_version: Literal[1] = 1
    milestones: list[Milestone] = []
```

### Repository APIs (`src/praxis/engagement/`)

One repo module per file, all following the same shape:

```python
class GlossaryRepo:
    def __init__(self, engagement_path: Path): ...
    def load(self) -> Glossary: ...
    def add_term(self, term: str, definition: str, **kw) -> GlossaryTerm: ...
    def update_term(self, term: str, **kw) -> GlossaryTerm: ...
    def remove_term(self, term: str) -> None: ...
    def find(self, query: str) -> list[GlossaryTerm]: ...   # case-insensitive substring on term and synonyms
    def get(self, term: str) -> GlossaryTerm | None: ...
```

Similar repos: `StakeholderRepo`, `DecisionRepo`, `OpenQuestionsRepo`,
`SystemLandscapeRepo`, `RiskRepo`, `AssumptionsConstraintsRepo`, `TimelineRepo`.

For `Decision`: each ADR is its own file `engagement/decisions/<id>.md` with
frontmatter (the `Decision` model) plus an extended Markdown body. Use the
file helpers from chunk 03.

For everything else: a single YAML file per type as scaffolded in chunk 02.

Every write emits an audit event:
- `glossary.term.added`, `glossary.term.updated`, `glossary.term.removed`
- `stakeholder.added`, `stakeholder.updated`, `stakeholder.removed`
- `decision.created`, `decision.updated`, `decision.superseded`
- `question.opened`, `question.asked`, `question.answered`, `question.withdrawn`
- etc.

### Tools (registered with chunk-5 registry)

For each repo, expose read tools (non-dangerous) and write tools (dangerous):

```python
@tool("glossary_search", toolset="engagement", dangerous=False)
def glossary_search(ctx, query: str) -> ToolResult: ...

@tool("glossary_get", toolset="engagement", dangerous=False)
def glossary_get(ctx, term: str) -> ToolResult: ...

@tool("glossary_add_term", toolset="engagement", dangerous=True)
def glossary_add_term(ctx, term: str, definition: str,
                      synonyms: list[str] = [], notes: str | None = None) -> ToolResult: ...
# similar for stakeholders, decisions, questions, systems, risks, assumptions, constraints, milestones
```

Total: roughly 25 tools across all engagement model components.

### CLI additions

A subcommand group per repo:

```
praxis engagement glossary add/list/get/remove/search
praxis engagement stakeholder add/list/get/update/remove
praxis engagement decision new/list/show/supersede
praxis engagement question open/list/answer/withdraw
praxis engagement system add/list/show
praxis engagement risk add/list/update/close
praxis engagement timeline add/list/update
```

All CLI write commands accept `--no-audit` to suppress audit events (testing
only; logged at WARN if used).

### Cross-references

Stakeholder IDs referenced from `Decision.decided_by`,
`OpenQuestion.candidate_answerers`, `Risk.owner`, `System.owner` must validate
against the stakeholder map at write time. Raise `EngagementError` on dangling
refs unless `--allow-dangling` is set.

---

## Deliverables

- `src/praxis/engagement/` — models, repos, ID generation, validators
- ~25 tools registered with the chunk-5 registry
- CLI subcommand groups for each repo
- Unit tests per repo: load, add, update, remove, validation errors, atomic writes
- Integration test: full lifecycle of a stakeholder, decision, and open question, including cross-reference validation
- `tests/integration/test_chunk_07.py`
- `docs/concepts/engagement-model.md` (the typed memory pattern, why this vs. flat files)
- `docs/reference/engagement-schema.md` (auto-include from Pydantic models)
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_full_engagement_lifecycle(tmp_engagement):
    glossary = GlossaryRepo(tmp_engagement)
    stakeholders = StakeholderRepo(tmp_engagement)
    decisions = DecisionRepo(tmp_engagement)
    questions = OpenQuestionsRepo(tmp_engagement)

    # Add a glossary term
    t = glossary.add_term("invoice", "A request for payment for goods or services")
    assert t.term == "invoice"
    assert glossary.find("invoice")[0].term == "invoice"

    # Add a stakeholder
    s = stakeholders.add(name="Maria L.", role="Finance Manager",
                         expertise=["accounts payable"],
                         decision_authority=["invoice approval thresholds"])
    assert s.id

    # Open a question that references Maria
    q = questions.open(question="What's the AP threshold for invoices?",
                       why_it_matters="Blocks story BA-101",
                       candidate_answerers=[s.id])
    assert q.status == "open"

    # Reject dangling reference
    with pytest.raises(EngagementError):
        questions.open(question="Bad ref", why_it_matters="test",
                       candidate_answerers=["does-not-exist"])

    # Create a decision
    d = decisions.create(title="Approval threshold = 10k",
                         context="...", decision="...", consequences="...",
                         decided_by=[s.id])
    assert d.id.startswith("ADR-")
    assert (tmp_engagement / ".praxis" / "engagement" / "decisions" / f"{d.id}.md").exists()

    # Audit log has all events
    events = audit_query(tmp_engagement, since=...)
    types = {e["event_type"] for e in events}
    assert "glossary.term.added" in types
    assert "stakeholder.added" in types
    assert "question.opened" in types
    assert "decision.created" in types
```

---

## Explicit non-goals

- No agent loop yet — tools exist but the agent that calls them comes in chunk 8
- No sufficiency gate (chunk 9)
- No work-queue integration (chunk 11) — questions don't yet auto-create work-items

---

## Notes

- ID generation: stakeholders use `<slug-of-name>-<short-uuid>`; decisions use
  `ADR-YYYY-MM-DD-<slug>`; questions/risks/etc. use UUIDv4 short forms.
- All datetimes are UTC-aware. Use `datetime.now(timezone.utc)` everywhere.
- Cross-reference validation happens at the repo level on write; reads do not
  validate (so a corrupted file doesn't crash everything).
- `notes` fields on each model are free-form Markdown to allow rich annotation
  without schema bloat.
- Keep CLI output compact by default; `--json` for machine reading.

---

## Definition of done

- All deliverables present
- Acceptance test passes
- `pytest`, `ruff`, `mypy` green
- Coverage ≥ 80% on engagement subsystem
- `chunks/STATUS.md` updated
