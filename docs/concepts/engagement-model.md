# Engagement Model

The engagement model is Praxis's **typed structured memory**. It replaces flat
Markdown notes with validated, cross-referenced data that the agent can read,
write, query, and reason over.

## Why typed memory?

A flat-file approach (one big Markdown doc per topic) works for humans but
breaks down for agents:

- **Validation** — a flat file can't enforce that a stakeholder ID referenced
  in a decision actually exists.
- **Querying** — searching a Markdown file for "all open questions assigned to
  Maria" requires parsing prose. The engagement model answers it with
  `questions.list_all(status="open")` plus a filter.
- **Audit** — every write through a repo emits a structured audit event, giving
  a complete history of how the engagement model evolved.
- **Atomic writes** — repos use atomic write patterns (write-tmp, fsync, rename)
  so a crash mid-write never corrupts the engagement state.

## Components

| Component                    | Storage                                    | Repo class                    |
| ---------------------------- | ------------------------------------------ | ----------------------------- |
| Glossary                     | `glossary.yaml`                            | `GlossaryRepo`               |
| Stakeholder map              | `stakeholders.yaml`                        | `StakeholderRepo`             |
| Architecture Decision Records| `decisions/<ADR-ID>.md` (frontmatter + body)| `DecisionRepo`               |
| Open questions               | `open-questions.yaml`                      | `OpenQuestionsRepo`           |
| System landscape             | `system-landscape.yaml`                    | `SystemLandscapeRepo`         |
| Risks                        | `risks.yaml`                               | `RiskRepo`                    |
| Assumptions & constraints    | `assumptions-and-constraints.yaml`         | `AssumptionsConstraintsRepo`  |
| Timeline                     | `timeline.yaml`                            | `TimelineRepo`                |

All files live under `<engagement>/.praxis/engagement/`.

## Cross-references

Stakeholder IDs are referenced from decisions (`decided_by`), open questions
(`candidate_answerers`), risks (`owner`), and systems (`owner`). The repos
validate these references **at write time** — a dangling reference raises
`EngagementError`. Reads do not validate, so corrupted files don't crash
the agent.

## ID generation

- **Stakeholders**: `<slug-of-name>-<8-char-uuid>`
- **Decisions**: `ADR-YYYY-MM-DD-<slug-of-title>`
- **Everything else**: 8-character UUID hex

## Tools

Each repo is exposed through the tool registry (toolset `engagement`). Read
tools are non-dangerous; write tools are marked `dangerous=True` and require
approval.

## CLI

The `praxis engagement` command group mirrors the repos:

```
praxis engagement glossary list/get/search/add/remove
praxis engagement stakeholder list/get/add/update/remove
praxis engagement decision list/show/new/supersede
praxis engagement question list/open/answer/withdraw
praxis engagement system list/add/show
praxis engagement risk list/add/update/close
praxis engagement timeline list/add/update
```
