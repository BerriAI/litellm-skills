# Policies and attachments

Read this when creating or changing a policy after it exists, building a
guardrail pipeline, or debugging why a policy did or did not apply. All
`/policies*` endpoints are proxy-admin only (admin viewers can read the lists)
and need a database. Source of truth: `litellm/proxy/policy_engine/` and
`litellm/types/proxy/policy_engine/` (LiteLLM v1.103).

## Contents

- Model: policy vs attachment
- Policy fields
- Versions (draft, published, production)
- Attachment fields and matching
- Pipelines
- Debugging endpoints
- Delete
- config.yaml equivalent

## Model: policy vs attachment

A **policy** says *what* runs: guardrails to add or remove, optional
inheritance, optional model condition, optional pipeline. An **attachment**
says *where*: global, or team aliases, key aliases, models, tags. A policy with
no attachment does nothing (unless a key or team lists it in its `policies`
field, which is Enterprise). Since v1.102, matched policies run in a fixed
order: global, then team, key, tag, and model scope, then policies the request
asked for explicitly. Since v1.103, an attachment `priority` (lower runs first)
overrides that order.

## Policy fields (`POST /policies`)

| Field | Notes |
|---|---|
| `policy_name` | Unique. What attachments and keys reference. |
| `guardrails_add` | Guardrail names. Not validated against the registry. |
| `guardrails_remove` | Names to drop from the inherited set. |
| `inherit` | Parent policy name; the child starts from the parent's resolved set. |
| `condition` | `{"model": "gpt-5.*"}`: exact name or regex; the policy applies only to matching models. |
| `pipeline` | Ordered steps; see Pipelines. |
| `description` | Free text. |

The response has `policy_id` (a version ID, not the name), `version_number`,
and `version_status`.

## Versions

A newly created policy is version 1 with status `production`, so it is live
immediately wherever it is attached. Only `draft` versions can be edited;
`PUT /policies/{policy_id}` on a published or production version returns 400.
To change a live policy:

```bash
# 1. clone production into a new draft (or pass source_policy_id to clone another version)
curl -sS -X POST "$LITELLM_BASE_URL/policies/name/marketing-pii/versions" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" -d '{}'
# 2. edit the draft (merge semantics: send only what changes)
curl -sS -X PUT "$LITELLM_BASE_URL/policies/<draft_policy_id>" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"guardrails_add": ["pii-mask", "prompt-injection"]}'
# 3. draft -> published, then published -> production (the old production becomes published)
curl -sS -X PUT "$LITELLM_BASE_URL/policies/<draft_policy_id>/status" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"version_status": "published"}'
curl -sS -X PUT "$LITELLM_BASE_URL/policies/<draft_policy_id>/status" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"version_status": "production"}'
```

Draft cannot go straight to production, and `published` is only accepted from
`draft` (the endpoint docstring mentions demoting production to published, but
the code rejects it). `GET /policies/name/{name}/versions` lists versions;
`GET /policies/compare?version_a=<id>&version_b=<id>` diffs two.
`GET /policies/list?version_status=production` shows what is live, including
config.yaml policies (`definition_location: config`).

## Attachment fields (`POST /policies/attachments`)

| Field | Notes |
|---|---|
| `policy_name` | Must have a production version, else 404. |
| `scope` | `"*"` applies to every request. |
| `teams` | Team **aliases**; trailing `*` wildcard. Unknown concrete aliases are rejected (400). |
| `keys` | Key **aliases**; same rules. A key or team with no alias only matches an omitted field or a bare `*`. |
| `models` | Model names or patterns. Unknown concrete model names are rejected (400); patterns are accepted. |
| `tags` | Request tag patterns (`health-*`). Empty means tags are not checked. |
| `priority` | int, lower runs first (v1.103+). |
| `default` | Builds after v1.103 only (v1.103 has `priority` only). `true`: only applies when no non-default attachment matches. |

The fields AND together: `{"teams": ["marketing"], "models": ["gpt-5.5"]}`
matches only marketing's gpt-5.5 traffic. An omitted `teams`, `keys`, or
`models` means "any", so an attachment with only `policy_name` applies to every
request, same as `scope: "*"`. There is no update; delete the
attachment and create a new one.
`POST /policies/attachments/estimate-impact` takes the same body and returns
`affected_keys_count`, `affected_teams_count`, `unnamed_keys_count`, and up to
10 `sample_keys` / `sample_teams`. Show this before attaching broadly.

## Pipelines

Without a pipeline, a policy's guardrails run independently. With one, they run
as ordered steps with branching:

```json
{"pipeline": {"mode": "pre_call", "steps": [
  {"guardrail": "pii-mask", "on_pass": "next", "on_fail": "block", "pass_data": true},
  {"guardrail": "prompt-injection", "on_pass": "allow", "on_fail": "block", "on_error": "allow"}
]}}
```

`mode` is `pre_call` or `post_call`. Actions: `allow`, `block`, `next`,
`modify_response` (with `modify_response_message`). `on_error` covers vendor
timeouts and outages and defaults to `on_fail`. `pass_data: true` forwards the
masked request to the next step. Try one without saving it:

```bash
curl -sS -X POST "$LITELLM_BASE_URL/policies/test-pipeline" \
  -H "Authorization: Bearer $LITELLM_API_KEY" -H "Content-Type: application/json" \
  -d '{"pipeline": {"mode": "pre_call", "steps": [{"guardrail": "pii-mask", "on_pass": "next", "on_fail": "block"}]},
       "test_messages": [{"role": "user", "content": "My SSN is 123-45-6789"}]}'
```

It returns `terminal_action` and per-step `step_results` (`outcome`,
`action_taken`, `duration_seconds`).

## Debugging endpoints

- `POST /policies/resolve` with `team_alias`, `key_alias`, `model`, `tags`:
  `effective_guardrails` and `matched_policies[].matched_via`. Add
  `?force_sync=true` to reload from the DB first (other pods' writes).
- `GET /policies/{policy_id}/resolved-guardrails`: the inherited set for one
  version.
- `GET /policies/attachments/list`: all attachments, config ones with IDs like
  `config-0`.
- `GET /policy/templates`: prebuilt guardrail bundles the UI offers.

## Delete

`DELETE /policies/{policy_id}` deletes one version. Deleting the production
version deactivates the policy (the response carries a `warning`) unless a
config.yaml policy of the same name takes over. `DELETE
/policies/name/{name}/all-versions` removes every version. Neither removes
attachments; list and delete those too (`DELETE
/policies/attachments/{attachment_id}`), and confirm with the user before any of
these, since traffic loses the guardrails immediately.

## config.yaml equivalent

```yaml
policies:
  marketing-pii:
    guardrails:
      add: [pii-mask]
policy_attachments:
  - policy: marketing-pii
    teams: [marketing]
```

Config policies and attachments show up in the list endpoints but can only be
changed in the file. Docs:
https://docs.litellm.ai/docs/proxy/guardrails/guardrail_policies
