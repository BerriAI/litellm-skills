---
name: litellm-guardrails
description: >
  Create, list, update, test, attach, and delete guardrails on a live LiteLLM
  proxy (AI gateway) with curl, and group them into policies scoped to teams,
  keys, models, or tags. Use this whenever someone wants PII masking or
  redaction, prompt injection or jailbreak blocking, content moderation,
  secret detection, banned words or regex filters, tool-call permissions, or
  MCP tool result scanning; asks to turn a guardrail on for one team, one key,
  or every request; wants to check whether a guardrail catches something
  ("does this block an SSN?"); asks which guardrails apply to a team or key; or
  wants guardrail block rates. Also use it for Presidio, Bedrock Guardrails,
  Lakera, Model Armor, Azure Prompt Shield, OpenAI moderation, Aporia, or the
  built-in content filter, even if the user never says "guardrail".
license: MIT
compatibility: Requires curl and python3. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(python3:*)
---

# LiteLLM guardrails

A guardrail is a named check (Presidio, Bedrock, Lakera, a regex filter, ...)
that runs at a point in the request lifecycle (`mode`). A guardrail only runs
when something turns it on: `default_on: true` (every request), a key or team
`guardrails` list, a policy attachment, or the request's own `guardrails` field.

## Connect

Read `LITELLM_BASE_URL` and `LITELLM_API_KEY` from the environment. If either is
missing, ask for it once and export it for the rest of the session. The key must
be a proxy admin key: creating, changing, and deleting guardrails and policies
is proxy-admin only, while testing with `/guardrails/apply_guardrail` works with
any key. Never echo the admin key or a newly generated key back into logs you
don't need to.

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
| See guardrails (DB and config.yaml) | `GET /v2/guardrails/list` |
| See one guardrail | `GET /guardrails/{guardrail_id}` |
| Add a guardrail at runtime | `POST /guardrails` |
| Change one field (name, `default_on`, a param) | `PATCH /guardrails/{guardrail_id}` |
| Run it on sample text | `POST /guardrails/apply_guardrail` |
| Turn it on for a key or team | `POST /key/update` or `/team/update` with `guardrails` (Enterprise) |
| Turn it on for a team/key/model/tag via a policy | `POST /policies`, then `POST /policies/attachments` |
| Ask "what runs for team X / key Y?" | `POST /policies/resolve` |
| Block rates and recent blocks | `GET /guardrails/usage/overview`, `/guardrails/usage/logs` |
| Remove it | `DELETE /guardrails/{guardrail_id}` |

Read `references/providers.md` (per-provider `litellm_params`) before creating
one, and `references/policies.md` for policy versions, pipelines, attachments.

## List and inspect

```bash
curl -sS "$LITELLM_BASE_URL/v2/guardrails/list" -H "Authorization: Bearer $LITELLM_API_KEY"
curl -sS "$LITELLM_BASE_URL/guardrails/<guardrail_id>" -H "Authorization: Bearer $LITELLM_API_KEY"
```

Entries carry `guardrail_id`, `guardrail_name`, `litellm_params` (`guardrail`,
`mode`, `default_on`, provider params; secrets masked), and
`guardrail_definition_location`: `db` (editable via API) or `config` (edit
config.yaml and restart; the write endpoints 404 on it).

## Create a guardrail

Needs a database. Ask for: a name (becomes the `guardrail_name` referenced
everywhere else, so keep it stable, e.g. `pii-mask`), the provider, the `mode`,
and whether it should run on every request (`default_on`).

```bash
curl -sS -X POST "$LITELLM_BASE_URL/guardrails" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"guardrail": {
    "guardrail_name": "pii-mask",
    "litellm_params": {"guardrail": "presidio", "mode": "pre_call", "default_on": false,
      "pii_entities_config": {"US_SSN": "MASK", "EMAIL_ADDRESS": "MASK", "CREDIT_CARD": "BLOCK"}},
    "guardrail_info": {"description": "Mask PII before it reaches the model"}}}'
```

Keep the returned `guardrail_id`. The pod that served the call enforces it at
once; other replicas pick it up on their next DB sync (default 30s,
`PROXY_CONFIG_RELOAD_INTERVAL_SECONDS`). A bad config is rejected with 400.

**Modes.** `pre_call` (input, before the LLM), `during_call` (input, in
parallel with the LLM; can block but not modify), `post_call` (output),
`logging_only` (mask what gets logged, never block), `pre_mcp_call` and
`during_mcp_call` (MCP tool arguments), `post_mcp_call` (MCP tool results,
v1.96+). `mode` can be a list, e.g. `["pre_call", "post_call"]`. Not every
provider supports every mode; `GET /guardrails/ui/add_guardrail_settings`
returns `supported_modes_by_provider`. Provider-independent flags
(`scan_only_tool_results`, fail-open, ...) are in `references/providers.md`.

## Update

`PATCH` merges: `litellm_params` you send are merged over the stored ones,
`guardrail_name` renames, `guardrail_info` replaces. `default_on` lives inside
`litellm_params`; a top-level `default_on` is silently ignored.

