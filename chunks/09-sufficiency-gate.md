# Chunk 09 — Sufficiency Gate

**Phase:** Praxis Distinctives | **Estimated effort:** 4–5 hours | **Dependencies:** 01–08

---

## Context

This is the first of the three components that make Praxis distinct from a
chat agent. Before producing any artifact (a story, spec, decision matrix,
report), the agent runs a typed self-check: **do I have enough information
to do this well?**

The Sufficiency Gate is structured (the agent doesn't just "decide" — it
produces a typed artifact you can inspect), explicit (the verdict is
`SUFFICIENT` / `PARTIAL` / `INSUFFICIENT`, not a vague vibe), and grounded
(it pulls from the engagement model rather than relying on chat history).

This chunk delivers the Gate as both an internal API and as a tool the agent
calls (and a CLI command for humans to invoke directly).

---

## Scope

### Models (`src/praxis/core/sufficiency.py`)

```python
class InfoNeedStatus(StrEnum):
    KNOWN = "known"             # already in engagement model / artifacts / history
    PARTIAL = "partial"         # some info but incomplete
    UNKNOWN = "unknown"         # nothing yet

class CandidateSource(BaseModel):
    kind: Literal["stakeholder", "artifact", "external", "registry"]
    ref: str                    # stakeholder id, artifact path, URL, etc
    rationale: str

class InfoNeed(BaseModel):
    need: str
    status: InfoNeedStatus
    have: str | None = None     # what we know so far
    missing: str | None = None  # what's still missing
    blocker: bool               # if true, output cannot proceed without this
    candidate_sources: list[CandidateSource]

class SufficiencyVerdict(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"

class SufficiencyReport(BaseModel):
    schema_version: Literal[1] = 1
    artifact_kind: str          # e.g. "user-story", "decision-matrix", "spec"
    artifact_target: str        # natural-language description of what's being produced
    information_needs: list[InfoNeed]
    verdict: SufficiencyVerdict
    recommended_action: Literal["produce", "elicit", "produce_with_caveats"]
    reasoning: str              # short explanation
    elicitation_targets: list[str] = []   # stakeholder ids if elicit
    generated_at: datetime
    by: Literal["agent", "human"]
```

### The Gate (`src/praxis/core/sufficiency.py`)

```python
def run_sufficiency_gate(
    artifact_kind: str,
    artifact_target: str,
    *,
    agent: Agent,
    extra_context: str | None = None,
) -> SufficiencyReport: ...
```

Internally:
1. Build a focused sub-prompt asking the LLM to:
   - Enumerate the information needs for the given artifact kind
   - For each, classify status (KNOWN/PARTIAL/UNKNOWN) by checking the engagement model
   - For UNKNOWN/PARTIAL needs, propose candidate sources (preferring stakeholders from the stakeholder map)
   - Produce a verdict and reasoning
2. Constrain the response to JSON matching `SufficiencyReport` (use response_format if supported, else parse-and-validate).
3. Validate cross-references (stakeholder ids exist).
4. Persist the report to `<engagement>/.praxis/state/sufficiency-reports/<uuid>.json`.
5. Emit `sufficiency.evaluated` audit event.

The sub-prompt uses the same model as the main agent by default but allows
override via `profile.sufficiency_gate_model_alias` (a cheaper model is fine).

### Heuristic helpers (`src/praxis/core/sufficiency_helpers.py`)

For known artifact kinds, pre-populate likely information needs from a
template library so the LLM has a strong prior. v1 templates:

- `user-story` — actor identity, action goal, value/why, acceptance criteria pattern, business rules, NFRs
- `decision-matrix` — options, criteria, weights, evaluator, decision authority
- `spec` — scope boundaries, in/out of scope, actors, business rules, data model, integrations, NFRs
- `process-model` — start/end events, actors, decision points, exception flows, system interactions
- `risk-register-entry` — likelihood basis, impact basis, owner, mitigation feasibility

Each template lives in `src/praxis/core/sufficiency_templates/<kind>.yaml`.

### Tool exposure

```python
@tool("sufficiency_check", toolset="meta", dangerous=False)
def sufficiency_check(ctx, artifact_kind: str, artifact_target: str,
                      extra_context: str | None = None) -> ToolResult: ...
```

