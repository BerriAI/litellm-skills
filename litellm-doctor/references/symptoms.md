# Symptoms, causes, fixes

Read this when the short table in SKILL.md is not enough: an error string you
need to match exactly, telling a budget block from a rate limit, or a slow
proxy. Strings are from LiteLLM v1.103 source (`litellm/proxy/auth/`,
`litellm/proxy/hooks/parallel_request_limiter_v3.py`, `litellm/exceptions.py`).

## Contents

- Reading a proxy error
- 401
- 403
- 400 and 404
- 422 and 429: budget or rate limit?
- 500, 502, 503
- Model added but not live
- Slow responses
- Guardrail blocked it

## Reading a proxy error

Errors come back OpenAI-shaped:
`{"error": {"message": ..., "type": ..., "param": ..., "code": "<status>"}}`.
`type` is the most reliable signal: `auth_error`, `expired_key`,
`budget_exceeded`, `key_model_access_denied` (also `team_`, `user_`, `org_`,
`project_` variants, plus `agent_` on builds after v1.103), `no_db_connection`, `bad_request_error`,
`not_found_error`, `internal_server_error`. Provider errors keep the provider's
status and name the provider in the message, e.g.
`litellm.AuthenticationError: AnthropicException - invalid x-api-key`.
To find the logged row for one failed call, filter `/spend/logs/v2` by the
time window plus `key_alias`, `model_group`, or `error_code`; if you have its
`request_id`, `search=<request_id>` matches it across all time.

## 401

| Message contains | Cause | Fix |
|---|---|---|
| `No api key passed in` | No `Authorization` or `x-litellm-api-key` header | Send `Authorization: Bearer sk-...` |
| `Malformed API Key passed in` | Header without `Bearer ` | Add the prefix |
| `Invalid proxy server token passed` / `Unable to find token in cache` | Typo, deleted key, or key from another proxy/DB | Check the key; issue a new one |
| `Expired Key. Key Expiry time ...` (type `expired_key`) | `expires` passed | `/key/update` with `duration`, or new key |
| `Key is blocked` | Key blocked | `/key/unblock` if intended |
| `Only proxy admin can be used to generate, delete, update info for new keys/users/teams` | Valid non-admin key on an admin route | Use an admin key or grant the role |
| Names a provider (`OpenAIException`, `AnthropicException`) | The **deployment's** provider credentials are bad, not the caller's key | Fix the model's `api_key` (`litellm-models`), confirm with `/health?model=` |

## 403

| Message / type | Cause | Fix |
|---|---|---|
| `The requested model 'X' is not available for this API key, or the model name is invalid` (type `*_model_access_denied`) | Model not in the key's, team's, user's, org's, or project's `models`. Older builds returned 401. | Add the model or its access group to the right object; `type` says which layer refused |
| `Virtual key is not allowed to call this route` | `key_type` (`llm_api`, `read_only`) or `allowed_routes` | Use an appropriate key |
| `user not allowed to access this route ... is an admin only route` | Role lacks the route | Admin key |
| `key not allowed to health-check model ...` | `/health?model=` on a model the key cannot use (v1.102+) | Use an admin key |
| `Organizations are only available for LiteLLM Enterprise users` | Org endpoints without a license (v1.102+) | License, or use teams |
| `only available for LiteLLM Enterprise` / `premium` | Other licensed features | `/health/license`; drop the field |

## 400 and 404

- `/<route>: Invalid model name passed in model=X. Call /v1/models to view
  available models for your key.` (400): the name matches no model, alias, or
  wildcard on this proxy. List `/v1/models` with the caller's key and
  `/model/info` with the admin key. Common causes: provider prefix sent
  (`openai/gpt-5.5` when the public name is `gpt-5.5`), a team-only model
  called with a key outside the team, or a model added on one replica only.
- A write on a setting declared in config.yaml (v1.103+) returns 400 naming the
  file; edit the file and restart.
- 404 on a management route: wrong ID, or the endpoint is newer than the proxy.

## 422 and 429: budget or rate limit?

