---
name: add-model
description: >
  Add a new model to a live LiteLLM proxy. Walks the user through picking a
  provider, entering the deployment name and credentials, calls POST /model/new,
  then test-calls the model to confirm it routes correctly.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Add Model

Add a new LLM to a live LiteLLM proxy.

## Setup

Ask for these if not already known:
```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://litellm.vercel.app/docs/proxy/model_management

## Ask the user

1. **Public model name** — what callers will send in `"model": "..."` (e.g. `gpt-4o`, `my-claude`, `llama3`)
2. **Provider** — pick from the table below
3. **Credentials** — whatever that provider needs

## Provider table

| Provider | `litellm_params.model` | Extra params |
|---|---|---|
| OpenAI | `openai/gpt-4o` | `api_key` |
| Azure OpenAI | `azure/<deployment-name>` | `api_key`, `api_base`, `api_version` |
| Anthropic | `anthropic/claude-3-5-sonnet-20241022` | `api_key` |
| AWS Bedrock | `bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0` | AWS creds via env |
| Google Vertex | `vertex_ai/gemini-1.5-pro` | `vertex_project`, `vertex_location` |
| Ollama | `ollama/llama3` | `api_base` (e.g. `http://localhost:11434`) |
| Groq | `groq/llama-3.3-70b-versatile` | `api_key` |
| Together AI | `together_ai/meta-llama/Llama-3-70b` | `api_key` |
| Mistral | `mistral/mistral-large-latest` | `api_key` |

Full list: https://docs.litellm.ai/docs/providers

## Run

```bash
curl -s -X POST "$BASE/model/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "<public-name>",
    "litellm_params": {
      "model": "<provider/deployment>",
      "api_key": "<key>",
      "api_base": "<base_if_needed>",
      "api_version": "<version_if_azure>"
    }
  }'
```

## Test it

After adding, verify it routes:

```bash
curl -s -X POST "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<public-name>",
    "messages": [{"role": "user", "content": "say hi"}],
    "max_tokens": 10
  }'
```

## Output

Show `model_id` from the response — needed to update or delete the model later.
Report pass/fail from the test call.
