# Connect Browser Harness

## What is it?

The browser harness gives Praxis CDP-level browser automation by delegating
to the [browser-use/browser-harness](https://github.com/browser-use/browser-harness)
project. This is a separate open-source project — Praxis does not bundle it.

## Install

```bash
praxis browser install
```

This will:
1. Clone `browser-use/browser-harness` to `~/.praxis/browser-harness/`
2. Symlink SKILL.md and skill directories into `~/.praxis/skills/`

## Verify

```bash
praxis browser doctor
```

## Custom install path

```bash
praxis browser install --path /opt/browser-harness
praxis browser doctor --path /opt/browser-harness
```

## How it works

The browser harness follows the Hermes pattern:
- Skills are loaded from the symlinked directory
- The agent uses its terminal tool to interact with the harness daemon
- No deep integration code — just filesystem linking

## Requirements

- `git` must be available in PATH
- The harness may require its own dependencies (see its README)
