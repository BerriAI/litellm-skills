#!/bin/sh
set -e

REPO="https://github.com/BerriAI/litellm-skills.git"
SKILLS_DIR="${HOME}/.claude/skills"
INSTALL_DIR="${SKILLS_DIR}/litellm"

# Clone or update
if [ -d "$INSTALL_DIR/.git" ]; then
  echo "Updating litellm-skills..."
  git -C "$INSTALL_DIR" pull --ff-only
else
  echo "Installing litellm-skills..."
  mkdir -p "$SKILLS_DIR"
  git clone --depth=1 "$REPO" "$INSTALL_DIR"
fi

# Symlink each skill directory
linked=0
for skill_dir in "$INSTALL_DIR"/*/; do
  name=$(basename "$skill_dir")
  target="${SKILLS_DIR}/${name}"
  if [ ! -e "$target" ]; then
    ln -s "$skill_dir" "$target"
    linked=$((linked + 1))
  fi
done

echo "Done. ${linked} skill(s) linked to ${SKILLS_DIR}"
echo "Try /add-model, /add-user, /view-usage, and more."
