# Configuration reference

All variables are optional. Defaults target a local Ollama on this machine.

| Variable | Default | Meaning |
|---|---|---|
| `GRAPHIFY_LOCAL_MODEL` | `qwen2.5-coder:14b` | Text model for documents and community labeling |
| `GRAPHIFY_LOCAL_VISION_MODEL` | `qwen3-vl:8b` | Model used when the corpus contains images |
| `GRAPHIFY_LOCAL_BASE_URL` | `http://127.0.0.1:11434/v1` | OpenAI-compatible endpoint; loopback only |
| `GRAPHIFY_LOCAL_NUM_CTX` | `32768` | Context window passed to the backend |
| `GRAPHIFY_LOCAL_TIMEOUT` | `600` | Seconds per model request |
| `GRAPHIFY_LOCAL_MAX_CONCURRENCY` | `1` | Parallel model calls; keep at 1 for local models |

## Suggested models

| Use | Model | Notes |
|---|---|---|
| General text | `qwen2.5-coder:14b` | Default: reliable JSON labels, good code and prose extraction |
| Lighter text | `qwen3.5:9b` | Faster, but on this setup it returns empty label responses |
| Images / diagrams | `qwen3-vl:8b` | Only model used when images are present |
| Larger local model | `smtek/Qwen3.8-27B:Q3_K_M` | Tested end-to-end; ~1 min on a small corpus |
| Larger budget | `gpt-oss:20b` | More RAM, better long-document recall |

Switch with an environment variable, without editing files:

```bash
GRAPHIFY_LOCAL_MODEL=qwen3.5:9b graphify-local build .
```

## Troubleshooting

**Ollama not running**

```text
errore: Ollama non raggiungibile su http://127.0.0.1:11434/v1: ...
```

Start it with `systemctl start ollama` (or `ollama serve`). Do not retry in a
loop. For code-only questions use `graphify-local build . --code-only`, which
never contacts the model.

**Model not installed**

```text
errore: modello qwen3.5:9b assente
disponibili: ...
installa con: ollama pull qwen3.5:9b
```

Install it, or point `GRAPHIFY_LOCAL_MODEL` at one of the listed models.

**`openai` package missing**

```text
errore: il backend ollama richiede il pacchetto openai
installa con: uv tool install "graphifyy[ollama]" --force
```

The Ollama backend is an optional Graphify extra. Reinstall Graphify with it;
`--code-only` keeps working without it.

**Remote endpoint refused**

Any host other than `localhost`, `127.0.0.1`, `::1`, or `127.*` is rejected
before any network call. This is intentional: the wrapper never sends source
code off the machine.

**Graph missing**

`query` and `label` need `graphify-out/graph.json`. Run a `build` first.

**`--update` and documents**

`--update` re-extracts code only. Documents, PDFs, and images keep their previous
extraction until a full `build`. `--code-only` and `--deep` are ignored with
`--update`, and the wrapper prints a warning when you combine them.

**Graphify flags changed**

Run `graphify-local doctor`. It checks `graphify` on `PATH`, the endpoint, the
two models, and the flags the wrapper relies on (`--code-only`, `--backend`,
`--max-concurrency`, `--api-timeout`, `--mode`).
