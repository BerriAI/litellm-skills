# Guardrail provider configs

`litellm_params` for the most used integrations, as JSON for
`POST /guardrails` (`{"guardrail": {"guardrail_name": ..., "litellm_params":
{...}}}`). The same keys work under `guardrails:` in config.yaml. Source of
truth: `LitellmParams` and `SupportedGuardrailIntegrations` in
`litellm/types/guardrails.py` (LiteLLM v1.103). For any provider,
`GET /guardrails/ui/provider_specific_params` returns its parameter list and
`GET /guardrails/ui/add_guardrail_settings` its supported modes.

## Contents

- Secrets and credentials
- Flags for any guardrail
- Built-in content filter (`litellm_content_filter`)
- Presidio PII (`presidio`)
- Bedrock Guardrails (`bedrock`)
- Lakera (`lakera_v2`)
- OpenAI moderation (`openai_moderation`)
- Azure Content Safety (`azure/prompt_shield`, `azure/text_moderations`)
- Google Model Armor (`model_armor`)
- Aporia (`aporia`)
- Secret detection (`hide-secrets`, Enterprise)
- Tool permissions (`tool_permission`)
- Your own HTTP service (`generic_guardrail_api`)
- Every supported `guardrail` value

## Secrets and credentials

On guardrails created through the API, `api_key` and `api_base` accept
`os.environ/VAR_NAME` and are resolved from the proxy's environment; prefer that
to pasting a raw secret. For AWS and GCP, prefer the proxy's own IAM role or
service account over putting keys in the body. Reads mask secrets, which is why
updates should use PATCH (see SKILL.md).

## Flags for any guardrail

These sit in `litellm_params` next to the provider fields. Apply to the unified
guardrail path; a provider page may list exceptions.

| Field | Effect |
|---|---|
| `default_on` | Run on every request. Defaults to `false`. |
| `scan_only_tool_results` | Scan only tool results (untrusted data fed back to the model), skipping system, user, and assistant text. For agent harnesses whose own prompts trip injection detectors (v1.97+). |
| `skip_system_message_in_guardrail`, `skip_tool_message_in_guardrail` | Leave system or tool messages out of the scan; `null` uses the global setting. |
| `experimental_use_latest_role_message_only` | Scan only the newest user message (pre_call) or assistant message (post_call). |
| `only_scan_new_messages` | Per session (`litellm_session_id`), scan only messages not seen before (v1.95+). Detection only; ignored when masking. |
| `run_in_parallel` | Run alongside other opted-in guardrails of the same hook (v1.95+). Block-only guardrails; never for maskers. |
| `scan_raw_request` | pre_call only: always scan the request as it was before other guardrails edited it. Block-only. |
| `fail_on_error` | `true` (default) fails the request on a guardrail error; `false` lets it through. Honored by `model_armor`, `generic_guardrail_api`, `crowdstrike_aidr`. |
| `unreachable_fallback` | `fail_closed` (default) or `fail_open` when the vendor is unreachable. Honored by `generic_guardrail_api` and a few HTTP integrations. |
| `timeout` | Seconds for the vendor call. |
| `violation_message_template` | Custom block message. |
| `mask_request_content`, `mask_response_content` | For providers that can redact (Bedrock, Model Armor): rewrite instead of block. |

## Built-in content filter (`litellm_content_filter`)

No external service. Regex patterns, keywords, and prebuilt harm categories,
each with `BLOCK` or `MASK`. Runs on `post_mcp_call` too (v1.97+).

```json
{
  "guardrail": "litellm_content_filter",
  "mode": "pre_call",
  "patterns": [
    {"pattern_type": "prebuilt", "pattern_name": "us_ssn", "action": "BLOCK"},
    {"pattern_type": "prebuilt", "pattern_name": "email", "action": "MASK"},
    {"pattern_type": "regex", "name": "employee_id", "pattern": "EMP-[0-9]{6}", "action": "MASK"}
  ],
  "blocked_words": [{"keyword": "project-falcon", "action": "BLOCK", "description": "Unannounced product"}],
  "categories": [{"category": "harmful_self_harm", "enabled": true, "action": "BLOCK", "severity_threshold": "medium"}]
}
```