**Budget.** `error.type` is `budget_exceeded` and the message starts
`Budget has been exceeded!` then names the layer: `Key=...`, `Team=...`,
`User=... in Team=...` (team member budget), plus `Current cost` and
`Max budget`. The status is **429** on v1.103 and earlier; builds after
v1.103 return **422** by default (`litellm.budget_exceeded_status_code`). Match on `type`, not status. Fix: raise
`max_budget` on that layer, add `temp_budget_increase`, or wait for
`budget_reset_at`. Throttling instead of blocking is opt-in: the key needs
`throttle_on_budget_exceeded: true`, a `tpm_limit` or `rpm_limit`, and
`litellm_settings.budget_exceeded_throttle_percentage` set on the proxy.
Router fallbacks re-check budgets per target (v1.103+).

**Proxy rate limit.** 429 with `Rate limit exceeded for <descriptor>:
<value>. Limit type: <requests|tokens|max_parallel_requests>. Current limit:
N, Remaining: 0. Limit resets at: <UTC time>`. The descriptor says which layer
(`api_key`, `team`, `user`, `end_user`, or a per-model variant). Headers carry
`retry-after`, `rate_limit_type`, and `reset_at`; successful responses carry
`x-ratelimit-<descriptor>-remaining-requests` / `-tokens` so a client can see
headroom before it hits the wall. Fix: raise `rpm_limit`/`tpm_limit` on that
layer or spread load.

**Provider rate limit.** 429 whose message comes from the provider
(`litellm.RateLimitError: OpenAIException - ...`). In `/spend/logs/v2`,
`metadata.error_information.error_rate_limit_category` is
`vendor_rate_limit`. Fix: more deployments in the model group, fallbacks, or a
higher provider quota.

**Cooldown.** `No deployments available for selected model, Try again in N
seconds. ... All deployments for selected model are in cooldown`: every
deployment failed recently and is benched. The root error is in the earlier
failures for that model group; run `/health?model=`.

## 500, 502, 503

- Message names a provider (`APIConnectionError`, `InternalServerError`,
  `Timeout`, `BadRequestError: ...Exception`): upstream problem or bad
  deployment config (`api_base`, region, deployment name). Probe with
  `/health?model=<name>`; the `error` there is the provider's answer.
- 503 with type `no_db_connection`, or `/health/readiness` showing
  `db: disconnected` (or `stalled`, builds after v1.103): Postgres is
  unreachable or slow. Auth for
  keys not already cached fails. `general_settings.allow_requests_on_db_unavailable`
  keeps serving during an outage (and keeps readiness at 200).
- 503 `shutting_down` from liveness/readiness: the pod is draining.
- 500 `Model list not initialized` on `/health`: no models configured.

## Model added but not live

1. Runtime models need `STORE_MODEL_IN_DB=True` (or
   `general_settings.store_model_in_db: true`) and a database; without them
   `/model/new` is refused with "Set `STORE_MODEL_IN_DB='True'` in your env".
2. Each replica reloads DB models every `PROXY_CONFIG_RELOAD_INTERVAL_SECONDS`
   (default 30). With Redis configured, a change also triggers a resync. Wait
   and retry; if one pod still lacks it, compare `/model/info` across pods.
3. Team-scoped models only appear to keys in that team.
4. The caller's key must allow the model (403 above), and `/v1/models` with that
   key must list it.

## Slow responses

- Compare `x-litellm-response-duration-ms` (total) with
  `x-litellm-overhead-duration-ms` (LiteLLM's own share). High total with low
  overhead is the provider; check `/health?model=` latency and the provider's
  status.
- High overhead: `GET /health/backlog` shows `in_flight_requests` and
  `queued_requests` per worker (add workers or replicas); `is_detailed_debug`
  in `/health/readiness/details` means debug logging is on (turn it off);
  `db: stalled` (builds after v1.103) means auth lookups wait on Postgres; many callbacks in
  `/active/callbacks` add work per request; no Redis with several workers
  causes cache misses.
- Retries and fallbacks add time: `x-litellm-attempted-retries` and
  `x-litellm-attempted-fallbacks` headers show them.
- Docs: https://docs.litellm.ai/docs/troubleshoot/latency_overhead

## Guardrail blocked it

A 400 whose message names a guardrail or "Violated guardrail policy" came from
a guardrail, not auth. `x-litellm-applied-guardrails` shows which ran; use the
`litellm-guardrails` skill (`POST /policies/resolve`, `/guardrails/usage/logs`)
to see why.
