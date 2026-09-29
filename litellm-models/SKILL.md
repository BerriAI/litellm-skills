---
name: litellm-models
description: >
  Add, test, list, update, pause, and delete LLM deployments on a live LiteLLM
  proxy (AI gateway) with curl, plus the pieces around them: reusable provider
  credentials, model access groups, and fallbacks. Use this whenever someone
  wants to register or deploy a model (OpenAI, Azure, Anthropic, Bedrock,
  Vertex, Gemini, Groq, Ollama, vLLM, any provider), connect a provider API key,
  rotate a provider key across many models, rename a model, set custom pricing
  or rpm/tpm on a deployment, check whether a model works, take a model out of
  rotation during an incident, group models so keys and teams can be granted
  them together, configure fallbacks, or find deprecated models. Also use it
  when a user says "model_id", "deployment", "model_name", or wants to fix a
  model that is missing from /v1/models or failing.
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM models

A deployment is one provider endpoint the proxy can call. Clients send the
public `model_name`; `litellm_params.model` (`provider/model`) says where it
goes; `model_info.id` (returned as `model_id`) identifies the deployment.
Several deployments with the same `model_name` are load balanced as one group.

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. The key must
be a proxy admin key (team admins can manage models scoped to their own team on
Enterprise). Never echo the admin key or a provider key back into logs you don't
need to.

