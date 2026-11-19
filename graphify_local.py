"""graphify-local: a local Ollama bridge for Graphify."""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Mapping, Sequence
from urllib.parse import urlparse


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
