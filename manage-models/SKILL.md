---
name: manage-models
description: >
  Add, list, and delete models on a live LiteLLM proxy. Walks the user through
  picking a provider, entering credentials and deployment details, then calls
  POST /model/new. Also supports listing all models and deleting by model ID.
  Use when the user wants to add a new LLM or manage existing models on their deployment.
license: MIT
compatibility: Requires curl. Proxy must be running and reachable.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Manage Models

Add, list, and remove models on a live LiteLLM proxy via the `/model` endpoints.

## Setup

Ask for these if not already available:
```
LITELLM_BASE_URL  — e.g. http://localhost:4000
LITELLM_API_KEY   — admin/master key
```

```bash
BASE="<LITELLM_BASE_URL>"
KEY="<LITELLM_API_KEY>"
```

API reference: https://litellm.vercel.app/docs/proxy/model_management

---

## Add a model

Ask the user:
1. **Model name** — the public name callers will use (e.g. `gpt-4o`, `my-claude`, `llama-3`)
2. **Provider + deployment** — the underlying model string LiteLLM routes to (see table below)
3. **Credentials** — API key, base URL, version — whatever that provider needs

### Provider reference

| Provider | `litellm_params.model` format | Extra params needed |
|---|---|---|
| OpenAI | `openai/gpt-4o` | `api_key` |
| Azure OpenAI | `azure/<deployment-name>` | `api_key`, `api_base`, `api_version` |
| Anthropic | `anthropic/claude-3-5-sonnet-20241022` | `api_key` |
| AWS Bedrock | `bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0` | AWS creds via env |
| Google Vertex | `vertex_ai/gemini-1.5-pro` | `vertex_project`, `vertex_location` |
| Ollama (local) | `ollama/llama3` | `api_base` (e.g. `http://localhost:11434`) |
| Groq | `groq/llama-3.3-70b-versatile` | `api_key` |
| Together AI | `together_ai/meta-llama/Llama-3-70b` | `api_key` |
| Cohere | `cohere/command-r-plus` | `api_key` |
| Mistral | `mistral/mistral-large-latest` | `api_key` |

Full provider list: https://docs.litellm.ai/docs/providers

### OpenAI example
```bash
curl -s -X POST "$BASE/model/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "gpt-4o",
    "litellm_params": {
      "model": "openai/gpt-4o",
      "api_key": "<OPENAI_API_KEY>"
    }
  }'
```

### Azure example
```bash
curl -s -X POST "$BASE/model/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "gpt-4o",
    "litellm_params": {
      "model": "azure/<your-deployment-name>",
      "api_key": "<AZURE_API_KEY>",
      "api_base": "https://<your-resource>.openai.azure.com",
      "api_version": "2024-02-01"
    }
  }'
```

### Anthropic example
```bash
curl -s -X POST "$BASE/model/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "claude-3-5-sonnet",
    "litellm_params": {
      "model": "anthropic/claude-3-5-sonnet-20241022",
      "api_key": "<ANTHROPIC_API_KEY>"
    }
  }'
```

### Ollama (local) example
```bash
curl -s -X POST "$BASE/model/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "llama3",
    "litellm_params": {
      "model": "ollama/llama3",
      "api_base": "http://localhost:11434"
    }
  }'
```

---

## List models

```bash
curl -s "$BASE/model/info" \
  -H "Authorization: Bearer $KEY"
```

This returns all models with their `model_info.id` (needed for update/delete).

---

## Update a model

First get the `model_id` from `/model/info`, then:

```bash
curl -s -X POST "$BASE/model/update" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model_info": {
      "id": "<model_id>"
    },
    "litellm_params": {
      "api_key": "<new-api-key>"
    }
  }'
```

---

## Delete a model

```bash
curl -s -X POST "$BASE/model/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"id": "<model_id>"}'
```

---

## Test a model works

After adding, verify it routes correctly:

```bash
curl -s -X POST "$BASE/chat/completions" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "<model_name>",
    "messages": [{"role": "user", "content": "say hi"}],
    "max_tokens": 10
  }'
```

---

## Instructions

1. Ask the user what they want to do: add / list / update / delete a model.
2. For **add**: ask for model name, provider, and required credentials. Build the curl from the provider table above.
3. For **list**: run `/model/info` and display the model names and their IDs in a clean table.
4. For **delete**: if the user gives a name not an ID, list models first to find the ID, then delete.
5. After adding, always run the test curl to confirm the model routes correctly.
6. Never log or echo API keys — pass them directly in the curl `-d` body.
