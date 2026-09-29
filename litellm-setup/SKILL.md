---
name: litellm-setup
description: >
  Stand up a LiteLLM proxy (AI gateway) locally or on a server: Docker Compose
  with Postgres, a single docker run, or uv/pip, plus the config.yaml, master
  key, salt key, and first model. Use this whenever someone wants to install,
  run, deploy, self-host, or try LiteLLM; get an OpenAI-compatible or
  Anthropic-compatible endpoint in front of several providers; needs a gateway
  for Claude Code, Codex, or their agents but has no proxy running yet (if one
  already exists, litellm-connect covers pointing clients at it); or hits "proxy refuses to start",
  "No connected db", or a master key error on boot.
license: MIT
compatibility: Requires a shell with docker (or uv/pip) and curl. Written against LiteLLM v1.103 (September 2026).
metadata:
  author: BerriAI
  version: "2.0"
allowed-tools: Bash(curl:*) Bash(docker:*) Bash(openssl:*) Bash(python3:*)
---

# LiteLLM setup

Get a working LiteLLM proxy with a database, a strong master key, and at least
one model, then hand off to the other `litellm-*` skills.

## Decide what to run

Ask two questions if the answer isn't obvious:

1. **Does it need keys, teams, budgets, spend tracking, or models added through
   the API/UI?** Almost always yes. Those need Postgres; without it every
   virtual key fails with `No connected db.` and `/model/new` fails.
2. **Local trial or long-lived deployment?** Local: Docker Compose below.
   Production: same shape, but pin a release tag, use a managed Postgres, and
   put secrets in a secret manager (see https://docs.litellm.ai/docs/proxy/prod).

The Admin UI ships in the same container at `http://<host>:4000/ui`.

## Two secrets to understand first

- `LITELLM_MASTER_KEY` is the admin credential. Always generate a strong one;
  do not reuse doc examples such as `sk-1234`. v1.103 starts anyway when it is
  unset and then runs with **no auth at all**, and accepts weak values. Builds
  after v1.103 **refuse to start** when it is unset, empty, or `sk-1234`.
- `LITELLM_SALT_KEY` encrypts provider API keys stored in the database. Set it
  before adding any model and never change it: there is no rotation path, and a
  new salt makes every stored credential unreadable. If unset, the master key is
  used for encryption, which then ties the two together forever.

```bash
printf 'LITELLM_MASTER_KEY=sk-%s\nLITELLM_SALT_KEY=sk-%s\n' \
  "$(openssl rand -hex 32)" "$(openssl rand -hex 32)" > .env
```

Tell the user where `.env` lives and to back it up. Don't print the values.

## Option A: Docker Compose with Postgres (recommended)

The quickstart file in the LiteLLM repo runs the gateway plus Postgres 16 and
refuses to start if either secret is missing.

```bash
curl -sSLO https://github.com/BerriAI/litellm/raw/main/docker/docker-compose.quickstart.yml
# .env from the step above must sit next to it
docker compose -f docker-compose.quickstart.yml up -d
```

It uses the rolling `main-stable` tag, which is fine for a trial. For anything
long-lived, edit the `image:` line to a pinned release such as
`ghcr.io/berriai/litellm:v1.103.0` (current stable when this skill was
written; see https://github.com/BerriAI/litellm/releases for newer ones).

## Option B: a single docker run against an existing Postgres

```bash
docker run -d --name litellm \
  --env-file .env \
  -e DATABASE_URL="postgresql://<user>:<password>@<host>:5432/<dbname>" \
  -e STORE_MODEL_IN_DB=True \
  -p 4000:4000 \
  ghcr.io/berriai/litellm:v1.103.0
```

`STORE_MODEL_IN_DB=True` does nothing without `DATABASE_URL`; always pair them.
To also load a config file, add `-v $(pwd)/config.yaml:/app/config.yaml` and
`--config /app/config.yaml` after the image name.

## Option C: uv / pip (no Docker)

```bash
uv tool install 'litellm[proxy]'
litellm --config config.yaml   # listens on port 4000; override with --port or PORT
```

Prefer `uv tool install`: a plain `pip install` on an old Python can silently
resolve an old LiteLLM release. Export `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`,
and `DATABASE_URL` in the shell first.

## Minimal config.yaml

Only needed when models live in a file instead of the database. Models added
through the API or UI (with `STORE_MODEL_IN_DB=True`) don't need it.

```yaml
model_list:
  - model_name: gpt-5.5                 # the name clients send
    litellm_params:
      model: openai/gpt-5.5
      api_key: os.environ/OPENAI_API_KEY
  - model_name: claude-sonnet-5-5
    litellm_params:
      model: anthropic/claude-sonnet-5-5
      api_key: os.environ/ANTHROPIC_API_KEY

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

`os.environ/NAME` is resolved from the container or shell environment, so pass
provider keys with `-e` or `.env`. Settings declared in this file become
read-only through the API (v1.103+ returns 400 on runtime writes to them),
so keep anything admins will tune at runtime out of it.

## Verify

```bash
curl -sS http://localhost:4000/health/liveliness      # "I'm alive!"
curl -sS http://localhost:4000/health/readiness       # {"status":"healthy","db":"connected",...}
curl -sS http://localhost:4000/health/readiness/details \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY"      # includes litellm_version
```

If readiness returns 503 the database is unreachable. Check the logs with
`docker compose -f docker-compose.quickstart.yml logs litellm --tail 100`
(or `docker logs litellm --tail 100`).

## Hand off

Once it's healthy, set the variables every other skill reads:

```bash
export LITELLM_BASE_URL=http://localhost:4000
export LITELLM_API_KEY=<the master key>
```

Then, depending on what the user wants next:

- add a provider model: **litellm-models**
- give a person or app a key: **litellm-keys**
- point Claude Code, Codex, an SDK, or an MCP client at the gateway: **litellm-connect**
- something is wrong: **litellm-doctor**

## Boot errors

| Symptom | Cause and fix |
|---|---|
| Refuses to start, mentions master key (builds after v1.103) | Unset, empty, or `sk-1234`. Generate a key as above. `LITELLM_DANGEROUSLY_PERMIT_WEAK_OR_UNSET_MASTER_KEY=true` bypasses it for throwaway local dev only. v1.103 has no such check and boots with no auth, so verify the key is set. |
| Compose error `set it in .env` | `.env` is missing or not next to the compose file. |
| `No connected db.` on key calls | `DATABASE_URL` not set or wrong. |
| Readiness 503 | Postgres not reachable yet; compose waits for the db healthcheck, a bare `docker run` does not. |
| Stored model credentials stop decrypting | `LITELLM_SALT_KEY` changed or was set after models were added. Restore the original value. |
| Port 4000 in use | Map another host port: `-p 4001:4000`. |
