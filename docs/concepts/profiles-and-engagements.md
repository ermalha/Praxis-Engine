# Profiles and Engagements

Praxis organises work into two complementary scopes: **profiles** and
**engagements**.

## Profiles

A profile is a user-identity scope. It lives under
`~/.praxis/profiles/<name>/` and stores:

- **Model aliases** — named LLM presets (provider, model, API key env var,
  timeout, headers).
- **Default model alias** — which alias to use when none is specified.
- **Display name** — optional human-readable label.

Create a profile:

```bash
praxis profile create alice
```

List profiles:

```bash
praxis profile list
```

The active profile is determined by:

1. `PRAXIS_PROFILE` environment variable (highest precedence)
2. `default_profile` in `~/.praxis/config.yaml`
3. Falls back to `"default"`

Profile names must match `[a-z0-9_-]+`.

## Engagements

An engagement is a project, programme, or workstream that Praxis is helping
analyse. It maps to a `.praxis/` directory inside a project folder.

Initialise an engagement:

```bash
praxis init ./my-project --name "My Project" --methodology agile
```

This creates the full directory scaffold:

```
my-project/.praxis/
├── config.yaml
├── engagement/
│   ├── glossary.yaml
│   ├── stakeholders.yaml
│   ├── decisions/
│   ├── open-questions.yaml
│   ├── assumptions-and-constraints.yaml
│   ├── system-landscape.yaml
│   ├── timeline.yaml
│   ├── risks.yaml
│   └── lessons-learned.md
├── artifacts/
│   ├── stories/
│   ├── specs/
│   ├── models/
│   ├── matrices/
│   └── reports/
├── state/
└── skills/
```

Praxis discovers the engagement by walking up from the current directory,
similar to how Git finds `.git/`.

## Configuration layering

Configuration resolves in precedence order (lowest to highest):

1. **Pydantic defaults** — baked into the model definitions.
2. **Global config** — `~/.praxis/config.yaml`
3. **Profile config** — `~/.praxis/profiles/<name>/profile.yaml`
4. **Engagement config** — `<project>/.praxis/config.yaml`
5. **Environment variables** — `PRAXIS_*` prefixed vars.
6. **CLI flags** — passed at invocation time.

View the resolved effective config:

```bash
praxis config show --json
```

## Supported methodologies

Engagements can declare a methodology: `agile`, `scrum`, `kanban`,
`waterfall`, `hybrid`, or `none` (default). The methodology is configuration,
not hard-coded behaviour — it influences skill selection and artifact
templates but does not constrain the agent's approach.
