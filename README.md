# graphify-local

A local, offline bridge that lets [Graphify](https://github.com/Graphify-Labs/graphify)
build and query codebase knowledge graphs through [Ollama](https://ollama.com),
with no API keys and no data leaving your machine.

## Requirements

- Python 3.10+
- [Graphify](https://github.com/Graphify-Labs/graphify) (`uv tool install graphifyy`)
- [Ollama](https://ollama.com) running locally
- A text model (default `qwen3.5:9b`) and, for images, a vision model
  (default `qwen3-vl:8b`)

## Install

```bash
./install.sh
```

This symlinks the repository into
`~/.config/opencode/skills/graphify-local` so OpenCode discovers the skill.
Remove it with `./install.sh --uninstall`.

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
Ollama.

## Privacy

Only loopback endpoints are accepted (`localhost`, `127.0.0.1`, `::1`).
No API key is read, written, or required. Source files are never modified;
output goes to `graphify-out/`.

## License

MIT
