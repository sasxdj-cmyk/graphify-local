"""graphify-local: a local Ollama bridge for Graphify."""

from __future__ import annotations

import json
import os
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
