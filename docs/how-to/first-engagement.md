# Your first engagement with Praxis

This walks through the **full Praxis pipeline** end-to-end on a fresh
checkout: install → profile → engagement init → capture state → ask the
agent → sufficiency check → elicit drafts → produce artifact → wake →
TUI. Every command in this document was executed on a cold sandbox
([proof](#how-this-document-stays-honest)) before publication. The
output blocks are the real captured output, lightly truncated where
it would otherwise wrap badly.

If you just want a 30-second chat REPL, see `first-chat.md`. This
document is for the full BA analytical loop.

---

## Prerequisites

- Python 3.11 or 3.12
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- An API key for one of: Anthropic, OpenAI, OpenRouter — or a local
  OpenAI-compatible endpoint (Ollama, vLLM, LM Studio)

You do **not** need Docker, a database server, or any cloud account.

## Install

```bash
git clone https://github.com/ermalha/Praxis-Engine.git
cd Praxis-Engine
uv sync --extra dev --extra all
```

Verify:

```bash
uv run praxis version
# praxis 0.3.1
```

> **Troubleshooting:** if `uv sync` fails with `Resolution failed`,
> make sure you're on uv 0.4+ (`uv --version`). Older uv has different
> extras semantics.

---

## Step 1 — Create a profile

A **profile** binds a name you choose to an LLM configuration
(provider + model + API-key environment variable).

```bash
export OPENAI_API_KEY=sk-...    # your real key
uv run praxis profile create alice \
  --provider openai --model gpt-4.1 --api-key-env OPENAI_API_KEY
```

Actual output:

```
Profile 'alice' created.
  Auto-set as default profile (only profile).
```

<img width="1882" height="619" alt="praxis profile create — terminal output" src="https://github.com/user-attachments/assets/02269fa1-77c7-4a9b-baa6-474f2517fb47" />

Two design choices worth knowing:

- **The API key never lives in config.** Only the environment-variable
  *name* (`OPENAI_API_KEY`) is persisted. `cat ~/.praxis/profiles/alice.yaml`
  is always safe to share.
- **The first profile is auto-set as default.** Later profiles
  (`praxis profile create bob ...`) are also created but not promoted;
  use `praxis profile set-default bob` to switch.

> **Troubleshooting:** if a later command errors with "no default
> profile set," run `praxis profile list` to see what's there, then
> `praxis profile set-default <name>`.

---

## Step 2 — Initialize an engagement

```bash
mkdir my-project && cd my-project
uv run praxis init --name "Acme Loan Intake" --methodology agile
```

Actual output:

```
Engagement 'Acme Loan Intake' initialized at /tmp/my-project
```

The command creates a `.praxis/` directory inside your project root.
This is the **engagement state** — the source of truth for everything
Praxis knows about this project:

```
my-project/
└── .praxis/
    ├── config.yaml                # engagement-level config
    ├── engagement/                # entity files (typed YAML)
    │   ├── assumptions-and-constraints.yaml
    │   ├── decisions/             # one ADR-style file per decision
    │   ├── glossary.yaml
    │   ├── lessons-learned.md
    │   ├── open-questions.yaml
    │   ├── risks.yaml
    │   ├── stakeholders.yaml
    │   ├── system-landscape.yaml
    │   └── timeline.yaml
    ├── artifacts/
    │   └── reports/               # generated artifacts land here
    ├── state/
    │   ├── praxis.db              # SQLite — work queue, sessions
    │   ├── sufficiency-reports/
    │   ├── wake-reports/
    │   └── audit.jsonl            # append-only audit trail
    └── skills/
```

Every file except `praxis.db` is plain text. Run `git init && git add
.praxis/` if you want version control over the engagement.

`config.yaml` looks like this after a fresh init:

```yaml
schema_version: 1
name: Acme Loan Intake
methodology: agile
model_alias: null
integrations: {}
wake_cycle:
  schema_version: 1
  mode: manual
  interval_minutes: 15
  quiet_hours: null
```

---

## Step 3 — Seed the engagement model

Praxis can't analyze anything until you tell it who and what is in
scope. Seed the core entities — even a minimal set unlocks the rest of
the pipeline:

```bash
# Stakeholders — humans who can answer questions
uv run praxis engagement stakeholder add "Alice Chen" "VP of Lending"

# Glossary — domain terms with definitions
uv run praxis engagement glossary add "Member" "A credit-union customer."

# Constraints — non-negotiable boundaries (typed)
uv run praxis engagement constraint add "Must comply with GLBA." regulatory

# Risks — impact + likelihood
uv run praxis engagement risk add "Vendor sandbox delay" \
  "Core banking sandbox takes 2 weeks" -i medium -l medium
```

Each command produces a one-line confirmation and stable ID:

```
Added stakeholder 'Alice Chen' [alice-chen-53ecb508].
Added term 'Member'.
Added constraint [16ac62cb].
Added risk 'Vendor sandbox delay' [de715481].
```

The IDs (`alice-chen-53ecb508`, `16ac62cb`, `de715481`) are stable —
they don't change when content is edited. References from
sufficiency citations, elicit drafts, and audit entries all point to
these IDs.

Add as much as you have. Decisions, assumptions, timeline events,
systems are all available via the same `praxis engagement <entity>
add` pattern. Use `praxis engagement --help` for the full list.

---

## Step 4 — Ask the engagement-aware agent

`ask` is a stateless single-shot question. The `-e .` flag matters: it
primes the LLM with your engagement state before answering, and the
system prompt instructs the model to **flag uncertainty rather than
invent**.

```bash
uv run praxis ask -e . "Should we save partial application progress automatically?"
```

Real output (truncated):

```
Based on the provided facts, there is no existing decision about
saving partial application progress automatically.

Key consideration:
- Regulatory constraint: Must comply with GLBA (Gramm-Leach-Bliley
  Act). This means any data saved—including partial progress—must be
  handled according to GLBA privacy and security requirements.

**Information gap:**
- There is no policy or stakeholder input on whether customers or
  business leaders want or require automatic saving of partial
  application progress.

**Recommendation:**
This should be raised as an open question to Alice Chen (VP of
Lending):

> Should Acme Loan Intake automatically save customers' partial
> application progress, and if so, what requirements or restrictions
> should be in place regarding privacy, security, and customer
> experience?
```

Notice what the agent **did not do**: invent a "yes" or "no" answer.
Instead it pointed at the constraint it knows about (GLBA), named the
gap (no policy/stakeholder input), and proposed a specific question
targeted at the right stakeholder.

> **Troubleshooting:** if `ask` produces a generic answer with no
> engagement awareness, double-check you passed `-e .` — without it,
> `ask` runs stateless and behaves like a plain chat completion.

---

## Step 5 — Sufficiency check before producing an artifact

The **Sufficiency Gate** is Praxis's pre-flight check before any
artifact is generated. It asks: *do we have enough information in the
engagement model to produce this artifact responsibly?*

```bash
uv run praxis check spec "MVP functional requirements for online loan flow" -e .
```

Real output (excerpt):

```
Sufficiency Check: spec
Target: MVP functional requirements for online loan flow
Verdict: INSUFFICIENT
Action: elicit

                          Information Needs
┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Status   ┃ Need             ┃ Blocker  ┃ Have             ┃ Missing          ┃
┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ UNKNOWN  │ Scope boundaries │ Yes      │ -                │ No decisions or  │
│          │                  │          │                  │ constraints      │
│          │                  │          │                  │ define the MVP.  │
│ PARTIAL  │ Business rules   │ Yes      │ Constraint       │ Specific rules   │
│          │                  │          │ 16ac62cb: GLBA.  │ are not defined. │
│ UNKNOWN  │ Data model       │ No       │ -                │ No data model.   │
└──────────┴──────────────────┴──────────┴──────────────────┴──────────────────┘

Elicitation targets: alice-chen-53ecb508

Next: run praxis elicit --latest -e . to convert these gaps into
open questions and stakeholder-targeted drafted emails.
```

Read the table column by column:

- **Status:** `KNOWN` / `PARTIAL` / `UNKNOWN` per information need.
- **Need:** named, in the agent's own words.
- **Blocker:** does this gap *block* producing the artifact? (`Yes`/`No`)
- **Have:** what in the engagement model contributes, by stable ID. The
  `Constraint 16ac62cb: GLBA` reference points back to the constraint
  we created in step 3.
- **Missing:** what's still required.

The gate ends with a `Next:` line telling you the recommended action.
This is **not** a UI hint — it's the gate's explicit `recommended_action`
field rendered as guidance.

> **Troubleshooting:** if `check` errors with "no transport configured,"
> your default profile lacks a model alias. Run
> `praxis profile show alice` to inspect; you can also pass
> `--profile alice` explicitly.

---

## Step 6 — Elicit drafts for the gaps

```bash
uv run praxis elicit --latest -e .
```

For each unknown/partial information need, `elicit`:

1. Generates a draft message (subject + body) targeted at a specific
   stakeholder.
2. Registers a corresponding **open question** in the engagement model.
3. Optionally queues a work item for the human (you) to send the draft.

Real output (excerpt):

```
                          Elicitation Drafts
┏━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━┓
┃ #   ┃ Priority ┃ Mode            ┃ Target     ┃ Channel  ┃ Needs         ┃
┡━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━┩
│ 1   │ CRITICAL │ meeting_request │ Alice Chen │ email    │ Scope, Actors │
└─────┴──────────┴─────────────────┴────────────┴──────────┴───────────────┘

Draft 1
Subject: Request for Meeting: Clarification Needed on MVP Online Loan
Flow Requirements

Hi Alice,

I am reviewing the current documentation for the MVP functional
requirements of the online loan flow and have identified several
areas where further clarification is needed to proceed effectively:

- Defining the boundaries of what is in and out of scope for the MVP
- Identifying all user roles and system actors involved
- Specifying the key business rules for loan eligibility, approval...

Could we schedule a meeting to discuss these points in detail?

Thank you,
[Your Name]
```

Praxis does **not** send the message — you do. Sending email is a
human-commit boundary. Edit the draft, send via your normal channel,
then record the answer with `praxis engagement question answer <id>
"<answer text>"`.

After running `elicit`, six new open questions are auto-registered
(one per information need). Verify with `praxis status -e .`.

---

## Step 7 — Generate the artifact

Even though the gate said `insufficient`, you can still generate the
artifact — but Praxis will produce a **scope brief with the gaps
explicitly named**, and bind it to the sufficiency report so anyone
reading the artifact can see exactly which gaps remain.

```bash
uv run praxis artifact generate scope-brief -e . --json
```

Real output (pretty-printed for the doc):

```json
{
  "schema_version": 1,
  "artifact_kind": "scope-brief",
  "created_at": "2026-05-23T08:27:45Z",
  "path": "/tmp/my-project/.praxis/artifacts/reports/scope-brief-20260523T082745Z.md",
  "content": "MVP Scope Brief\n...",
  "sufficiency_verdict": "insufficient",
  "sufficiency_report_path": "/tmp/my-project/.praxis/state/sufficiency-reports/568d2204082c.json"
}
```

The artifact itself (in `path`) is Markdown:

```markdown
MVP Scope Brief
Project: Acme Loan Intake
Methodology: Agile
Stakeholder: Alice Chen (VP of Lending)

---

**In-Scope:**
Given the current information, precise in-scope functionality is
unknown. Awaiting clarification on:
- Processes/features surrounding loan intake for credit-union members.

**Constraints:**
- Regulatory: Must comply with GLBA (Gramm-Leach-Bliley Act).

**Risks:**
- Medium/Medium: Delay if vendor's core banking sandbox is unavailable
  for two weeks.

**Open Questions:**
- [Critical] What are the precise scope boundaries?
- [Critical] Who are the users/actors that will interact with the system?
...

---

**Artifact source note:**
This MVP scope brief was generated from the persisted Acme Loan Intake
engagement model. All content is strictly based on known engagement
facts; unknowns and assumptions are marked explicitly.
```

The `sufficiency_report_path` field is the auditability claim made
concrete: anyone reading the artifact can click through to the exact
sufficiency-report JSON that justified producing it.

> **Troubleshooting (RW-019 / D-047):** `--json | jq` now works
> cleanly. If you ever see structlog debug output mixed into the
> JSON, that's a regression — please file an issue. To opt into debug
> output (which goes to stderr, not stdout): set `PRAXIS_DEBUG=1`.

---

## Step 8 — Daily status snapshot

```bash
uv run praxis status -e .
```

Real output:

```
Engagement Status: Acme Loan Intake
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric                          ┃ Value                                      ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Stakeholders                    │ 1                                          │
│ Glossary terms                  │ 1                                          │
│ Decisions                       │ 0                                          │
│ Constraints                     │ 1                                          │
│ Risks                           │ 1                                          │
│ Open questions                  │ 6 / 6                                      │
│ Human work-items (active/total) │ 0 / 0                                      │
│ Agent work-items (active/total) │ 0 / 0                                      │
│ Last sufficiency                │ insufficient (2026-05-23T08:27:08Z)        │
└─────────────────────────────────┴────────────────────────────────────────────┘

Top critical open questions:
  - [f2e55304] Scope boundaries — what is in scope and what is out of scope?
  - [c7ec85b5] Actors — who interacts with the system?
  - [e9b3a476] Business rules governing the domain logic
```

`6 / 6` open questions = `<unanswered> / <total>`. Run this first
thing each morning — it's the "where are we" command.

---

## Step 9 — Wake cycle

`wake` is the proactive loop that makes Praxis different from a chat
agent: scheduled, idempotent, state-diff-aware.

```bash
uv run praxis wake -e .
```

Real output:

```
Wake Report (manual)
  Duration: 2026-05-23 08:28:08 → 2026-05-23 08:28:08

  Tasks considered: 1
  Tasks executed: 1
    - Re-evaluate insufficient artifact: spec — MVP functional
      requirements for online loan flow
  Work-items created: wi-6930dcfd82
```

The wake cycle saw the recent insufficient sufficiency report from
step 5 and auto-enqueued an agent follow-up task. Run `wake` again
immediately and it'll do **nothing** — work items are deduped by
stable key. This is intentional: scheduled wake cycles (cron, launchd)
don't pile up redundant tasks.

To schedule wake, add a cron entry like:

```cron
# Every weekday at 6 AM, wake the engagement
0 6 * * 1-5  cd /path/to/my-project && /path/to/uv run praxis wake -e .
```

---

## Step 10 — The TUI

```bash
uv run praxis tui -e .
```

This is interactive. Press number keys 1–9 to switch screens, `r` to
refresh, `w` to trigger a wake from inside the TUI, `q` to quit. See
`use-the-tui.md` for keybindings.

For automation or CI, use `--smoke` to verify the TUI loads without
opening it:

```bash
uv run praxis tui --smoke -e .
```

Real output:

```json
{"status": "ok", "screens_loaded": true, "initial_screen": "queue", "available_screens": ["queue", "conversation", "engagement", "audit", "backlog", "config", "setup", "priorities", "artifact_viewer"]}
```

---

## What's next

You've completed the full Praxis pipeline once. The engagement model
is now ready to grow. From here:

- **Add real decisions.** As you make calls with stakeholders, record
  them: `praxis engagement decision create "..."`. Decisions carry the
  most weight in the sufficiency gate.
- **Answer open questions.** As stakeholders respond:
  `praxis engagement question answer <id> "<answer>"`. The next
  `check` will reflect the new information.
- **Schedule wake.** Cron, launchd, or a GitHub Action. The agent
  works overnight; you wake up to a prioritized queue.
- **Open the TUI.** Once the engagement has shape, the TUI is the
  daily-driver workspace. `priorities` (key 8) is the "what to work
  on now" view.

## How this document stays honest

The cold-run that produced every output block above is reproducible:

```bash
# Sandbox setup
rm -rf /tmp/praxis-cold && mkdir -p /tmp/praxis-cold/.praxis-home /tmp/praxis-cold/eng
cd /tmp/praxis-cold/eng

# Env
export PRAXIS_HOME=/tmp/praxis-cold/.praxis-home
export OPENAI_API_KEY=sk-...    # your key

# Run the 10 steps in order, capturing each command's stdout.
```

CI verifies the **non-LLM steps** of this walkthrough on every push
(`tests/integration/test_tour_offline.py`). If you find a step that
deviates from what's documented here, please file an issue — the
document is intended to track reality, not the other way around.
