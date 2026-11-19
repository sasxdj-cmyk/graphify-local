#!/usr/bin/env bash
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
target="$config_home/opencode/skills/graphify-local"

uninstall=0
case "${1:-}" in
  --uninstall) uninstall=1 ;;
  "") ;;
  *) echo "usage: $0 [--uninstall]" >&2; exit 2 ;;
esac

if [ "$uninstall" -eq 1 ]; then
  if [ -L "$target" ]; then
    current="$(readlink -f "$target" || true)"
    if [ "$current" = "$repo" ]; then
      rm "$target"
      echo "removed: $target"
    else
      echo "refusing: $target points to $current, not $repo" >&2
      exit 1
    fi
  elif [ -e "$target" ]; then
    echo "refusing: $target exists and is not a symlink" >&2
    exit 1
  else
    echo "nothing to remove: $target"
  fi
  exit 0
fi

mkdir -p "$(dirname "$target")"

if [ -L "$target" ]; then
  current="$(readlink -f "$target" || true)"
  if [ "$current" = "$repo" ]; then
    echo "already installed: $target"
    exit 0
  fi
  echo "refusing: $target points to $current, not $repo" >&2
  exit 1
fi

if [ -e "$target" ]; then
  echo "refusing: $target exists and is not a symlink" >&2
  exit 1
fi

ln -s "$repo" "$target"
echo "installed: $target -> $repo"

for f in graphify-local graphify_local.py; do
  if [ -f "$repo/$f" ]; then
    chmod +x "$repo/$f"
  fi
done

if ! command -v graphify >/dev/null 2>&1; then
  echo "warning: graphify is not on PATH; install it with: uv tool install graphifyy" >&2
fi
