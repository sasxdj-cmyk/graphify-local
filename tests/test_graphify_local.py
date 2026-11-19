import os
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import graphify_local as gl


class ConfigTests(unittest.TestCase):
    def test_defaults_match_design(self):
        cfg = gl.load_config({})
        self.assertEqual(cfg.model, "qwen3.5:9b")
        self.assertEqual(cfg.vision_model, "qwen3-vl:8b")
        self.assertEqual(cfg.base_url, "http://127.0.0.1:11434/v1")
        self.assertEqual(cfg.num_ctx, 32768)
        self.assertEqual(cfg.timeout, 600)
        self.assertEqual(cfg.max_concurrency, 1)

    def test_env_overrides(self):
        cfg = gl.load_config({
            "GRAPHIFY_LOCAL_MODEL": "m",
            "GRAPHIFY_LOCAL_NUM_CTX": "8192",
            "GRAPHIFY_LOCAL_TIMEOUT": "120",
        })
        self.assertEqual(cfg.model, "m")
        self.assertEqual(cfg.num_ctx, 8192)
        self.assertEqual(cfg.timeout, 120)

    def test_loopback_only(self):
        self.assertTrue(gl.is_loopback_url("http://localhost:11434/v1"))
        self.assertTrue(gl.is_loopback_url("http://127.0.0.1:11434/v1"))
        self.assertTrue(gl.is_loopback_url("http://[::1]:11434/v1"))
        self.assertFalse(gl.is_loopback_url("http://192.168.1.10:11434/v1"))
        self.assertFalse(gl.is_loopback_url("https://example.com/v1"))
        self.assertFalse(gl.is_loopback_url("ftp://localhost/v1"))

    def test_model_present(self):
        self.assertTrue(gl.model_present(["qwen3.5:9b", "x"], "qwen3.5:9b"))
        self.assertFalse(gl.model_present(["qwen3.5:9b-q8_0"], "qwen3.5:9b"))


class CorpusTests(unittest.TestCase):
    def test_detect_images_ignores_graphify_out(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "graphify-out").mkdir()
            (root / "graphify-out" / "x.png").write_bytes(b"")
            self.assertFalse(gl.detect_images(root))
            (root / "a.png").write_bytes(b"")
            self.assertTrue(gl.detect_images(root))

    def test_resolve_model_prefers_vision_for_images(self):
        cfg = gl.load_config({})
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(gl.resolve_model(cfg, root, False), (cfg.model, False))
            (root / "a.webp").write_bytes(b"")
            self.assertEqual(gl.resolve_model(cfg, root, False), (cfg.vision_model, True))
            self.assertEqual(gl.resolve_model(cfg, root, True), (cfg.model, False))

    def test_extract_command_flags(self):
        cfg = gl.load_config({})
        cmd = gl.build_extract_command(Path("/p"), "m", cfg, code_only=True, deep=False)
        self.assertEqual(cmd[0], "graphify")
        self.assertIn("extract", cmd)
        self.assertIn("--code-only", cmd)
        self.assertNotIn("--mode", cmd)

        cmd = gl.build_extract_command(Path("/p"), "m", cfg, code_only=False, deep=True)
        self.assertIn("ollama", cmd)
        self.assertIn("--backend", cmd)
        self.assertIn("--model", cmd)
        self.assertIn("--max-concurrency", cmd)
        self.assertIn("--api-timeout", cmd)
        self.assertIn("--mode", cmd)
        self.assertIn("deep", cmd)

    def test_summary_counts_and_malformed(self):
        with tempfile.TemporaryDirectory() as d:
            g = Path(d) / "graph.json"
            g.write_text('{"nodes": [{}, {}], "edges": [{}]}')
            self.assertEqual(gl.summarize_graph(g), "2 nodi, 1 archi")
            g.write_text("not json")
            self.assertIn("illeggibile", gl.summarize_graph(g))


