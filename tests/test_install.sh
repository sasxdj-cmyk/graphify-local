#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"
export XDG_CONFIG_HOME="$tmp/config"
mkdir -p "$HOME"
"$repo/install.sh"
target="$XDG_CONFIG_HOME/opencode/skills/graphify-local"
test -L "$target" || { echo "FAIL: symlink mancante"; exit 1; }
test "$(readlink -f "$target")" = "$repo" || { echo "FAIL: symlink errato"; exit 1; }
"$repo/install.sh" --uninstall
test ! -e "$target" || { echo "FAIL: symlink non rimosso"; exit 1; }
mkdir -p "$target"
if "$repo/install.sh" 2>/dev/null; then echo "FAIL: ha sovrascritto una directory reale"; exit 1; fi
echo "OK"
