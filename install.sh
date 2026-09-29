#!/bin/sh
# Install or update litellm-skills.
#
#   curl -fsSL https://raw.githubusercontent.com/BerriAI/litellm-skills/main/install.sh | sh
#
# SKILLS_DIR picks the agent's skills directory (default: ~/.claude/skills).
# LITELLM_SKILLS_HOME picks where the repo is cloned (default: $SKILLS_DIR/litellm).
set -e

REPO="https://github.com/BerriAI/litellm-skills.git"
SKILLS_DIR="${SKILLS_DIR:-${HOME}/.claude/skills}"
INSTALL_DIR="${LITELLM_SKILLS_HOME:-${SKILLS_DIR}/litellm}"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating litellm-skills in $INSTALL_DIR"
  git -C "$INSTALL_DIR" pull --ff-only --quiet
else
  echo "Installing litellm-skills into $INSTALL_DIR"
  mkdir -p "$(dirname "$INSTALL_DIR")"
  git clone --quiet --depth=1 "$REPO" "$INSTALL_DIR"
fi
mkdir -p "$SKILLS_DIR"

# Remove links from earlier versions whose skill no longer exists
# (v1 shipped add-key, update-key, ... and also linked tests/).
removed=0
for link in "$SKILLS_DIR"/*; do
  [ -L "$link" ] || continue
  target=$(readlink "$link")
  case "$target" in
    "$INSTALL_DIR"/*)
      if [ ! -f "${target%/}/SKILL.md" ]; then
        rm "$link"
        removed=$((removed + 1))
      fi
      ;;
  esac
done

# Link every directory that is a skill.
linked=0
skipped=""
for skill_dir in "$INSTALL_DIR"/*/; do
  [ -f "${skill_dir}SKILL.md" ] || continue
  name=$(basename "$skill_dir")
  target="${SKILLS_DIR}/${name}"
  if [ -L "$target" ]; then
    continue
  elif [ -e "$target" ]; then
    skipped="$skipped $name"
  else
    ln -s "${skill_dir%/}" "$target"
    linked=$((linked + 1))
  fi
done

echo "Done. Linked ${linked} new skill(s), removed ${removed} stale link(s) in ${SKILLS_DIR}."
if [ -n "$skipped" ]; then
  echo "Skipped (something that is not a link already uses that name):${skipped}"
fi
echo "Set LITELLM_BASE_URL and LITELLM_API_KEY, then ask your agent something like \"create a key for the billing team\"."