class DoctorTests(unittest.TestCase):
    def test_doctor_ok_with_models(self):
        cfg = gl.load_config({})
        help_text = (
            "--code-only --backend --max-concurrency --api-timeout --mode"
        )
        with mock.patch.object(gl.shutil, "which", return_value="/usr/bin/graphify"), \
             mock.patch.object(gl, "fetch_models", return_value=[cfg.model, cfg.vision_model]), \
             mock.patch.object(gl, "run_capture", return_value=(0, help_text)):
            self.assertEqual(gl.cmd_doctor(cfg, {"PATH": "/usr/bin:/bin"}), 0)

    def test_doctor_reports_missing_model(self):
        cfg = gl.load_config({})
        help_text = (
            "--code-only --backend --max-concurrency --api-timeout --mode"
        )
        with mock.patch.object(gl.shutil, "which", return_value="/usr/bin/graphify"), \
             mock.patch.object(gl, "fetch_models", return_value=["altro:1b"]), \
             mock.patch.object(gl, "run_capture", return_value=(0, help_text)):
            self.assertEqual(gl.cmd_doctor(cfg, {}), 1)

    def test_doctor_handles_unreachable_ollama(self):
        cfg = gl.load_config({})
        help_text = (
            "--code-only --backend --max-concurrency --api-timeout --mode"
        )
        with mock.patch.object(gl.shutil, "which", return_value="/usr/bin/graphify"), \
             mock.patch.object(gl, "fetch_models", side_effect=OSError("connection refused")), \
             mock.patch.object(gl, "run_capture", return_value=(0, help_text)):
            self.assertEqual(gl.cmd_doctor(cfg, {}), 1)

    def test_doctor_rejects_remote_url(self):
        cfg = gl.load_config({"GRAPHIFY_LOCAL_BASE_URL": "http://10.0.0.5:11434/v1"})
        with mock.patch.object(gl.shutil, "which", return_value="/usr/bin/graphify"), \
             mock.patch.object(gl, "run_capture", return_value=(0, "")):
            self.assertEqual(gl.cmd_doctor(cfg, {}), 2)

    def test_status_missing_and_present(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(gl.cmd_status(root), 1)
            out = root / "graphify-out"
            out.mkdir()
            (out / "graph.json").write_text('{"nodes": [], "edges": []}')
            self.assertEqual(gl.cmd_status(root), 0)

    def test_env_sets_ollama_and_vision(self):
        cfg = gl.load_config({})
        env = gl.graphify_env(cfg, vision=True)
        self.assertEqual(env["OLLAMA_BASE_URL"], cfg.base_url)
        self.assertEqual(env["OLLAMA_MODEL"], cfg.model)
        self.assertEqual(env["GRAPHIFY_OLLAMA_NUM_CTX"], "32768")
        self.assertEqual(env["GRAPHIFY_OLLAMA_VISION"], "1")
        self.assertNotIn("GRAPHIFY_OLLAMA_VISION", gl.graphify_env(cfg, vision=False))


class CliTests(unittest.TestCase):
    def _fake_graphify(self, bin_dir: Path, record: Path, body: str = "") -> None:
        script = bin_dir / "graphify"
        script.write_text(
            "#!/usr/bin/env python3\n"
            "import sys, pathlib\n"
            f"pathlib.Path({str(record)!r}).write_text(' '.join(sys.argv[1:]))\n"
            + body
        )
        script.chmod(0o755)

    def test_build_code_only_calls_graphify(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            project = root / "progetto con spazi"
            project.mkdir()
            (project / "a.py").write_text("def a(): pass\n")
            bin_dir = root / "bin"
            bin_dir.mkdir()
            record = root / "args.txt"
            self._fake_graphify(bin_dir, record)
            env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "GRAPHIFY_LOCAL_MODEL": "m"}
            old = dict(os.environ)
            os.environ.update(env)
            try:
                rc = gl.main(["build", str(project), "--code-only"])
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(rc, 0)
            self.assertIn("extract", record.read_text())
            self.assertIn("--code-only", record.read_text())

    def test_build_rejects_remote_url_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            os.environ["GRAPHIFY_LOCAL_BASE_URL"] = "http://10.0.0.5:11434/v1"
            try:
                rc = gl.main(["build", str(project)])
            finally:
                del os.environ["GRAPHIFY_LOCAL_BASE_URL"]
            self.assertEqual(rc, 2)

    def test_query_missing_graph(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(gl.cmd_query("x", Path(d), 2000), 1)

    def test_update_warns_docs_stale(self):
        with tempfile.TemporaryDirectory() as d:
            project = Path(d)
            (project / "graphify-out").mkdir()
            (project / "graphify-out" / "graph.json").write_text('{"nodes": [], "edges": []}')
            with mock.patch.object(gl, "run", return_value=0), \
                 mock.patch("sys.stderr") as err:
                rc = gl.cmd_build(project, code_only=False, deep=False, update=True)
            self.assertEqual(rc, 0)
            self.assertIn("documenti", err.write.call_args_list[0].args[0].lower())
