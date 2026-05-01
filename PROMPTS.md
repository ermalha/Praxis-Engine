# Claude Code Prompts

Paste-ready prompts for driving the Praxis build with Claude Code. The
structure of these prompts is itself an error-rate optimization — read the
notes at the bottom before modifying them.

---

## 1. Repo bootstrap (run once, before chunk 01)

Run this in an empty directory after copying the spec package files
(`PROJECT.md`, `README.md`, `CONTRIBUTING.md`, and the `chunks/` directory)
into it.

```
You are starting a new open-source project called Praxis. The repository is
currently empty except for these specification files:

- PROJECT.md            (always-on architecture and principles)
- README.md             (project intro)
- CONTRIBUTING.md       (contributor guide pointing at chunks/00-conventions.md)
- chunks/               (15 build briefs + STATUS.md + 00-conventions.md)

Your task right now: do NOT start building. Instead:

1. Read PROJECT.md in full.
2. Read chunks/00-conventions.md in full.
3. Read chunks/STATUS.md.
4. Read chunks/01-skeleton.md (the first chunk we'll execute).
5. Confirm in your reply that you have read all four files by quoting one
   key principle from each.
6. List the files you will create for chunk 01 and the order you'll create
   them in.
7. Stop. Do not write any code yet. Wait for me to say "go".

Do not skim. Do not summarize from training-data assumptions. Read the actual
files. They contain the binding requirements; anything you remember from
similar projects is irrelevant if it conflicts with these files.
```

---

## 2. Per-chunk kickoff (template — fill in NN)

After bootstrap, run this once per chunk in order:

```
We are now executing chunk NN of the Praxis build. Your task:

1. Read PROJECT.md and chunks/00-conventions.md if you haven't read them in
   this session. (Always-on context.)
2. Read chunks/NN-<name>.md in full. This is the brief for this chunk.
3. Read every chunks/MM-<name>.md listed under "Dependencies" in the brief
   that you haven't already implemented in this session.
4. Examine the existing code under src/praxis/ to ground yourself in what's
   already there. Note the public APIs in __init__.py files of the
   subsystems you'll touch.
5. Write a SHORT plan (max 30 lines) covering:
   - The files you'll create or modify, in implementation order
   - The test cases you'll write (bullet list, brief)
   - Any ambiguities in the brief that need clarification before you start
6. Stop and show me the plan. Wait for my "go" before writing code.

When I say "go":

- Implement the chunk in test-first order where practical.
- Follow chunks/00-conventions.md exactly. Do not invent new patterns.
- Use the public API of subsystems from earlier chunks; do not reach into
  their internals.
- Run `pytest`, `ruff check .`, `ruff format --check .`, and
  `mypy src/praxis` before declaring the chunk done. They must all pass.
- Run the chunk's acceptance test (tests/integration/test_chunk_NN.py)
  and show me the output.
- Update chunks/STATUS.md (check the box).
- Update any docs the brief specifies.
- Commit using Conventional Commits, one logical change per commit.
- Tell me explicitly: "Chunk NN done. Ready for chunk NN+1."

If you find yourself wanting to do something the brief doesn't cover, STOP
and ask me. Do not silently expand scope. Adding code that's "obviously
needed for later" is the single most common source of bugs in this kind of
build — resist it.

If a deliverable in the brief is impossible or conflicts with another
chunk's deliverable, STOP and tell me. Do not paper over it.
```

---

## 3. Mid-chunk recovery (when something goes wrong)

If Claude Code goes off the rails — invents a pattern, edits a file outside
the chunk's scope, skips tests — paste this:

```
Stop. Something has gone wrong. Reset:

1. Show me `git status` and `git diff` since the start of this chunk.
2. Re-read chunks/00-conventions.md and chunks/NN-<name>.md.
3. Identify, specifically, where you deviated from the brief or
   conventions. Quote the relevant lines from the brief and from your
   diff.
4. Propose how to undo or correct the deviation.

Do not make any further changes until I confirm the correction plan.
```

---

## 4. Chunk completion verification

Before moving to the next chunk, paste this to force a self-audit:

```
Before we move to chunk NN+1, audit chunk NN:

1. Run pytest. Paste the output.
2. Run ruff check . and ruff format --check . Paste the output.
3. Run mypy src/praxis. Paste the output.
4. Open chunks/NN-<name>.md and walk through the Deliverables section
   line by line. For each deliverable, point to the file or commit that
   delivers it. If anything is missing or partial, say so plainly.
5. Open the "Definition of done" section of chunks/NN-<name>.md and
   confirm each bullet point is met.
6. Show me `git log --oneline` since the chunk started. Confirm the
   commit messages follow Conventional Commits.

Only after all six checks pass do I want to hear "ready for chunk NN+1".
```

---

## 5. Resuming after a break

If you're returning after hours or days away, paste this first:

```
We are mid-build on Praxis. Re-orient yourself:

1. Read PROJECT.md.
2. Read chunks/00-conventions.md.
3. Read chunks/STATUS.md to see what's done and what's next.
4. Read the brief for the next unchecked chunk.
5. Run `git log --oneline -20` and tell me what was last committed.
6. Run pytest and tell me if everything still passes.
7. Tell me which chunk we should execute next.

Do not start coding. Wait for me to say "go on chunk NN".
```

---

## Notes on prompt design (why these work)

**Forced reading.** Every prompt requires reading the actual files. The
"quote one principle from each" check in the bootstrap prompt is a
deliberate token-burn that forces real ingestion vs. confabulation from
training data.

**Plan-then-act.** Every chunk gets a plan checkpoint before code is
written. This catches misunderstandings of the brief while they're cheap to
fix. The plan is short (30 lines) so reviewing it isn't a chore.

**Explicit scope guardrails.** The "do not silently expand scope" line is
the single most important defensive instruction. Without it, agents
routinely "helpfully" add code that breaks future chunks.

**Quality gates as commands, not aspirations.** The audit prompt forces
pasted output rather than self-reports. "Does mypy pass?" → "Run mypy and
paste the output." Different question.

**Recovery prompt as standard tool.** When things go wrong, the recovery
prompt does NOT scold or restart. It diagnoses and corrects. This keeps the
session productive after a deviation.

**Conventional Commits.** Force these from chunk 01 onward. The git log
becomes a readable build narrative, useful when something goes wrong three
chunks later and you need to find when a regression entered.

**No "let me just also fix X."** A chunk does what its brief says, nothing
more. If you find a real bug in earlier code, file it as a separate fix
commit BEFORE starting the next chunk. The chunks must remain bounded.

---

## Optional: a "discovery" prompt for adding a new chunk

If during the build you decide to add chunk 16 (or split a chunk), use this
to draft the brief:

```
We need a new chunk. Draft chunks/<NN>-<name>.md following the same
structure as the existing chunks. The chunk should:

- Goal: <one paragraph>
- Fit in phase: <Foundations | Agent Core | Praxis Distinctives | Real-World Surface>
- Dependencies: <list>

Use the template structure: Context, Scope, Deliverables, Acceptance Test,
Explicit non-goals, Notes, Definition of done.

The brief should be self-contained — reading just it (plus PROJECT.md and
chunks/00-conventions.md) should be enough to execute it without reading
other chunks beyond the listed dependencies.

Show me the draft. Don't write any code yet.
```