The agent SHOULD call this before any artifact write (this becomes a strong
recommendation in the system prompt updated in this chunk). When the agent
calls a "produce artifact" type tool (added in chunks 14 and beyond), the
tool layer can also invoke the gate automatically and refuse if the verdict
is INSUFFICIENT — that policy is configurable via
`profile.enforce_sufficiency_gate: bool = True`.

### CLI

```
praxis check <artifact-kind> "<target description>"
praxis check user-story "Story for invoice approval workflow"
```

Output: pretty-printed report, with table of info needs, verdict highlighted.
`--json` flag supported.

---

## Deliverables

- `src/praxis/core/sufficiency.py` — models, runner
- `src/praxis/core/sufficiency_helpers.py` — template loader
- `src/praxis/core/sufficiency_templates/` — at least 5 YAML templates
- Tool: `sufficiency_check`
- CLI: `praxis check`
- Update agent system prompt builder to mention the Gate as a default expectation
- Tests:
  - Template loading and merge with LLM-produced needs
  - JSON-mode parsing with validation errors
  - Cross-reference validation (rejected when stakeholder ids don't exist)
  - SUFFICIENT verdict when all needs KNOWN
  - INSUFFICIENT verdict when blocker UNKNOWN
  - PARTIAL when no blockers UNKNOWN but some needs are PARTIAL
  - Report persisted to disk with correct schema
  - Audit event emitted
  - Enforcement: when `enforce_sufficiency_gate=true`, a "produce" tool refuses on INSUFFICIENT
- `tests/integration/test_chunk_09.py`
- `docs/concepts/sufficiency-gate.md` — the principle, the format, examples
- `docs/reference/sufficiency-templates.md`
- Update `chunks/STATUS.md`

---

## Acceptance test

```python
def test_sufficiency_gate_blocks_on_missing_blocker(tmp_engagement, mock_anthropic):
    mock_anthropic.queue_response(json={
        "artifact_kind": "user-story",
        "artifact_target": "Invoice approval workflow",
        "information_needs": [
            {"need": "Approval thresholds",
             "status": "unknown",
             "blocker": True,
             "candidate_sources": [
                 {"kind": "stakeholder", "ref": "maria-l-x1", "rationale": "AP Manager"}
             ]
            }
        ],
        "verdict": "insufficient",
        "recommended_action": "elicit",
        "reasoning": "Threshold value missing",
        "elicitation_targets": ["maria-l-x1"],
        ...
    })
    StakeholderRepo(tmp_engagement).add(name="Maria L.", role="AP Manager", id="maria-l-x1")

    agent = make_agent(tmp_engagement)
    report = run_sufficiency_gate("user-story", "Invoice approval workflow", agent=agent)
    assert report.verdict == "insufficient"
    assert report.recommended_action == "elicit"
    assert "maria-l-x1" in report.elicitation_targets

    # Cross-ref validation: bad target id rejected
    mock_anthropic.queue_response(json={..., "elicitation_targets": ["nope"], ...})
    with pytest.raises(SufficiencyError):
        run_sufficiency_gate(...)

def test_cli_check_command(tmp_engagement, mock_anthropic):
    result = runner.invoke(app, ["check", "user-story", "Test target",
                                 "--engagement", str(tmp_engagement)])
    assert "verdict" in result.stdout.lower()
```

---

## Explicit non-goals

- No automatic elicitation work-item creation yet (chunks 10 + 11)
- No "produce" tools that consume sufficiency reports (those come in later chunks)
- The Gate doesn't yet tie into the proactive wake cycle (chunk 12)

---

## Notes

- The Sufficiency Gate is the moment the agent's analytical posture shows.
  It's worth making the output beautiful — humans will read these.
- For artifact kinds not in the template library, the LLM is asked to enumerate
  needs from scratch. Document this as the default fallback.
- The Gate is intentionally cheap (a single LLM call with bounded output). It
  should be invoked liberally.
- Reports are immutable once written. Re-running the Gate creates a new report.

---

## Definition of done

- All deliverables present
- Acceptance test passes
- `praxis check` produces useful output against a real engagement
- `pytest`, `ruff`, `mypy` green
- `chunks/STATUS.md` updated
