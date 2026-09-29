# Model fields

Fields accepted in the body of `POST /model/new` and
`PATCH /model/{model_id}/update` (LiteLLM v1.103), plus the request shapes for
access groups and fallbacks. Send only what the user asked for. Source of
truth: `Deployment`, `LiteLLM_Params`, `GenericLiteLLMParams`, and `ModelInfo`
in `litellm/types/router.py`; pricing fields in `CustomPricingLiteLLMParams`
in `litellm/types/utils.py`.

## Contents

- Top level
- litellm_params: routing and limits
- litellm_params: pricing
- model_info
- Team-scoped models (Enterprise)
- Provisioned throughput (PTU)
- PATCH semantics
- Model access groups
- Fallbacks
- Deprecations

## Top level

| Field | Type | Notes |
|---|---|---|
| `model_name` | string | Public name clients send. Required on create. Reusing an existing name adds a load-balanced deployment to that group. |
| `litellm_params` | object | Required on create; `model` is its only required key. Auth fields per provider are in `providers.md`. |
| `model_info` | object | Optional metadata. `id` is generated if omitted and becomes `model_id`. Unknown keys are kept. |
| `blocked` | bool | PATCH only. Same as `/model/block`; proxy admin only. |

## litellm_params: routing and limits

| Field | Type | Notes |
|---|---|---|
| `model` | string | `provider/model`, e.g. `openai/gpt-5.5`. |
| `litellm_credential_name` | string | Stored credential to pull auth from. Only a proxy admin may attach or detach one (v1.101+). Keys set directly on the model win over the credential's. |
| `rpm`, `tpm` | int | Deployment rate limits used by the router. Required and positive when `general_settings.enforce_rpm_tpm_on_model_add: true` (v1.100+). |
| `itpm`, `otpm` | int | Input and output tokens per minute. |
| `max_parallel_requests` | int | Concurrency cap for this deployment. |
| `order` | int | Priority within the group: `1` is tried first, higher numbers only when lower ones fail. |
| `weight` | int | Share of traffic under weighted shuffle routing. |
| `timeout`, `stream_timeout` | number (s) | Request timeouts. |
| `max_retries` | int | Provider SDK retries. |
| `cooldown_time` | float (s) | Per-deployment cooldown after failures. |
| `max_budget`, `budget_duration` | float, string | Deployment-level spend cap (`30d`, `1mo`). |
| `default_api_key_tpm_limit`, `default_api_key_rpm_limit` | int | Per-key limit applied on this deployment when the key has no model-specific limit. |
| `tags` | list | Tag-based routing; with tag filtering on, only requests carrying a matching tag reach this deployment. |
| `tag_regex` | list | Regexes matched against request headers for tag routing. |
| `drop_params` | bool | Drop OpenAI params the provider doesn't support instead of erroring. |
| `use_in_pass_through` | bool | Let the provider pass-through routes use these credentials. |
| `use_chat_completions_api` | bool | Serve `/v1/responses` through the provider's chat completions API. |
| `cache_control_injection_points` | list | Gateway-injected prompt caching points. |
| `custom_llm_provider` | string | Force the provider when the model string is ambiguous. |
| `aws_session_tags` | list | Bedrock STS session tags; proxy admin only. |

## litellm_params: pricing

