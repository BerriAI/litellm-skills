---
name: add-org
description: >
  Create a new organization on a live LiteLLM proxy. Asks for org name, budget,
  and allowed models, then calls POST /organization/new.
license: MIT
compatibility: Requires curl.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Add Organization

Create a new organization on a live LiteLLM proxy.

## Setup

Ask for these if not already known:
```
LITELLM_BASE_URL  — e.g. https://my-proxy.example.com
LITELLM_API_KEY   — proxy admin key
```

API reference: https://litellm.vercel.app/docs/proxy/org_based_routing

## Ask the user

1. **Org name** (required, becomes `organization_alias`)
2. **Allowed models** (required, e.g. `gpt-4o, claude-3-5-sonnet`)
3. **Max budget** (optional, e.g. `500.00`)
4. **TPM / RPM limits** (optional)

## Run

```bash
curl -s -X POST "$BASE/organization/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "organization_alias": "<name>",
    "models": [<models>],
    "max_budget": <budget_or_null>,
    "tpm_limit": <tpm_or_null>,
    "rpm_limit": <rpm_or_null>
  }'
```

## Output

Show the user:
- `organization_id` — needed for assigning teams/users to this org
- `organization_alias`, `max_budget`, `models`

On error show `detail` and the likely fix.
