#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
printf 'def alpha():\n    return 1\n' > "$tmp/a.py"
printf '# note\n' > "$tmp/notes.md"
"$repo/graphify-local" build "$tmp" --code-only
test -f "$tmp/graphify-out/graph.json"
"$repo/graphify-local" status "$tmp"
"$repo/graphify-local" query "alpha" "$tmp" --budget 200
echo "SMOKE OK"