Custom prices override the cost map for this deployment only. They belong in
`litellm_params`. Since v1.102 pricing sent in `model_info` on a model write is
dropped (PR #36222), because clients echoing `/model/info` were freezing
catalog prices. v1.103 also ignores pricing that older Admin UI edits copied
into `model_info`, and `/model/info` reports the overridden fields in
`model_info.pricing_overrides` (read-only, PR #41843).

| Field | Unit |
|---|---|
| `input_cost_per_token`, `output_cost_per_token` | USD per token (so $3 per 1M tokens is `0.000003`) |
| `cache_read_input_token_cost`, `cache_creation_input_token_cost` | USD per cached token |
| `input_cost_per_character`, `output_cost_per_character` | USD per character |
| `tiered_pricing` | list of ranges with their own rates |
| `input_cost_per_second`, `output_cost_per_second` | USD per second (audio, video, dedicated endpoints) |
| `input_cost_per_pixel`, `output_cost_per_pixel`; `output_cost_per_image_512`, `_1024`, `_1536` (builds after v1.103) | image pricing |

On PATCH, `null` clears the fields in the first four rows; the others can only be overwritten.
Docs: https://docs.litellm.ai/docs/proxy/custom_pricing

## model_info

| Field | Type | Notes |
|---|---|---|
| `id` | string | Deployment id (`model_id`). Set it only if you need a stable, known id. |
| `mode` | string | `chat`, `completion`, `embedding`, `image_generation`, `image_edit`, `audio_speech`, `audio_transcription`, `rerank`, `video_generation`, `realtime`, `responses`, `ocr`, `batch`. Needed when the model string is not in the cost map. |
| `base_model` | string | Cost-map key used for pricing and limits. Required for accurate Azure spend (`azure/gpt-5.5`). |
| `access_groups` | list | Model access groups this deployment belongs to. Replaced whole on PATCH. |
| `team_id` | string | Makes this a team-scoped model; see below. |
| `discoverable` | bool | Builds after v1.103 only. `false` hides it from `/v1/models` and other listings while keeping it callable. |
| `access_windows` | list | Builds after v1.103 only. Reserve the deployment for teams during a daily window: `[{"start": "22:00", "end": "06:00", "timezone": "America/New_York", "team_ids": ["<team_id>"]}]`. |
| `tier` | `free` \| `paid` | Label. |
| `max_input_tokens`, `max_output_tokens` | int | Override context limits shown in listings. |
| `allow_fail_open` | bool | Fall back to default-tagged deployments when tag constraints exclude all. |
| `enable_tag_filtering` | bool | Per-group override of the router setting. |
| `health_check_model` | string | Concrete model a wildcard deployment probes. |
| `health_check_params` | object | Extra params merged into health probes and `/health/test_connection` (v1.100+), e.g. provider-specific required fields. |
| `health_check_timeout`, `health_check_max_tokens`, `health_check_reasoning_effort`, `health_check_voice` | | Probe tuning. |
| `disable_background_health_check` | bool | Skip in the background health loop. |
| `deprecation_date` | date string | Overrides the cost map date used by `/model/deprecations`. |

Read-only in responses: `db_model`, `created_at`, `created_by`, `updated_at`,
`updated_by`, `blocked`, `team_public_model_name`, `pricing_overrides`,
`access_via_team_ids`, `direct_access`.

## Team-scoped models (Enterprise)

Set `model_info.team_id` on create. Proxy admins or that team's admins can do
it. The proxy stores the row under an internal `model_name` like
`model_name_<team_id>_<uuid>`, keeps the name you sent in
`model_info.team_public_model_name`, and adds that public name to the team's
`models`. Only keys on that team can call it. Without a license the call
returns 403. Docs: https://docs.litellm.ai/docs/proxy/team_model_add

## Provisioned throughput (PTU)

`ptu_count` and `cost_per_ptu_per_hour` (both together), optional
`ptu_effective_from` / `ptu_effective_to` (ISO datetimes), in `model_info`.
Requires `LITELLM_ENABLE_PTU_COST_ATTRIBUTION=true` on the proxy, otherwise
400. A PTU deployment bills flat hourly cost and its per-token prices are
zeroed, so do not send nonzero token prices with it. Docs:
https://docs.litellm.ai/docs/proxy/ptu_flat_cost

## PATCH semantics

`PATCH /model/{model_id}/update` merges the stored `litellm_params` and
`model_info` with what you send, key by key. Omitted keys are kept. `null` is
ignored except for the pricing fields above, `litellm_credential_name`
(detaches the credential), and `cache_control_injection_points`. Sending
`model_name` renames the group entry; access groups (v1.101+) and key, team,
org, project, and user model allowlists (v1.103+) follow the rename. Config
models return 400. The response is the updated row; its `litellm_params`
values are encrypted.

## Model access groups

Tag deployments with a group name, then put that name in a key's or team's
`models` list to grant every model in it.

```bash
curl -sS -X POST "$LITELLM_BASE_URL/access_group/new" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"access_group": "prod-models", "model_names": ["gpt-5.5", "claude-sonnet-5-5"]}'
```

| Call | Notes |
|---|---|
| `POST /access_group/new` | `access_group` plus `model_names` (tags every deployment of each name) or `model_ids` (specific deployments). Names must exist. |
| `GET /access_group/list` | Groups with `model_names`, `deployment_count`, spend, budget. |
| `GET /access_group/{g}/info` | One group. |
| `PUT /access_group/{g}/update` | Replaces membership with the new `model_names` / `model_ids`. |
| `DELETE /access_group/{g}/delete` | Untags every deployment; keys and teams that listed the group lose those models. Confirm first. |
| `GET` / `PUT` / `DELETE /access_group/{g}/budget` | Shared budget (v1.100+): `max_budget`, `soft_budget`, `budget_duration`, or `budget_id`. Every key reaching the group draws from it. |

Only DB deployments are tagged by these calls; config models need
`access_groups` in `config.yaml`. The newer unified groups at
`/v1/access_group` (POST, GET, `GET/PUT/DELETE /v1/access_group/{id}`, proxy
admin) bundle `access_model_names` with MCP servers and agents and attach to
keys via `access_group_ids`. Docs:
https://docs.litellm.ai/docs/proxy/model_access_groups,
https://docs.litellm.ai/docs/proxy/access_groups

## Fallbacks

```bash
curl -sS -X POST "$LITELLM_BASE_URL/fallback" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -w '\nHTTP %{http_code}\n' \
  -d '{"model": "gpt-5.5", "fallback_models": ["claude-sonnet-5-5"], "fallback_type": "general"}'
```

`fallback_type` is `general` (any error after retries), `context_window`, or
`content_policy`. Both the model and every fallback must be existing model
names, and a model cannot fall back to itself. Posting again for the same model
replaces its list. `GET /fallback/{model}?fallback_type=general` reads it (404
when none); `DELETE /fallback/{model}?fallback_type=general` removes it. Needs
`STORE_MODEL_IN_DB=True`. From v1.103, a setting that `config.yaml` declares is
owned by the file and runtime writes to it are refused or ignored; if the
file declares `router_settings.fallbacks`, change it there. Since v1.103 the
caller's budget is re-checked on each fallback target. Docs:
https://docs.litellm.ai/docs/proxy/fallback_management

## Deprecations

`GET /model/deprecations?warn_within_days=30` (v1.99+) returns `deprecated`,
`imminent`, and `upcoming` lists for models configured on this proxy, from the
cost map's `deprecation_date` or a `model_info.deprecation_date` override. Use
it when asked what needs migrating.
