---
name: graphify-local
description: "Use for a local, offline map of a codebase built with Ollama — no API keys, no data leaving the machine — or when graphify-out/ exists and the question is about architecture, relationships, or project content. Prefer it over the official graphify skill when the user wants offline operation or no API keys. Wraps Graphify so code is parsed with local AST and documents/images go through a local model."
metadata:
  opencode/autoinvoke: true
---

# graphify-local

Local bridge between [Graphify](https://github.com/Graphify-Labs/graphify) and
Ollama. Everything runs on this machine: no API key, no cloud call, no data
leaving localhost.

## When to use it

- The user asks for a map, overview, or architecture of a local project.
- The question spans many files or needs relationships between modules.
- `graphify-out/graph.json` already exists: treat the question as a graph query
  first.
- The user wants offline operation or asks about Ollama.

## When not to use it

- A single fact from one file: use `grep` and `read` directly.
- A one-off question on a tiny folder: reading the files is cheaper.
- The user needs cloud-grade extraction quality on large PDFs: say so instead of
  silently switching model.

## Commands

Always prefer `query`: it needs no model and burns no tokens.

```bash
graphify-local status [PATH]            # is there a graph, how big, how fresh
graphify-local query "question" [PATH]  # BFS over the graph, no LLM
graphify-local build [PATH] --code-only # AST only: no model, no tokens, offline
graphify-local build [PATH]             # code + docs + images through Ollama
graphify-local build [PATH] --update    # re-extract only changed code files
graphify-local label [PATH]             # rename communities with Ollama
graphify-local doctor                   # check graphify, Ollama, models, flags
graphify-local config                   # show effective configuration
```

Typical flow:

1. `graphify-local status` — if a graph exists and is recent, go to step 3.
2. `graphify-local build <path> --code-only` for code-only questions, otherwise
   `graphify-local build <path>`.
3. `graphify-local query "..." <path>`.
4. Read `graphify-out/graph.json` or the source file only if the query is not
   enough.

## Token rules

- Do not read `GRAPH_REPORT.md` in full. Query instead, or read a small slice.
- Do not paste `graph.json` into the conversation; use `query`.
- Build the graph only when the user asks for it or when you expect several
  questions on the same project.
- `--code-only` is free: prefer it whenever documents are not needed.
- Report paths and counts, not file bodies.

## Errors

- Ollama unreachable: say it plainly, suggest
  `systemctl start ollama`, and offer `--code-only` as the offline fallback.
- Missing model: the command lists available models and the `ollama pull` line.
- Missing backend package: reinstall Graphify with
  `uv tool install "graphifyy[ollama]" --force`; until then use `--code-only`.
- Non-local endpoint: the wrapper refuses anything but `localhost`, `127.0.0.1`,
  `::1`. Do not try to bypass it.
- No graph on `query`: run `build` first (or `--code-only`).

## Notes

- Output goes only to `graphify-out/`; source files are never modified.
- `--update` refreshes code only: documents and images stay stale until a full
  `build`.
- Details on variables and models: `references/config.md`.