```bash
curl -sS "$LITELLM_BASE_URL/health/readiness/details" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Skip it if you already checked this proxy earlier in the session. It confirms
the URL and key work and returns `litellm_version`. Features
below that changed recently name the version they arrived in; if the proxy is
older, say so instead of guessing.

Append `-w '\nHTTP %{http_code}\n'` to write calls so the status is visible.

## Pick the operation

| The user wants to | Call |
|---|---|
| Check a model string before adding (builds after v1.103) | `GET /utils/model_info?model=<provider/model>` |
| Add a deployment | `POST /model/new` |
| Test a deployment | `POST /health/test_connection` |
| List or find deployments | `GET /v2/model/info?search=`, `GET /model/info` |
| Change key, base, name, limits, pricing | `PATCH /model/{model_id}/update` |
| Take out of rotation / restore | `POST /model/block`, `POST /model/unblock` |
| Remove permanently | `POST /model/delete` |
| Store a provider key once, reuse it | `/credentials` |
| Grant a bundle of models | `/access_group/*` |
| Retry failures on another model | `/fallback` |
| Find models near end of life | `GET /model/deprecations` (v1.99+) |

Writes need a database and `STORE_MODEL_IN_DB=True` on the proxy. Models
declared in `config.yaml` are read-only here: update, block, and delete return
400.

## Add a model

1. **Provider and model string.** Get the `litellm_params` shape from
   `references/providers.md`. Optionally validate it (builds after v1.103; v1.103
   and earlier return a plain 404 "Not Found" for the route, so skip it). A 404
   with a message only means the string is not in the cost map (fine for custom or self-hosted models, but then set
   `model_info.mode` and pricing yourself):

   ```bash
   curl -sS "$LITELLM_BASE_URL/utils/model_info?model=openai/gpt-5.5" \
     -H "Authorization: Bearer $LITELLM_API_KEY"
   ```

2. **Secrets.** Prefer a stored credential (below) referenced by
   `litellm_credential_name`; only a proxy admin may attach one (v1.101+). An
   inline `api_key` also works and is encrypted at rest. `os.environ/VAR`
   values resolve from the proxy host env on v1.92+ (ignored v1.83.10 to
   v1.91) and only if every replica has the variable. Never print provider keys.
   `/model/new` does not check that the credential name exists; the test step
   catches a typo.

3. **Create.**

```bash
curl -sS -X POST "$LITELLM_BASE_URL/model/new" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{
    "model_name": "gpt-5.5",
    "litellm_params": {"model": "openai/gpt-5.5", "litellm_credential_name": "openai-prod", "rpm": 500},
    "model_info": {"mode": "chat"}
  }'
```

   Show only `model_id` and `model_name`; the response's `litellm_params` are
   encrypted blobs. Custom pricing goes in `litellm_params`
   (`input_cost_per_token`, ...): v1.102+ strips pricing from `model_info` on
   writes. Limits, tags, `base_model` (needed for Azure spend), team models,
   and PTU are in `references/fields.md`.

4. **Test by `model_id`** (next section), then **report** `model_name`,
   `model_id`, provider, and test status.

If `/model/new` returns 500 "Model create was saved to the database, but ...
not live", the row exists: do not retry (that creates a duplicate). Find it with
`/v2/model/info?search=` and check the server logs it names.

## Test a model

```bash
curl -sS -X POST "$LITELLM_BASE_URL/health/test_connection" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model_info": {"id": "<model_id>"}}'
```

This probes that exact deployment with its stored params. The mode is read
from the cost map and defaults to chat, so for a custom model string that is not
chat add `"mode"` (`embedding`, `rerank`, `image_generation`, `audio_speech`,
...). It returns 200 either way: read `status` (`success`/`error`) and show
`result.error`. Don't also send `litellm_params.model` with the public name;
request params override the stored ones. To test before saving, send full
`litellm_params` and no id (`os.environ/` refs are rejected here).
`GET /health?model_id=<id>` is an alternative. Other replicas load a new model
on their next reload, so an immediate `/chat/completions` may miss it.

## List and find

```bash
curl -sS "$LITELLM_BASE_URL/v2/model/info?search=claude&size=50" \
  -H "Authorization: Bearer $LITELLM_API_KEY" | python3 -c "
import sys,json
for m in json.load(sys.stdin)['data']:
  i=m['model_info']; print(i['id'], m['model_name'], m['litellm_params'].get('model'), 'db' if i.get('db_model') else 'config', 'BLOCKED' if i.get('blocked') else '')"
```

It pages (`page`, `size`, `total_pages`) and filters by `modelId`, `teamId`,
`access_group`. `/model/info?litellm_model_id=<id>` returns one deployment;
`GET /model_group/info?model_group=gpt-5.5` shows the group as clients see it.

## Update a model

```bash
curl -sS -X PATCH "$LITELLM_BASE_URL/model/<model_id>/update" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"litellm_params": {"rpm": 1000}, "model_info": {"access_groups": ["prod-models"]}}'
```

PATCH merges key by key into the stored `litellm_params` and `model_info`, so
send only what changes. Lists such as `access_groups` are replaced whole. A
`null` is ignored except on the pricing fields, `litellm_credential_name`, and
`cache_control_injection_points`, which it clears. Renaming via
`model_name` updates access groups (v1.101+) and key, team, and org allowlists
(v1.103+). An inline `api_key` keeps winning over an attached credential and
cannot be nulled, so to move a model onto a credential add a new deployment,
test it, then delete the old one. Avoid `POST /model/update`: it is the legacy
endpoint, ignores `model_info`, and returns `200 null` when the DB is off.

## Block and unblock (proxy admin, v1.101+)

```bash
curl -sS -X POST "$LITELLM_BASE_URL/model/block" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"model_id": "<model_id>"}'
# /model/unblock takes the same body
```

It stops serving but keeps its config and history; other deployments sharing
the `model_name` keep serving. Suggest this before delete.

## Delete a model

Look it up first and show `model_name`, provider, `db_model`, team, access
groups, and whether other deployments share the name; get an explicit yes.
Deletion also drops it from access groups and, for team models, removes the
team's public name when no sibling still backs it. If it is the last deployment
for that `model_name`, every key calling it starts failing.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/model/delete" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"id": "<model_id>"}'
```

## Credentials, access groups, fallbacks

```bash
# store once; credential_info is required (may be {})
curl -sS -X POST "$LITELLM_BASE_URL/credentials" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"credential_name": "openai-prod", "credential_values": {"api_key": "<key>"}, "credential_info": {}}'
```

`GET /credentials` and `/credentials/by_name/{name}` return masked values.
Rotating with `PATCH /credentials/{name}` (body repeats `credential_name` and
`credential_info`) updates every model that references it. Renaming it or
`DELETE /credentials/{name}` leaves those models calling the provider without
auth, so find them in `/v2/model/info` and confirm first. Access
groups (`POST /access_group/new {"access_group", "model_names"}`) and fallbacks
(`POST /fallback {"model", "fallback_models", "fallback_type"}`) are covered in
`references/fields.md`.

## Errors

- **500 "No DB Connected" / "Set STORE_MODEL_IN_DB"**: add `DATABASE_URL` and
  `STORE_MODEL_IN_DB=True`, or declare models in `config.yaml`.
- **500 "saved to the database, but ... not live"**: do not retry; see Add.
- **400 "Cannot edit config-based model" / "not found in db"**: the model lives
  in `config.yaml`; edit the file.
- **400 "... must be set to a positive value"**: `enforce_rpm_tpm_on_model_add`
  is on (v1.100+); send positive `rpm` and `tpm`.
- **403 "Only a proxy admin can ..."**: attaching a stored credential needs a
  proxy admin key. **403 "Only proxy admins can change a model's blocked
  flag."**: same for block/unblock.
- **400 "Model updates only supported for DB-stored models"**: the proxy runs
  without `STORE_MODEL_IN_DB`; PATCH and block only work on database models. **403 premium**: team models need an Enterprise license.
- **400 "PTU cost attribution is disabled"**: set
  `LITELLM_ENABLE_PTU_COST_ATTRIBUTION=true` or drop the PTU fields.
- **test_connection `status: error`**: show `result.error`; usually a bad key,
  wrong `api_base`/region, or wrong mode.
- Anything else: show `detail` / `error.message` verbatim and the likely fix.

Docs: https://docs.litellm.ai/docs/proxy/model_management
