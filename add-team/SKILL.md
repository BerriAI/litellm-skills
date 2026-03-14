---
name: add-team
description: >
  Create a new team on a live LiteLLM proxy. Asks for team name, budget, and
  allowed models, then calls POST /team/new and shows the result.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Add Team

Create a new team on a live LiteLLM proxy.

## Setup

Ask for these if not already known:
```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://litellm.vercel.app/docs/proxy/team_based_routing

## Ask the user

1. **Team name** (required, becomes `team_alias`)
2. **Max budget** (optional, e.g. `100.00`)
3. **Allowed models** (optional, e.g. `gpt-4o, gpt-4o-mini`) — leave empty to allow all
4. **TPM / RPM limits** (optional)

## Run

```bash
curl -s -X POST "$BASE/team/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "team_alias": "<name>",
    "max_budget": <budget_or_null>,
    "models": [<models_or_empty>],
    "tpm_limit": <tpm_or_null>,
    "rpm_limit": <rpm_or_null>
  }'
```

## Output

Show the user:
- `team_id` — they'll need this to generate keys for the team
- `team_alias`, `max_budget`, `models`

On error show `detail` and the likely fix.
