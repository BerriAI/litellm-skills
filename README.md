# litellm skills

[Agent Skills](https://agentskills.io) for LiteLLM proxy workflows. Requires `git` + `gh` CLI.

## Skills

| Skill | Description |
|-------|-------------|
| [`changelog`](changelog/) | Generate a LinkedIn/social-style release changelog from PRs merged to main today. |
| [`ci-fixer`](ci-fixer/) | Review failing CircleCI tests, bisect to find the offending commit, and propose fixes. |
| [`queue-release`](queue-release/) | Queue a Docker build and deploy GitHub Action for a LiteLLM release branch. |
| [`queue-rc-to-stable`](queue-rc-to-stable/) | Graduate an RC branch to a new stable release branch and queue a Docker build. |
| [`queue-enterprise-pip-pkg`](queue-enterprise-pip-pkg/) | Publish a new version of the `litellm-enterprise` pip package. |
| [`queue-proxy-extras-pkg`](queue-proxy-extras-pkg/) | Publish a new version of the `litellm-proxy-extras` pip package. |
| [`ship`](ship/) | Ship workflow: merge main, run tests, review diff, bump VERSION, update CHANGELOG, commit, push, create PR. |
| [`review`](review/) | Pre-landing PR review for SQL safety, LLM trust boundary violations, and structural issues. |
| [`retro`](retro/) | Weekly engineering retrospective with per-person contribution breakdowns and trend tracking. |

## Install

```bash
git clone https://github.com/BerriAI/litellm-skills.git ~/.claude/skills/litellm
cd ~/.claude/skills
ln -s litellm/changelog changelog
ln -s litellm/ci-fixer ci-fixer
ln -s litellm/queue-release queue-release
ln -s litellm/queue-rc-to-stable queue-rc-to-stable
ln -s litellm/queue-enterprise-pip-pkg queue-enterprise-pip-pkg
ln -s litellm/queue-proxy-extras-pkg queue-proxy-extras-pkg
ln -s litellm/ship ship
ln -s litellm/review review
ln -s litellm/retro retro
```

Or as a submodule:

```bash
git submodule add https://github.com/BerriAI/litellm-skills.git .skills/litellm
cd .skills
ln -s litellm/changelog changelog
ln -s litellm/ci-fixer ci-fixer
ln -s litellm/queue-release queue-release
ln -s litellm/queue-rc-to-stable queue-rc-to-stable
ln -s litellm/queue-enterprise-pip-pkg queue-enterprise-pip-pkg
ln -s litellm/queue-proxy-extras-pkg queue-proxy-extras-pkg
ln -s litellm/ship ship
ln -s litellm/review review
ln -s litellm/retro retro
```

Claude Code discovers skills by looking for `SKILL.md` files at `~/.claude/skills/<skill-name>/SKILL.md`. Since this is a multi-skill repo, symlinks are needed to expose each sub-skill at the expected depth.

## Usage

Invoke by name in your agent (e.g. `/changelog` or `/ci-fixer 123` or `/queue-release`). Skills that take a PR number or branch name auto-detect from the current branch when not provided.

## License

MIT
