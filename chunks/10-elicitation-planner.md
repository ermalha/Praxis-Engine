# Chunk 10 — Elicitation Planner

**Phase:** Praxis Distinctives | **Estimated effort:** 4 hours | **Dependencies:** 01–09

---

## Context

When the Sufficiency Gate verdict is `INSUFFICIENT` or `PARTIAL`, the agent
must figure out **what to ask, whom to ask, and how to ask**. This is the
Elicitation Planner. It produces draft elicitation work-items that the
human operator (in chunk 11) can review and dispatch.

The Planner closes the loop between "I don't know X" and "Maria knows X and
prefers Teams; here's the message."

---

## Scope

### Models (`src/praxis/core/elicitation.py`)

```python
class ElicitationMode(StrEnum):
    DIRECT_QUESTION = "direct_question"        # one-line ask
    EMAIL = "email"                            # full email draft
    MEETING_REQUEST = "meeting_request"        # need a sync conversation
    WORKSHOP = "workshop"                      # multi-stakeholder, agenda needed
    DOCUMENT_REQUEST = "document_request"      # ask for a doc/artifact
    SHADOWING = "shadowing"                    # observe a process

class ElicitationDraft(BaseModel):
    schema_version: Literal[1] = 1
    target_stakeholder_id: str
    target_stakeholder_name: str               # denormalized for clarity
    channel: ContactChannel
    mode: ElicitationMode
    priority: Literal["critical", "high", "medium", "low"]
    rationale: str                             # why this person, why now
    related_info_needs: list[str]              # need.need texts from sufficiency report
    blocks: list[str]                          # artifact ids / question ids that depend on this
    drafted_subject: str | None = None         # for emails
    drafted_body: str                          # the actual question / message
    expected_response_format: str              # "free text" | "yes/no" | "list of items" | etc
    followup_after_days: int = 3
    deadline: datetime | None = None
```

### The Planner (`src/praxis/core/elicitation.py`)

```python
def plan_elicitations(
    sufficiency_report: SufficiencyReport,
    *,
    agent: Agent,
    max_drafts: int = 5,
) -> list[ElicitationDraft]: ...
```

Algorithm:
1. Collect all info needs with status `UNKNOWN` or `PARTIAL`.
2. Group by candidate stakeholder (from `candidate_sources`).
3. For each stakeholder group, ask the LLM to:
   - Choose the right channel based on the stakeholder's `contact_preference`
   - Choose a mode based on (a) number of needs to address, (b) complexity, (c) priority
   - Draft the message in that mode (subject + body for email, agenda for workshop, etc.)
   - Order priority by blocker status and downstream blocks
4. For each draft, also auto-create or update the corresponding `OpenQuestion`
   entries in the engagement model so they're tracked even before the message
   is sent.