Prebuilt `pattern_name` values include `us_ssn`, `email`, `us_phone`,
`credit_card`, `visa`, `mastercard`, `amex`, `iban`, `ipv4`, `ipv6`,
`aws_access_key`, `aws_secret_key`, `github_token`, `slack_token`,
`generic_api_key`, `passport_us`, `street_address`, plus many country-specific
IDs (`br_cpf`, `au_tfn`, `ca_sin`, `sg_nric`, `uae_emirates_id`, ...).
Categories include `harmful_self_harm`, `harmful_violence`,
`harmful_illegal_weapons`, `harmful_child_safety`, `bias_gender`,
`bias_racial`, `bias_religious`, `prompt_injection_jailbreak`,
`prompt_injection_system_prompt`, `prompt_injection_data_exfiltration`,
`prompt_injection_sql`, `denied_medical_advice`, `denied_legal_advice`,
`denied_financial_advice`. `severity_threshold` is `high`, `medium`, or `low`.
Docs: https://docs.litellm.ai/docs/proxy/guardrails/litellm_content_filter

## Presidio PII (`presidio`)

Needs a Presidio analyzer and anonymizer reachable from the proxy, either via
`PRESIDIO_ANALYZER_API_BASE` / `PRESIDIO_ANONYMIZER_API_BASE` in its
environment or the params below.

```json
{
  "guardrail": "presidio",
  "mode": "pre_call",
  "presidio_analyzer_api_base": "http://presidio-analyzer:3000",
  "presidio_anonymizer_api_base": "http://presidio-anonymizer:3000",
  "pii_entities_config": {"US_SSN": "MASK", "EMAIL_ADDRESS": "MASK", "PHONE_NUMBER": "MASK", "CREDIT_CARD": "BLOCK"},
  "presidio_score_thresholds": {"ALL": 0.6, "CREDIT_CARD": 0.8},
  "presidio_language": "en"
}
```

Actions are `MASK` or `BLOCK`. Entity names are Presidio's (`PERSON`,
`LOCATION`, `IP_ADDRESS`, `IBAN_CODE`, `US_PASSPORT`, `UK_NHS`, `IN_AADHAAR`,
...). `output_parse_pii: true` restores the original values in the model's
reply. `presidio_filter_scope` is `input`, `output`, or `both`.
`presidio_entities_deny_list` drops noisy entity types. Use
`mode: "pre_mcp_call"` to mask MCP tool arguments.
Docs: https://docs.litellm.ai/docs/proxy/guardrails/pii_masking_v2

## Bedrock Guardrails (`bedrock`)

```json
{
  "guardrail": "bedrock",
  "mode": "pre_call",
  "guardrailIdentifier": "ff6ujrregl1q",
  "guardrailVersion": "1",
  "aws_region_name": "us-east-1",
  "mask_request_content": true
}
```

`guardrailVersion` can be `DRAFT`. `disable_exception_on_block: true` returns
the masked or blocked output instead of raising. For `post_call` streaming,
`streaming_end_of_stream_only` and `streaming_sampling_rate` trade latency for
coverage. Credentials follow the usual AWS chain (`aws_role_name`,
`aws_profile_name`, or the proxy's IAM role).
Docs: https://docs.litellm.ai/docs/proxy/guardrails/bedrock

## Lakera (`lakera_v2`)

```json
{
  "guardrail": "lakera_v2",
  "mode": "pre_call",
  "api_key": "os.environ/LAKERA_API_KEY",
  "project_id": "project-7539648934",
  "on_flagged": "block"
}
```

`on_flagged`: `block`, `monitor` (log only), or `inject_system_message` (with
`advisory_system_message`). Prefer `lakera_v2`; `lakera` is the legacy v1
integration. Docs: https://docs.litellm.ai/docs/proxy/guardrails/lakera_ai

## OpenAI moderation (`openai_moderation`)

```json
{"guardrail": "openai_moderation", "mode": "pre_call", "api_key": "os.environ/OPENAI_API_KEY", "model": "omni-moderation-latest"}
```

`model` defaults to `omni-moderation-latest` (or `text-moderation-latest`);
`api_key` falls back to `OPENAI_API_KEY`. Use `post_call` to screen output.
Docs: https://docs.litellm.ai/docs/proxy/guardrails/openai_moderation

## Azure Content Safety

```json
{"guardrail": "azure/prompt_shield", "mode": "pre_call", "api_key": "os.environ/AZURE_GUARDRAIL_API_KEY", "api_base": "os.environ/AZURE_GUARDRAIL_API_BASE"}
```

Prompt Shield (jailbreak and injection) supports `pre_call` or `during_call`.
`azure/text_moderations` (harm categories) takes `mode: ["pre_call",
"post_call"]`, `severity_threshold`, `severity_threshold_by_category`,
`categories`, `blocklistNames`, `haltOnBlocklistHit`.
Docs: https://docs.litellm.ai/docs/proxy/guardrails/azure_content_guardrail

## Google Model Armor (`model_armor`)

```json
{
  "guardrail": "model_armor",
  "mode": ["pre_call", "post_call"],
  "template_id": "prod-llm-template",
  "project_id": "acme-ai-prod",
  "location": "us-central1",
  "mask_request_content": true,
  "mask_response_content": true
}
```

`credentials` takes a service-account JSON path or string; omit it to use the
proxy's default GCP credentials. `fail_on_error` defaults to `true` (fail
closed). Docs: https://docs.litellm.ai/docs/proxy/guardrails/model_armor

