# Contributing to Praxis

Thanks for your interest in Praxis. This file is intentionally short — most
of the conventions are in `chunks/00-conventions.md`, which you should read
end-to-end before submitting a substantial change.

## TL;DR

```bash
git clone https://github.com/<org>/praxis.git
cd praxis
uv sync --extra dev --extra all
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run mypy src/praxis
```

If all three of the last commands are green and the tests pass, you're good.

## Where the rules live

- **Architecture and principles:** `PROJECT.md`
- **Coding conventions:** `chunks/00-conventions.md`
- **Build status and roadmap:** `chunks/STATUS.md`
- **Per-feature briefs (the build plan):** `chunks/01-skeleton.md` through `chunks/15-skills-library.md`
- **User-facing walkthrough:** `docs/how-to/first-engagement.md` — must remain runnable on a fresh checkout. CI exercises the non-LLM steps on every push (`tests/integration/test_tour_offline.py`); if you change a CLI surface used in the walkthrough, update the doc and the test in the same PR.

## What we accept

- Bug fixes with a regression test
- New skills in the bundled library (follow `docs/how-to/author-a-skill.md`)
- New integrations (subpackage under `src/praxis/integrations/<name>/`, must be optional)
- Documentation improvements
- Performance improvements with before/after measurements

## What we won't merge without discussion

- New top-level subsystems
- Changes to `PROJECT.md` design principles
- Changes to public APIs in `__init__.py` files of any subsystem
- Changes that touch more than one chunk's subsystem in a single PR
- Anything that violates the "integrations are optional" principle (P12)

Open an issue first for these.

## PR checklist

- [ ] Tests added or updated
- [ ] `pytest` passes locally
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `mypy src/praxis` passes
- [ ] Coverage hasn't dropped below 80% on touched subsystems
- [ ] Docs updated where the change is user-visible
- [ ] Conventional Commits used in the PR title

## Code of Conduct

Be kind. Be patient. Assume good faith. Disagree on the substance, not on the person.

## License

By contributing you agree your contribution is licensed under MIT, the same
as the rest of Praxis.
