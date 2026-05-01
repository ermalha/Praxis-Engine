# Initial Prompt for Claude Code

Paste **everything between the BEGIN and END markers** as your very first
message to Claude Code, after you've created the directory and put the spec
files in it. Do not modify it unless you've changed the directory structure.

---

## ⬇️ BEGIN — paste this entire block to Claude Code ⬇️

You are Claude Code, helping me build **Praxis** — an open-source, MIT-licensed,
agent-led framework for IT business analysis. The repository is currently
populated only with specification files; no code exists yet.

The spec files in this directory are:

- `CLAUDE.md` — your contract for how to work in this repo (auto-loaded by you)
- `PROJECT.md` — architecture, design principles, tech stack
- `README.md` — project intro for humans
- `CONTRIBUTING.md` — contributor guide
- `LICENSE` — MIT
- `chunks/00-conventions.md` — cross-cutting patterns and rules
- `chunks/STATUS.md` — build progress tracker
- `PROMPTS.md` — prompts I'll use to drive you across sessions
- `chunks/01-skeleton.md` through `chunks/15-skills-library.md` — fifteen
  self-contained build briefs in dependency order

These specifications are the binding requirements. Anything you remember from
similar projects in your training data is irrelevant where it conflicts with
these files. Do not skim, summarize from priors, or assume.

---

## Your task right now (do NOT start coding)

Work through these steps in order. Stop at the end of step 7 and wait for me.

### Step 1 — Read the always-on context

Read these files in full:

- `CLAUDE.md`
- `PROJECT.md`
- `chunks/00-conventions.md`

### Step 2 — Read the build status and the first chunk

- `chunks/STATUS.md`
- `chunks/01-skeleton.md` (the first chunk we'll execute)

### Step 3 — Confirm reading by quoting

In your reply, quote one short, distinctive line from each of these four
files (`CLAUDE.md`, `PROJECT.md`, `chunks/00-conventions.md`,
`chunks/01-skeleton.md`). One line each, with the file name. This is a check
that you actually read them.

### Step 4 — State the non-negotiables in your own words

In 5–8 bullets, restate the non-negotiables from `CLAUDE.md` in your own
phrasing. This confirms you understand them, not just read them.

### Step 5 — Initialize git

Run `git init`, then immediately run `git add -A && git commit -m "chore:
import praxis specification (pre-build)"`. Show me the resulting commit
hash. This pins the spec as commit #1, so we always have a clean reset
point.

Then create `.gitignore` with the standard Python ignores (venv, pycache,
egg-info, dist, build, .pytest_cache, .ruff_cache, .mypy_cache, .coverage,
coverage.xml) plus `.praxis/`, `.env`, `.envrc`, `.idea/`, `.vscode/`, and
`*.swp`. Commit it: `chore: gitignore`.

### Step 6 — Pre-flight check

Run these commands and show me the output:

```bash
python --version
uv --version
git --version
```

If any are missing or the Python version is below 3.11, stop and tell me —
I'll fix the environment before we proceed.

Also check whether `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or
`OPENROUTER_API_KEY` are set in the environment (just check existence, do
NOT print the values). Tell me which providers are available. This affects
which transport adapter we'll actually exercise during chunk 4 testing.

### Step 7 — Plan chunk 01

Based on `chunks/01-skeleton.md`, produce a plan covering:

1. The files you'll create, in implementation order.
2. The pyproject.toml dependency choices (just confirm they match the brief
   exactly).
3. Any ambiguity in the brief that needs my clarification before you start.

Keep the plan ≤ 30 lines. Do not write any code yet.

After step 7, **stop and wait** for me to say "go on chunk 01". I will
review your plan and either approve it or push back.

---

## Behavioral contract — read this carefully

When we start coding (after my "go"), you will follow `CLAUDE.md` as the
binding contract. The most important rules:

1. **Stay in scope.** A chunk does what its brief says, nothing more. If you
   spot a real bug in earlier code, file it as a separate fix commit before
   continuing — never fold it into the current chunk.
2. **TDD-ish.** Tests are written alongside or before implementation.
3. **Quality gates run before "done".** `pytest`, `ruff check .`,
   `ruff format --check .`, `mypy src/praxis` — all must pass, and you paste
   the actual output, not summaries.
4. **Conventional Commits, one logical change per commit.** The git log is
   the build narrative.
5. **Stop and ask, don't guess.** If a brief is ambiguous or a design choice
   isn't covered by `PROJECT.md`/`00-conventions.md`, stop and ask.
6. **No reflexive deference.** When I'm wrong, say so plainly with reasoning.
   Sycophancy is a defect.
7. **Use public APIs.** Each subsystem under `src/praxis/` exposes its API
   in `__init__.py`. Don't reach into another subsystem's internals.

When something goes wrong (you deviate from a brief, a test reveals a
design problem, a convention conflicts with a brief): stop, run `git status`
and `git diff`, tell me plainly what happened, propose a correction, wait
for my confirmation before continuing.

Begin.

## ⬆️ END — end of paste block ⬆️

---

## What happens after this prompt

Claude Code will work through steps 1–7 and stop. You'll see:

- Quoted lines from the four files (proving real reads, not confabulation)
- The non-negotiables in Claude Code's own words
- An initial git commit hash
- Pre-flight environment output
- A short plan for chunk 01

Review the plan. If it looks right, reply "go on chunk 01". If anything
looks wrong, push back specifically before approving.

For all subsequent chunks, use the **per-chunk kickoff** prompt from
`PROMPTS.md`, replacing `NN` with the chunk number.

For verification at the end of each chunk, use the **completion
verification** prompt from `PROMPTS.md`. Don't skip this — it forces
Claude Code to paste the actual quality-gate output rather than self-report.

If something goes wrong mid-chunk, use the **recovery prompt** from
`PROMPTS.md`.

If you come back after a break, use the **resuming after a break** prompt
from `PROMPTS.md`.

---

## Pre-flight reminders for you

Before you paste the initial prompt:

1. Created the directory? (e.g. `mkdir praxis && cd praxis`)
2. Copied all 21 spec files in (PROJECT.md, README.md, CONTRIBUTING.md,
   LICENSE, CLAUDE.md, INITIAL_PROMPT.md, plus the `chunks/` directory)?
3. Set your API key in the shell? (`export ANTHROPIC_API_KEY=...` or whichever
   provider you'll use first — Anthropic recommended for chunk 4's caching)
4. Decided on review cadence? (Recommended: tight for chunks 1–2, per-chunk
   thereafter)
5. Picked a non-confidential first engagement to dogfood on once chunk 8
   ships? (Save EU Commission OOTS work for after the system is shaken
   down.)

If all five are yes, you're ready. Paste the BEGIN/END block and go.
