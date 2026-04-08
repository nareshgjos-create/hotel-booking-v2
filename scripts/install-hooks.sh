#!/usr/bin/env bash
# install-hooks.sh — copies git hooks from scripts/hooks/ into .git/hooks/
# Run once after cloning: bash scripts/install-hooks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
GIT_ROOT="$(git -C "$PROJECT_ROOT" rev-parse --show-toplevel 2>/dev/null || echo "")"

if [ -z "$GIT_ROOT" ]; then
  echo "❌ Not inside a git repository. Run 'git init' first."
  exit 1
fi

HOOKS_SRC="${SCRIPT_DIR}/hooks"
HOOKS_DST="${GIT_ROOT}/.git/hooks"

for hook in "$HOOKS_SRC"/*; do
  hook_name="$(basename "$hook")"
  dest="${HOOKS_DST}/${hook_name}"
  cp "$hook" "$dest"
  chmod +x "$dest"
  echo "✅ Installed hook: ${hook_name}"
done

echo ""
echo "Git hooks installed. Every 'git push' will now run the test suite first."