## Aporia (`aporia`)

```json
{"guardrail": "aporia", "mode": "during_call", "api_key": "os.environ/APORIA_API_KEY", "api_base": "os.environ/APORIA_API_BASE"}
```

Docs: https://docs.litellm.ai/docs/proxy/guardrails/aporia_api

## Secret detection (`hide-secrets`, Enterprise)

```json
{"guardrail": "hide-secrets", "mode": "pre_call"}
```

Redacts API keys, tokens, and credentials from prompts. Lives in the
`litellm-enterprise` package, so it fails on proxies without it.
`detect_secrets_config` tunes the detectors.
Docs: https://docs.litellm.ai/docs/proxy/guardrails/secret_detection

## Tool permissions (`tool_permission`)

Allow or deny tool calls the model makes, by regex on the tool name and
optionally on argument values.

```json
{
  "guardrail": "tool_permission",
  "mode": "post_call",
  "rules": [
    {"id": "allow_github_mcp", "tool_name": "^mcp__github_.*$", "decision": "allow"},
    {"id": "internal_email_only", "tool_name": "^send_email$", "decision": "allow",
     "allowed_param_patterns": {"to[]": "^.+@acme\\.com$"}}
  ],
  "default_action": "deny",
  "on_disallowed_action": "block"
}
```

`default_action` defaults to `deny`, so an empty rule list blocks every tool.
`on_disallowed_action: "rewrite"` strips the tool call instead of failing.
Docs: https://docs.litellm.ai/docs/proxy/guardrails/tool_permission

## Your own HTTP service (`generic_guardrail_api`)

```json
{
  "guardrail": "generic_guardrail_api",
  "mode": "pre_call",
  "api_base": "https://guardrails.internal.acme.com",
  "api_key": "os.environ/ACME_GUARDRAIL_KEY",
  "unreachable_fallback": "fail_closed",
  "additional_provider_specific_params": {"threshold": 0.8}
}
```

`unreachable_fallback: "fail_open"` lets traffic through when the service is
down; `fail_on_error: false` does so on any error. A team member with a
team-scoped key can submit one for approval with `POST /guardrails/register` (lands as
`pending_review`; a proxy admin approves with
`POST /guardrails/submissions/{guardrail_id}/approve`).
Docs: https://docs.litellm.ai/docs/adding_provider/generic_guardrail_api

## Every supported `guardrail` value

`aim`, `agent_365`, `akto`, `alice`, `aporia`, `azure/prompt_shield`,
`azure/text_moderations`, `bedrock`, `block_code_execution`, `cato_networks`,
`cisco_ai_defense`, `compresr`, `conduct`, `crowdstrike_aidr`, `custom_code`,
`deepkeep`, `dynamoai`, `enkryptai`, `generic_guardrail_api`, `grayswan`,
`guardrails_ai`, `headroom`, `hiddenlayer`, `hide-secrets`, `ibm_guardrails`,
`javelin`, `lakera`, `lakera_v2`, `lasso`, `litellm_content_filter`,
`llm_as_a_judge`, `mcp_end_user_permission`, `mcp_jwt_signer`,
`mcp_security`, `microsoft_purview`, `model_armor`, `noma`, `noma_v2`,
`onyx`, `openai_moderation`, `ovalix`, `pangea`, `panw_prisma_airs`,
`pillar`, `presidio`, `prompt_security`, `promptguard`, `qostodian_nexus`,
`qualifire`, `repelloai`, `rubrik`, `semantic_guard`, `singulr`, `straiker`,
`tool_permission`, `typesafe`, `vigil_guard`, `xecguard`, `zscaler_ai_guard`.
Most have a page under https://docs.litellm.ai/docs/proxy/guardrails/quick_start
(for example https://docs.litellm.ai/docs/proxy/guardrails/pangea); read it for
the provider's own params before creating one.
