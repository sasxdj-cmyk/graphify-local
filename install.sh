#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"
skill_target="$config_home/opencode/skills/graphify-local"
bin_target="$bin_home/graphify-local"

uninstall=0
case "${1:-}" in
  --uninstall) uninstall=1 ;;
  "") ;;
  *) echo "usage: $0 [--uninstall]" >&2; exit 2 ;;
esac

is_ours() {
  [ -L "$1" ] && [ "$(readlink -f "$1" || true)" = "$2" ]
}

check_free() {
  local target="$1" source="$2"
  if is_ours "$target" "$source"; then
    return 0
  fi
  if [ -e "$target" ] || [ -L "$target" ]; then
    echo "refusing: $target exists and does not point to $source" >&2
    exit 1
  fi
}

if [ "$uninstall" -eq 1 ]; then
  for pair in "$skill_target:$repo" "$bin_target:$repo/graphify-local"; do
    target="${pair%%:*}"
    source="${pair#*:}"
    if is_ours "$target" "$source"; then
      rm "$target"
      echo "removed: $target"
    elif [ -e "$target" ] || [ -L "$target" ]; then
      echo "refusing: $target does not point to $source" >&2
      exit 1
    else
      echo "nothing to remove: $target"
    fi
  done
  exit 0
fi

check_free "$skill_target" "$repo"
check_free "$bin_target" "$repo/graphify-local"

mkdir -p "$(dirname "$skill_target")" "$bin_home"

for f in graphify-local graphify_local.py; do
  if [ -f "$repo/$f" ]; then
    chmod +x "$repo/$f"
  fi
done

if ! is_ours "$skill_target" "$repo"; then
  ln -s "$repo" "$skill_target"
  echo "installed: $skill_target -> $repo"
else
  echo "already installed: $skill_target"
fi

if ! is_ours "$bin_target" "$repo/graphify-local"; then
  ln -s "$repo/graphify-local" "$bin_target"
  echo "installed: $bin_target -> $repo/graphify-local"
else
  echo "already installed: $bin_target"
fi

if ! command -v graphify >/dev/null 2>&1; then
  echo "warning: graphify is not on PATH; install it with: uv tool install \"graphifyy[ollama]\"" >&2
fi

case ":$PATH:" in
  *":$bin_home:"*) ;;
  *) echo "warning: $bin_home is not on PATH; add it to use graphify-local" >&2 ;;
esac
