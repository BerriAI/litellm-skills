# Provider cookbook

`litellm_params` for `POST /model/new`, per provider (LiteLLM v1.103). Every
example model string was checked against the model cost map on latest main;
confirm a newer one with `GET /utils/model_info?model=<string>` before adding (builds after v1.103 only).
Source of truth for the auth fields: `CredentialLiteLLMParams` in
`litellm/types/router.py`.

The same auth keys go in `credential_values` when you store them with
`POST /credentials`; the model then carries only `model` plus
`litellm_credential_name`. A value set directly on the model wins over the
same key in the credential.

## Contents

- OpenAI and OpenAI-compatible
- Azure OpenAI and Azure AI Foundry
- Anthropic
- AWS Bedrock
- Google Vertex AI and Gemini (AI Studio)
- Other hosted APIs (Groq, Together, Mistral, xAI, DeepSeek, OpenRouter)
- Self-hosted (Ollama, vLLM)
- Embeddings, rerank, images

## OpenAI and OpenAI-compatible

```json
{"model_name": "gpt-5.5",
 "litellm_params": {"model": "openai/gpt-5.5", "api_key": "<key>"}}
```

Optional: `organization`, `api_base` (proxies, EU data residency). Any server
that speaks the OpenAI API uses `openai/<its model id>` plus `api_base`
(ending in `/v1`); set `model_info.mode` and pricing, since the cost map will
not know it. Docs: https://docs.litellm.ai/docs/providers/openai_compatible

## Azure OpenAI

```json
{"model_name": "gpt-5.5",
 "litellm_params": {"model": "azure/<deployment-name>",
                    "api_base": "https://<resource>.openai.azure.com",
                    "api_version": "<api-version>",
                    "api_key": "<key>"},
 "model_info": {"base_model": "azure/gpt-5.5"}}
```

The part after `azure/` is your deployment name, which Azure lets you choose,
so LiteLLM cannot price it. Set `model_info.base_model` to the matching cost
map key (`azure/gpt-5.5`) or spend is recorded as 0.

Entra ID instead of `api_key`: `tenant_id` + `client_id` + `client_secret`
(service principal), or `azure_ad_token`, or `azure_username` +
`azure_password`; `azure_scope` overrides the token scope. Docs:
https://docs.litellm.ai/docs/providers/azure/azure

## Azure AI Foundry (non-OpenAI models)

```json
{"model_name": "claude-sonnet-5-5",
 "litellm_params": {"model": "azure_ai/claude-sonnet-5-5",
                    "api_base": "https://<resource>.services.ai.azure.com",
                    "api_key": "<key>"}}
```

Docs: https://docs.litellm.ai/docs/providers/azure_ai

## Anthropic

```json
{"model_name": "claude-sonnet-5-5",
 "litellm_params": {"model": "anthropic/claude-sonnet-5-5", "api_key": "<key>"}}
```

`claude-opus-5-5` is also in the cost map. Docs:
https://docs.litellm.ai/docs/providers/anthropic

## AWS Bedrock

```json
{"model_name": "claude-sonnet-5-5",
 "litellm_params": {"model": "bedrock/us.anthropic.claude-sonnet-5-5",
                    "aws_region_name": "us-east-1",
                    "aws_access_key_id": "<id>",
                    "aws_secret_access_key": "<secret>"}}
```

`us.` and `global.` cross-region inference profiles both exist for Sonnet 5.5.
Auth options, pick one set:

| Method | Fields |
|---|---|
| Static keys | `aws_access_key_id`, `aws_secret_access_key`, optional `aws_session_token` |
| Assume role | `aws_role_name`, `aws_session_name`, optional `aws_external_id`, `aws_sts_endpoint` |
| Web identity (IRSA, OIDC) | `aws_web_identity_token`, `aws_role_name`, `aws_session_name` |
| Named profile | `aws_profile_name` (profile must exist on every proxy host) |
| Bedrock API key | `api_key`, or `AWS_BEARER_TOKEN_BEDROCK` in the proxy env |
| Instance / task role | nothing; only `aws_region_name` |

Also: `aws_bedrock_runtime_endpoint` (VPC endpoint), `aws_session_tags`
(proxy admin only). Docs: https://docs.litellm.ai/docs/providers/bedrock

## Google Vertex AI

```json
{"model_name": "gemini-3.5-flash",
 "litellm_params": {"model": "vertex_ai/gemini-3.5-flash",
                    "vertex_project": "<gcp-project>",
                    "vertex_location": "us-central1",
                    "vertex_credentials": "<service-account JSON as a string>"}}
```

Omit `vertex_credentials` to use the host's Application Default Credentials.
Claude on Vertex: `vertex_ai/claude-sonnet-5-5`. `vertex_ai/gemini-3.5-flash`
carries a `deprecation_date` of 2027-05-19, so it will appear in
`/model/deprecations`. Docs: https://docs.litellm.ai/docs/providers/vertex

## Gemini (Google AI Studio)

```json
{"model_name": "gemini-3.5-flash",
 "litellm_params": {"model": "gemini/gemini-3.5-flash", "api_key": "<key>"}}
```

Docs: https://docs.litellm.ai/docs/providers/gemini

## Other hosted APIs

All take `api_key`; `api_base` only to override the default endpoint.

| Provider | `litellm_params.model` | Docs |
|---|---|---|
| Groq | `groq/openai/gpt-oss-120b` | https://docs.litellm.ai/docs/providers/groq |
| Together AI | `together_ai/moonshotai/Kimi-K3` | https://docs.litellm.ai/docs/providers/togetherai |
| Mistral | `mistral/mistral-large-latest` | https://docs.litellm.ai/docs/providers/mistral |
| xAI | `xai/grok-4.7` | https://docs.litellm.ai/docs/providers/xai |
| DeepSeek | `deepseek/deepseek-v4-pro` | https://docs.litellm.ai/docs/providers/deepseek |
| OpenRouter | `openrouter/anthropic/claude-sonnet-5.5` | https://docs.litellm.ai/docs/providers/openrouter |

## Self-hosted

| Server | `litellm_params` | Docs |
|---|---|---|
| Ollama | `{"model": "ollama/llama3", "api_base": "http://ollama:11434"}` | https://docs.litellm.ai/docs/providers/ollama |
| vLLM | `{"model": "hosted_vllm/<served-model-name>", "api_base": "http://vllm:8000/v1"}` | https://docs.litellm.ai/docs/providers/vllm |

`api_base` must be reachable from the proxy container, not from your laptop.
Self-hosted models are usually free: set `input_cost_per_token: 0` and
`output_cost_per_token: 0` in `litellm_params` if you want that explicit.

## Embeddings, rerank, images

Set `model_info.mode` so health checks and `/model_group/info` treat them
correctly.

| Kind | Example `litellm_params.model` | `model_info.mode` |
|---|---|---|
| OpenAI embedding | `openai/text-embedding-3-large` | `embedding` |
| Gemini embedding | `gemini/gemini-embedding-2` | `embedding` |
| Cohere rerank | `cohere/rerank-v3.5` | `rerank` |
| OpenAI image | `openai/gpt-image-2` | `image_generation` |

When testing these with `/health/test_connection`, pass the same `mode`.
