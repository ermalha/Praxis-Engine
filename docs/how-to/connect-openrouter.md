# How to Connect to OpenRouter

OpenRouter provides access to many LLM providers through a single API.

## 1. Get an API key

Sign up at [openrouter.ai](https://openrouter.ai) and create an API key.

## 2. Set the environment variable

```bash
export OPENROUTER_API_KEY="sk-or-..."
```

## 3. Configure a profile

```yaml
# ~/.praxis/profiles/default/profile.yaml
name: default
schema_version: 1
default_model_alias: default
model_aliases:
  default:
    schema_version: 1
    provider: openrouter
    model: anthropic/claude-sonnet-4-20250514
    api_key_env: OPENROUTER_API_KEY
```

## 4. Verify

```bash
praxis doctor --profile default
```

## Notes

- Model names use the `provider/model` format (e.g., `anthropic/claude-sonnet-4-20250514`)
- OpenRouter automatically adds `HTTP-Referer` and `X-Title` headers
- Pricing and rate limits vary by model — check the OpenRouter dashboard
