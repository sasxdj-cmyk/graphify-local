# graphify-local

A local, offline bridge that lets [Graphify](https://github.com/Graphify-Labs/graphify)
build and query codebase knowledge graphs through [Ollama](https://ollama.com),
with no API keys and no data leaving your machine.

Repository: <https://github.com/sasxdj-cmyk/graphify-local>

## Requirements

- Python 3.10+
- [Graphify](https://github.com/Graphify-Labs/graphify) with the Ollama extra:
  `uv tool install "graphifyy[ollama]" --force`
- [Ollama](https://ollama.com) running locally
- A text model (default `qwen2.5-coder:14b`) and, for images, a vision model
  (default `qwen3-vl:8b`)

## Install

```bash
./install.sh
```

This symlinks the repository into
`~/.config/opencode/skills/graphify-local` so OpenCode discovers the skill,
and links the `graphify-local` launcher into `~/.local/bin` (or
`$XDG_BIN_HOME`). Make sure that directory is on your `PATH`.
Remove both with `./install.sh --uninstall`.

## Commands

```bash
graphify-local doctor
graphify-local build [PATH] [--code-only] [--deep] [--update]
graphify-local query "question" [PATH]
graphify-local label [PATH]
graphify-local status [PATH]
graphify-local config
```

`build --code-only` uses only the local AST pass: no model, no tokens, fully
offline. The default `build` also extracts documents and images through
Ollama and therefore needs the `openai` package shipped by the
`graphifyy[ollama]` extra; `graphify-local doctor` checks it.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Missing prerequisite (graph, model, backend package) or command failure |
| `2` | Invalid configuration (non-local endpoint, non-integer setting) |

`query` also propagates Graphify's own codes: `3` for an ambiguous name and
`4` when no node matches.

## Privacy

Only loopback endpoints are accepted (`localhost`, `127.0.0.1`, `::1`).
No API key is read, written, or required. Source files are never modified;
output goes to `graphify-out/`.

## License

MIT
