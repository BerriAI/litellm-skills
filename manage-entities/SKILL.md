---
name: manage-entities
description: >
  CRUD operations for users, teams, API keys, and organizations on a live LiteLLM proxy.
  Ask the user which entity and operation they want, collect the required fields,
  then run the curl and show the result. Use when the user wants to create, list,
  update, or delete users / teams / keys / orgs on their LiteLLM deployment.
license: MIT
compatibility: Requires curl. Proxy must be running and reachable.
metadata:
  author: BerriAI
  version: "1.0"
allowed-tools: Bash(curl:*)
---

# Manage Entities

Create, read, update, and delete users, teams, API keys, and organizations on a live LiteLLM proxy.

## Setup

Ask the user for these two values if not already set in the environment:

```
LITELLM_BASE_URL  — e.g. http://localhost:4000 or https://my-proxy.example.com
LITELLM_API_KEY   — an admin/master key (not a virtual key scoped to llm_api_routes)
```

Set them as shell variables for all subsequent curls:
```bash
BASE="<LITELLM_BASE_URL>"
KEY="<LITELLM_API_KEY>"
```

API reference: https://litellm.vercel.app/docs/proxy/virtual_keys

---

## Users

### Create user
```bash
curl -s -X POST "$BASE/user/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_email": "<email>",
    "user_alias": "<alias>",
    "user_role": "internal_user"
  }'
```
Roles: `proxy_admin`, `proxy_admin_viewer`, `internal_user`, `internal_user_viewer`

### List users
```bash
curl -s "$BASE/user/list?page=1&page_size=25" \
  -H "Authorization: Bearer $KEY"
```
Optional filters: `&role=internal_user`, `&user_email=foo@bar.com`

### Update user
```bash
curl -s -X POST "$BASE/user/update" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "<user_id>",
    "max_budget": 10.00,
    "models": ["gpt-4o", "claude-3-5-sonnet"]
  }'
```

### Delete user
```bash
curl -s -X POST "$BASE/user/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_ids": ["<user_id>"]}'
```

---

## Teams

### Create team
```bash
curl -s -X POST "$BASE/team/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "team_alias": "<name>",
    "max_budget": 100.00,
    "models": ["gpt-4o"]
  }'
```

### List teams
```bash
curl -s "$BASE/team/list" \
  -H "Authorization: Bearer $KEY"
```

### Get team info
```bash
curl -s "$BASE/team/info?team_id=<team_id>" \
  -H "Authorization: Bearer $KEY"
```

### Update team
```bash
curl -s -X POST "$BASE/team/update" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "team_id": "<team_id>",
    "max_budget": 200.00,
    "tpm_limit": 100000
  }'
```

### Delete team
```bash
curl -s -X POST "$BASE/team/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"team_ids": ["<team_id>"]}'
```

---

## API Keys

### Generate key
```bash
curl -s -X POST "$BASE/key/generate" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key_alias": "<alias>",
    "models": ["gpt-4o"],
    "max_budget": 5.00,
    "duration": "30d"
  }'
```
`duration` examples: `24h`, `7d`, `30d` — omit for no expiry.

### List keys
```bash
curl -s "$BASE/key/list?page=1&size=25" \
  -H "Authorization: Bearer $KEY"
```
Optional filters: `&user_id=<id>`, `&team_id=<id>`, `&key_alias=<alias>`

### Get key info
```bash
curl -s "$BASE/key/info?key=<the-key>" \
  -H "Authorization: Bearer $KEY"
```

### Update key
```bash
curl -s -X POST "$BASE/key/update" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "<the-key>",
    "max_budget": 20.00,
    "models": ["gpt-4o", "gpt-4o-mini"]
  }'
```

### Delete key
```bash
curl -s -X POST "$BASE/key/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["<the-key>"]}'
```

---

## Organizations

### Create org
```bash
curl -s -X POST "$BASE/organization/new" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "organization_alias": "<name>",
    "models": ["gpt-4o"],
    "max_budget": 500.00
  }'
```

### List orgs
```bash
curl -s "$BASE/organization/list" \
  -H "Authorization: Bearer $KEY"
```

### Delete org
```bash
curl -s -X DELETE "$BASE/organization/delete" \
  -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"organization_ids": ["<org_id>"]}'
```

---

## Instructions

1. Ask the user which entity (user / team / key / org) and which operation (create / list / get / update / delete).
2. Ask only for the fields required by that operation.
3. Run the curl and pretty-print the JSON response.
4. If the response contains an `id` or key value the user will need later, highlight it clearly.
5. On errors, show the `detail` or `error.message` field and suggest the likely fix (wrong key permissions, missing required field, etc.).