```bash
curl -sS -X PATCH "$LITELLM_BASE_URL/guardrails/<guardrail_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"litellm_params": {"default_on": true}}'
```

Prefer PATCH. `PUT` replaces the whole definition (create's body), and since
reads mask secrets, a PUT built from a GET would store the masked `api_key`.
An invalid update returns 422 and the old config stays live. Renaming breaks
every key, team, policy, and client that uses the old name.

## Attach a guardrail

**Every request:** PATCH `default_on: true`. A key or team can opt out with
`disable_global_guardrails: true` (Enterprise; only a proxy admin may set it).

**One key or team (Enterprise):** send `guardrails` top-level on
`/key/update` or `/team/update`. The list replaces the stored one, so read the
current list first (`/key/info` gives `info.metadata.guardrails`, `/team/info`
gives `team_info.metadata.guardrails`) and send the union. `policies` works the
same way for policy names. Don't nest it in `metadata`, which replaces a key's
whole metadata.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/team/update" \
  -H "Authorization: Bearer $LITELLM_API_KEY" \
  -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"team_id": "<team_id>", "guardrails": ["pii-mask"]}'
```

**By team alias, key alias, model, or tag:** use a policy (live as version 1
the moment it exists) plus an attachment. Before attaching broadly, run the
same body through `POST /policies/attachments/estimate-impact` and show the
affected key and team counts.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/policies" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"policy_name": "marketing-pii", "guardrails_add": ["pii-mask"], "description": "PII masking for marketing"}'

curl -sS -X POST "$LITELLM_BASE_URL/policies/attachments" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"policy_name": "marketing-pii", "teams": ["marketing"]}'
```

`POST /policies` does not check that guardrail names exist (a typo never
runs), so compare against `/v2/guardrails/list`. Attachments match **aliases**
(`team_alias`, `key_alias`), not IDs; trailing `*` is a wildcard. Use
`"scope": "*"`, `models`, or `tags` for the other shapes. The docs label
team/key-scoped attachments Enterprise.

**One request:** clients can send `"guardrails": ["pii-mask"]` in the body.

## Test

```bash
curl -sS -X POST "$LITELLM_BASE_URL/guardrails/apply_guardrail" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"guardrail_name": "pii-mask", "text": "My SSN is 123-45-6789, email jo@example.com"}'
```

A mask returns 200 with `response_text` rewritten; a block returns an error
(usually 400) naming the violation. Add `"input_type": "response"` to test
output-side behavior. It calls the real vendor, so it can cost a little.
Then check the wiring:

```bash
curl -sS -X POST "$LITELLM_BASE_URL/policies/resolve" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"team_alias": "marketing", "model": "gpt-5.5"}'
```

`effective_guardrails` lists what would run and `matched_policies[].matched_via`
says why. On a real call, the `x-litellm-applied-guardrails` and
`x-litellm-applied-policies` response headers show what ran.

## Usage

```bash
curl -sS "$LITELLM_BASE_URL/guardrails/usage/overview?start_date=2026-09-01&end_date=2026-09-29" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
curl -sS "$LITELLM_BASE_URL/guardrails/usage/logs?guardrail_id=<guardrail_id>&action=blocked&page_size=50" \
  -H "Authorization: Bearer $LITELLM_API_KEY"
```

Overview (default last 7 days, max 366) returns `totalRequests`,
`totalBlocked`, `passRate`, and `rows` with `requestsEvaluated`, `failRate`,
`status` (`warning` above 5%, `critical` above 15%), `trend`, `cost`. Logs take
`action=blocked|passed|flagged|not_run`. Also: `/guardrails/usage/detail/{id}`
(daily series) and `/policies/usage/overview`.

## Delete

Look it up and show what references it (`default_on`, key and team
`guardrails` lists, `guardrails_add` in `GET /policies/list`), then get an
explicit yes. Enforcement stops at once and references silently match nothing,
so protected traffic flows unprotected. To pause instead, PATCH
`default_on: false` or delete the policy attachment.

```bash
curl -sS -X DELETE "$LITELLM_BASE_URL/guardrails/<guardrail_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -w '\nHTTP %{http_code}\n'
```

## Errors

- **403 "Admin access required to manage guardrails"**, or a route-permission
  error on `/policies*`: not a proxy admin key.
- **404 on PATCH/PUT/DELETE**: wrong ID, or a `config` guardrail.
- **400 "Guardrail configuration error"** (create) / **422** (update): bad or
  missing provider params; the message names the field.
- **500 "Prisma client not initialized" / "Database not connected"**: runtime
  guardrails and policies need `DATABASE_URL`.
- **400 "Only draft versions can be updated"**: see `references/policies.md`.
- **Enterprise errors** on key/team `guardrails`, `policies`,
  `disable_global_guardrails`, tag-based `mode`, or `hide-secrets`: say so and
  offer `default_on` or a policy attachment instead.
- **Never fires**: nothing turned it on, the mode doesn't match the traffic
  (MCP vs LLM), or `logging_only` was expected to block. Check
  `x-litellm-applied-guardrails` and `/policies/resolve`.
- Docs: https://docs.litellm.ai/docs/proxy/guardrails/quick_start
