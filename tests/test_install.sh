#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home"
export XDG_CONFIG_HOME="$tmp/config"
export XDG_BIN_HOME="$tmp/bin"
mkdir -p "$HOME"
"$repo/install.sh"
target="$XDG_CONFIG_HOME/opencode/skills/graphify-local"
test -L "$target" || { echo "FAIL: symlink skill mancante"; exit 1; }
test "$(readlink -f "$target")" = "$repo" || { echo "FAIL: symlink skill errato"; exit 1; }
launcher="$XDG_BIN_HOME/graphify-local"
test -L "$launcher" || { echo "FAIL: symlink launcher mancante"; exit 1; }
test "$(readlink -f "$launcher")" = "$repo/graphify-local" || { echo "FAIL: symlink launcher errato"; exit 1; }
"$launcher" --help >/dev/null || { echo "FAIL: launcher non eseguibile"; exit 1; }
"$repo/install.sh" --uninstall
test ! -e "$target" || { echo "FAIL: symlink skill non rimosso"; exit 1; }
test ! -e "$launcher" || { echo "FAIL: symlink launcher non rimosso"; exit 1; }
mkdir -p "$target"
if "$repo/install.sh" 2>/dev/null; then echo "FAIL: ha sovrascritto una directory reale"; exit 1; fi
echo "OK"
