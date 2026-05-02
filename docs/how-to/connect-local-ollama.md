# How to Connect to a Local Ollama Server

Ollama runs LLMs locally and exposes an OpenAI-compatible API.

## 1. Install and start Ollama

```bash
# macOS
brew install ollama
ollama serve

# Pull a model
ollama pull llama3.1
```

## 2. Configure a profile

```yaml
# ~/.praxis/profiles/default/profile.yaml
name: default
schema_version: 1
default_model_alias: default
model_aliases:
  default:
    schema_version: 1
    provider: openai_compat
    model: llama3.1
    api_key_env: OLLAMA_API_KEY
    base_url: http://localhost:11434/v1
```

## 3. Set the environment variable

Ollama doesn't require an API key, but the config expects one. Set a dummy:

```bash
export OLLAMA_API_KEY="ollama"
```

## 4. Verify

```bash
praxis doctor --profile default
```

## Notes

- The `base_url` must include `/v1` (Ollama's OpenAI-compatible endpoint)
- Tool/function calling may not be supported depending on the model
- The `openai_compat` adapter works with vLLM, LM Studio, Groq, Together,
  and any server exposing the OpenAI Chat Completions API
- For vLLM: `base_url: http://localhost:8000/v1`
- For LM Studio: `base_url: http://localhost:1234/v1`