5. Return a list of `ElicitationDraft` (do NOT yet enqueue them as work-items;
   that's chunk 11).

### Stakeholder selection helpers

When the sufficiency report's candidate sources don't include a stakeholder
(or the suggested ones don't exist), fall back to:

1. Stakeholders with matching `expertise` keywords (token overlap with the need)
2. Stakeholders with `decision_authority` matching the artifact target
3. The engagement's primary sponsor / project owner (from engagement config)
4. If nothing matches: produce a special draft with `target_stakeholder_id="UNKNOWN"`
   and the body asking the human operator to identify the right person.

### Drafting templates (`src/praxis/core/elicitation_templates/`)

YAML templates per (mode × channel) combination provide the LLM with a
"good shape" to imitate. v1 templates:

- `email_direct_question.yaml`
- `email_meeting_request.yaml`
- `email_document_request.yaml`
- `chat_direct_question.yaml`  (Teams/Slack)
- `meeting_workshop_agenda.yaml`

Each template has placeholders the LLM fills in (recipient name, context,
specific needs, due date).

### Tool exposure

```python
@tool("plan_elicitations_for_report", toolset="meta", dangerous=False)
def plan_elicitations_for_report(ctx, sufficiency_report_id: str,
                                 max_drafts: int = 5) -> ToolResult: ...
```

### CLI

```
praxis elicit <sufficiency-report-id>
praxis elicit --latest
```

Prints the drafts (rich tables + body previews). Drafts saved to
`<engagement>/.praxis/state/elicitation-drafts/<id>.json`. Chunk 11 then
ingests these into the work-queue.

---

## Deliverables

- `src/praxis/core/elicitation.py`
- `src/praxis/core/elicitation_templates/` (5 templates)
- Stakeholder selection helpers in `src/praxis/core/stakeholder_match.py`
- Tool: `plan_elicitations_for_report`
- CLI: `praxis elicit`
- Auto-creation of OpenQuestion entries (with status="open" and `candidate_answerers` linking to the chosen stakeholder)
- Tests:
  - Selection picks the right stakeholder by expertise match
  - Selection falls back to UNKNOWN when nothing matches
  - Mode selection: 1 need → DIRECT_QUESTION; 5+ needs across topics → WORKSHOP; complex single topic → MEETING_REQUEST
  - Channel chosen from stakeholder's preference
  - Drafts persisted to disk
  - OpenQuestion entries created and linked
- `tests/integration/test_chunk_10.py` — full flow from sufficiency report → elicitation drafts → open questions in engagement model
- `docs/concepts/elicitation-planner.md`
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_planner_produces_targeted_drafts(tmp_engagement, mock_anthropic):
    StakeholderRepo(tmp_engagement).add(
        name="Maria L.", role="AP Manager", id="maria-l-x1",
        expertise=["accounts payable", "invoice approval"],
        decision_authority=["approval thresholds"],
        contact_preference=ContactChannel.EMAIL,
        contact_handle="maria.l@example.com",
    )

    report = SufficiencyReport(
        artifact_kind="user-story",
        artifact_target="Invoice approval workflow",
        information_needs=[
            InfoNeed(need="What's the AP threshold?", status="unknown",
                     blocker=True,
                     candidate_sources=[CandidateSource(kind="stakeholder",
                                                         ref="maria-l-x1",
                                                         rationale="AP Manager")]),
        ],
        verdict="insufficient", recommended_action="elicit",
        elicitation_targets=["maria-l-x1"],
        ...
    )

    mock_anthropic.queue_response(json=[{
        "target_stakeholder_id": "maria-l-x1",
        "target_stakeholder_name": "Maria L.",
        "channel": "email",
        "mode": "direct_question",
        "priority": "high",
        "rationale": "Single direct question; AP Manager owns this.",
        "related_info_needs": ["What's the AP threshold?"],
        "blocks": [],
        "drafted_subject": "Quick question on invoice approval thresholds",
        "drafted_body": "Hi Maria, ... [draft body] ...",
        "expected_response_format": "free text",
        ...
    }])

    drafts = plan_elicitations(report, agent=make_agent(tmp_engagement))
    assert len(drafts) == 1
    d = drafts[0]
    assert d.target_stakeholder_id == "maria-l-x1"
    assert d.channel == ContactChannel.EMAIL
    assert d.mode == ElicitationMode.DIRECT_QUESTION

    # Open question was created
    qs = OpenQuestionsRepo(tmp_engagement).load().questions
    assert any("threshold" in q.question.lower() for q in qs)
    assert "maria-l-x1" in qs[0].candidate_answerers
```

---

## Explicit non-goals

- No work-queue enqueueing yet (chunk 11)
- No actually-sending of messages — drafts only
- No followup automation — that's a future enhancement

---

## Notes

- The Planner is the most "LLM-creative" component so far. The templates are
  there to constrain its output style without making it formulaic.
- Stakeholder selection should be conservative: when in doubt, fall back to
  UNKNOWN and let the human choose. Wrong-recipient elicitations are a
  trust-killer.
- `OpenQuestion.blocks` is updated when an elicitation is tied to a specific
  artifact or work-item; chunk 11 adds the work-item link.

---

## Definition of done

- All deliverables present
- Acceptance test passes
- `pytest`, `ruff`, `mypy` green
- `chunks/STATUS.md` updated
