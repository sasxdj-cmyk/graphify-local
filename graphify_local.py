"""graphify-local: a local Ollama bridge for Graphify."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import shutil
import subprocess
import sys
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
        model=source.get("GRAPHIFY_LOCAL_MODEL") or "qwen2.5-coder:14b",
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
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


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
        if any(part in _SKIP_DIRS for part in entry.relative_to(root).parts):
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
    edges = None
    if isinstance(data, dict):
        edges = data.get("edges")
        if not isinstance(edges, list):
            edges = data.get("links")
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
    env["OLLAMA_MODEL"] = cfg.vision_model if vision else cfg.model
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
    try:
        size = graph_path.stat().st_size
    except OSError as exc:
        print(f"errore: impossibile leggere {graph_path}: {exc}", file=sys.stderr)
        return 1
    print(f"grafo: {graph_path}")
    print(f"dimensione: {size} byte")
    summary = summarize_graph(graph_path)
    print(summary)
    return 1 if summary.startswith("graph.json illeggibile") else 0


def cmd_doctor(cfg: Config, env: Mapping[str, str] | None = None) -> int:
    ok = True

    which_env = os.environ if env is None else env
    graphify_path = shutil.which("graphify", path=which_env.get("PATH"))
    if graphify_path:
        print(f"OK   graphify: {graphify_path}")
    else:
        print("FAIL graphify: non trovato nel PATH (uv tool install graphifyy)")
        ok = False

    if graphify_path:
        if ollama_extra_available(graphify_path):
            print("OK   backend ollama: extra openai presente")
        else:
            print(
                'FAIL backend ollama: manca il pacchetto openai; '
                'esegui: uv tool install "graphifyy[ollama]" --force'
            )
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


def _graph_path(path: Path) -> Path:
    return Path(path) / "graphify-out" / "graph.json"


def _print_summary(path: Path) -> None:
    graph_path = _graph_path(path)
    print(f"grafo: {graph_path}")
    if graph_path.is_file():
        print(summarize_graph(graph_path))


def _require_graphify() -> bool:
    if shutil.which("graphify") is None:
        print("errore: graphify non trovato nel PATH", file=sys.stderr)
        print("installa con: uv tool install graphifyy", file=sys.stderr)
        return False
    return True


def _require_model(cfg: Config, model: str) -> bool:
    try:
        models = fetch_models(cfg.base_url, timeout=5.0)
    except (OSError, ValueError) as exc:
        print(f"errore: Ollama non raggiungibile su {cfg.base_url}: {exc}", file=sys.stderr)
        print("avvia con: systemctl start ollama", file=sys.stderr)
        return False
    if not model_present(models, model):
        print(f"errore: modello {model} assente", file=sys.stderr)
        print(f"disponibili: {', '.join(models) or 'nessuno'}", file=sys.stderr)
        print(f"installa con: ollama pull {model}", file=sys.stderr)
        return False
    return True


def _print_remote_error(base_url: str) -> None:
    print(f"errore: endpoint non locale: {base_url}", file=sys.stderr)
    print("sono ammessi solo localhost, 127.0.0.1 e ::1", file=sys.stderr)


def cmd_build(path: Path, *, code_only: bool, deep: bool, update: bool) -> int:
    project = Path(path).resolve()
    cfg = load_config()

    if update:
        if not is_loopback_url(cfg.base_url):
            _print_remote_error(cfg.base_url)
            return 2
        print(
            "attenzione: update ri-estrae solo il codice; i documenti non vengono aggiornati",
            file=sys.stderr,
        )
        ignored = []
        if code_only:
            ignored.append("--code-only")
        if deep:
            ignored.append("--deep")
        if ignored:
            print(f"attenzione: --update ignora {', '.join(ignored)}", file=sys.stderr)
        if not _require_graphify():
            return 1
        rc = run(build_update_command(project))
        if rc != 0:
            return rc
        _print_summary(project)
        return 0

    if not _require_graphify():
        return 1

    if code_only:
        rc = run(build_extract_command(project, cfg.model, cfg, code_only=True, deep=deep))
        if rc != 0:
            return rc
        _print_summary(project)
        return 0

    if not is_loopback_url(cfg.base_url):
        _print_remote_error(cfg.base_url)
        return 2

    if not ollama_extra_available():
        print(
            "errore: il backend ollama richiede il pacchetto openai",
            file=sys.stderr,
        )
        print('installa con: uv tool install "graphifyy[ollama]" --force', file=sys.stderr)
        return 1

    model, vision = resolve_model(cfg, project, code_only=False)
    if not _require_model(cfg, model):
        return 1

    env = graphify_env(cfg, vision=vision)
    rc = run(
        build_extract_command(project, model, cfg, code_only=False, deep=deep),
        env=env,
    )
    if rc != 0:
        return rc

    rc = _label_communities(project, cfg, model, env)
    if rc != 0:
        return rc

    _print_summary(project)
    return 0


def cmd_query(question: str, path: Path, budget: int) -> int:
    project = Path(path).resolve()
    graph_path = _graph_path(project)
    if not graph_path.is_file():
        print(f"errore: grafo assente: {graph_path}", file=sys.stderr)
        print("esegui prima: graphify-local build", file=sys.stderr)
        return 1
    if not _require_graphify():
        return 1
    return run(
        [
            "graphify",
            "query",
            question,
            "--graph",
            str(graph_path),
            "--budget",
            str(budget),
        ]
    )


def _label_communities(project: Path, cfg: Config, model: str, env: Mapping[str, str]) -> int:
    rc, output = run_capture(build_label_command(project, model, cfg), env=env)
    if rc != 0:
        return rc
    lowered = output.lower()
    if "labeling failed" in lowered or "placeholders" in lowered:
        print(
            "attenzione: labeling delle community fallito; restano etichette segnaposto",
            file=sys.stderr,
        )
        print(output.strip(), file=sys.stderr)
        return 1
    return 0


def cmd_label(path: Path) -> int:
    project = Path(path).resolve()
    graph_path = _graph_path(project)
    if not graph_path.is_file():
        print(f"errore: grafo assente: {graph_path}", file=sys.stderr)
        print("esegui prima: graphify-local build", file=sys.stderr)
        return 1
    if not _require_graphify():
        return 1
    cfg = load_config()
    if not is_loopback_url(cfg.base_url):
        print(f"errore: endpoint non locale: {cfg.base_url}", file=sys.stderr)
        return 2
    if not _require_model(cfg, cfg.model):
        return 1
    return _label_communities(project, cfg, cfg.model, graphify_env(cfg, vision=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="graphify-local",
        description="Graphify con Ollama locale: nessuna API key, nessun dato fuori dalla macchina.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_doctor = sub.add_parser("doctor", help="verifica prerequisiti e configurazione")
    p_doctor.set_defaults(func=lambda args: cmd_doctor(load_config()))

    p_build = sub.add_parser("build", help="costruisci o aggiorna il grafo")
    p_build.add_argument("path", nargs="?", default=".")
    p_build.add_argument("--code-only", action="store_true", help="solo AST locale, nessun LLM")
    p_build.add_argument("--deep", action="store_true", help="estrazione documenti piu' profonda")
    p_build.add_argument("--update", action="store_true", help="re-estrai solo i file di codice cambiati")
    p_build.set_defaults(
        func=lambda args: cmd_build(
            Path(args.path),
            code_only=args.code_only,
            deep=args.deep,
            update=args.update,
        )
    )

    p_query = sub.add_parser("query", help="interroga il grafo senza LLM")
    p_query.add_argument("question")
    p_query.add_argument("path", nargs="?", default=".")
    p_query.add_argument("--budget", type=int, default=2000)
    p_query.set_defaults(func=lambda args: cmd_query(args.question, Path(args.path), args.budget))

    p_label = sub.add_parser("label", help="rinomina le community con Ollama")
    p_label.add_argument("path", nargs="?", default=".")
    p_label.set_defaults(func=lambda args: cmd_label(Path(args.path)))

    p_status = sub.add_parser("status", help="mostra stato del grafo")
    p_status.add_argument("path", nargs="?", default=".")
    p_status.set_defaults(func=lambda args: cmd_status(Path(args.path)))

    p_config = sub.add_parser("config", help="mostra la configurazione effettiva")
    p_config.set_defaults(func=lambda args: cmd_config(load_config()))

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ValueError as exc:
        print(f"errore: {exc}", file=sys.stderr)
        return 2


def _graphify_python(graphify_path: str) -> str | None:
    try:
        first_line = Path(graphify_path).read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError):
        return None
    if not first_line.startswith("#!"):
        return None
    parts = first_line[2:].strip().split()
    if not parts:
        return None
    interpreter = parts[0]
    if Path(interpreter).name == "env" and len(parts) > 1:
        interpreter = parts[1]
    return interpreter


def ollama_extra_available(graphify_path: str | None = None) -> bool:
    path = graphify_path or shutil.which("graphify")
    if not path:
        return False
    interpreter = _graphify_python(path)
    if not interpreter:
        return False
    code, _ = run_capture([interpreter, "-c", "import openai"])
    return code == 0
