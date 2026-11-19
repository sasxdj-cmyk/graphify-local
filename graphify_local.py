"""graphify-local: a local Ollama bridge for Graphify."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlparse

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_SKIP_DIRS = {".git", "node_modules", "graphify-out", ".venv", "venv", "__pycache__"}


@dataclass(frozen=True)
class Config:
    model: str
    vision_model: str
    base_url: str
    num_ctx: int
    timeout: int
    max_concurrency: int


def _int_value(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} deve essere un intero, ricevuto {raw!r}") from exc


def load_config(env: Mapping[str, str] | None = None) -> Config:
    source = os.environ if env is None else env
    return Config(
        model=source.get("GRAPHIFY_LOCAL_MODEL") or "qwen3.5:9b",
        vision_model=source.get("GRAPHIFY_LOCAL_VISION_MODEL") or "qwen3-vl:8b",
        base_url=source.get("GRAPHIFY_LOCAL_BASE_URL") or "http://127.0.0.1:11434/v1",
        num_ctx=_int_value(source, "GRAPHIFY_LOCAL_NUM_CTX", 32768),
        timeout=_int_value(source, "GRAPHIFY_LOCAL_TIMEOUT", 600),
        max_concurrency=_int_value(source, "GRAPHIFY_LOCAL_MAX_CONCURRENCY", 1),
    )


def is_loopback_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"} or host.startswith("127.")


def fetch_models(base_url: str, timeout: float = 5.0) -> list[str]:
    url = base_url.rstrip("/") + "/models"
    with urllib.request.urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    data = payload.get("data")
    if not isinstance(data, list):
        raise ValueError("risposta /models priva della lista 'data'")
    return [
        item["id"]
        for item in data
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]


def model_present(models: Sequence[str], name: str) -> bool:
    return name in models


def detect_images(root: Path) -> bool:
    root = Path(root)
    if not root.exists():
        return False
    for entry in root.rglob("*"):
        if any(part in _SKIP_DIRS for part in entry.parts):
            continue
        if entry.is_file() and entry.suffix.lower() in _IMAGE_SUFFIXES:
            return True
    return False


def resolve_model(cfg: Config, root: Path, code_only: bool) -> tuple[str, bool]:
    if code_only:
        return cfg.model, False
    if detect_images(Path(root)):
        return cfg.vision_model, True
    return cfg.model, False


def build_extract_command(
    path: Path,
    model: str,
    cfg: Config,
    *,
    code_only: bool,
    deep: bool,
) -> list[str]:
    command = ["graphify", "extract", str(path)]
    if code_only:
        command.append("--code-only")
    else:
        command.extend(
            [
                "--backend",
                "ollama",
                "--model",
                model,
                "--max-concurrency",
                str(cfg.max_concurrency),
                "--api-timeout",
                str(cfg.timeout),
            ]
        )
    if deep:
        command.extend(["--mode", "deep"])
    return command


def build_label_command(path: Path, model: str, cfg: Config) -> list[str]:
    return [
        "graphify",
        "label",
        str(path),
        "--backend",
        "ollama",
        "--model",
        model,
        "--max-concurrency",
        str(cfg.max_concurrency),
    ]


def build_update_command(path: Path) -> list[str]:
    return ["graphify", "update", str(path)]


def summarize_graph(graph_path: Path) -> str:
    path = Path(graph_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"graph.json illeggibile: {path}"
    nodes = data.get("nodes") if isinstance(data, dict) else None
    edges = data.get("edges") if isinstance(data, dict) else None
    return f"{len(nodes) if isinstance(nodes, list) else 0} nodi, {len(edges) if isinstance(edges, list) else 0} archi"


def run(cmd: Sequence[str], env: Mapping[str, str] | None = None, cwd: Path | None = None) -> int:
    completed = subprocess.run(list(cmd), env=None if env is None else dict(env), cwd=cwd)
    return completed.returncode


def run_capture(
    cmd: Sequence[str],
    env: Mapping[str, str] | None = None,
    cwd: Path | None = None,
) -> tuple[int, str]:
    completed = subprocess.run(
        list(cmd),
        env=None if env is None else dict(env),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.returncode, completed.stdout or ""


def graphify_env(cfg: Config, *, vision: bool) -> dict[str, str]:
    env = dict(os.environ)
    env["OLLAMA_BASE_URL"] = cfg.base_url
    env["OLLAMA_MODEL"] = cfg.model
    env["GRAPHIFY_OLLAMA_NUM_CTX"] = str(cfg.num_ctx)
    if vision:
        env["GRAPHIFY_OLLAMA_VISION"] = "1"
    else:
        env.pop("GRAPHIFY_OLLAMA_VISION", None)
    return env


def cmd_config(cfg: Config) -> int:
    print(f"modello: {cfg.model}")
    print(f"modello vision: {cfg.vision_model}")
    print(f"base url: {cfg.base_url}")
    print(f"num ctx: {cfg.num_ctx}")
    print(f"timeout: {cfg.timeout}")
    print(f"max concurrency: {cfg.max_concurrency}")
    return 0


def cmd_status(path: Path) -> int:
    graph_path = Path(path) / "graphify-out" / "graph.json"
    if not graph_path.is_file():
        print(f"nessun grafo: atteso {graph_path}")
        print("esegui: graphify-local build")
        return 1
    size = graph_path.stat().st_size
    print(f"grafo: {graph_path}")
    print(f"dimensione: {size} byte")
    print(summarize_graph(graph_path))
    return 0


def cmd_doctor(cfg: Config, env: Mapping[str, str] | None = None) -> int:
    ok = True

    graphify_path = shutil.which("graphify")
    if graphify_path:
        print(f"OK   graphify: {graphify_path}")
    else:
        print("FAIL graphify: non trovato nel PATH (uv tool install graphifyy)")
        ok = False

    if is_loopback_url(cfg.base_url):
        print(f"OK   endpoint: {cfg.base_url}")
    else:
        print(f"FAIL endpoint: {cfg.base_url} non e' locale; sono ammessi solo localhost/127.0.0.1/::1")
        return 2

    try:
        models = fetch_models(cfg.base_url, timeout=5.0)
    except (OSError, ValueError) as exc:
        print(f"FAIL ollama: {exc} (avvia Ollama con: systemctl start ollama)")
        models = None
        ok = False
    else:
        print(f"OK   ollama: {len(models)} modelli disponibili")

    if models is not None:
        for label, name in (("modello", cfg.model), ("modello vision", cfg.vision_model)):
            if model_present(models, name):
                print(f"OK   {label}: {name}")
            else:
                print(f"FAIL {label}: {name} assente; ollama pull {name}")
                ok = False

    if graphify_path:
        code, help_text = run_capture(["graphify", "--help"])
        if code != 0:
            print(f"FAIL graphify --help: exit {code}")
            ok = False
        for flag in ("--code-only", "--backend", "--max-concurrency", "--api-timeout", "--mode"):
            if flag in help_text:
                print(f"OK   flag: {flag}")
            else:
                print(f"FAIL flag: {flag} non supportato da questa versione di graphify")
                ok = False

    return 0 if ok else 1
