import sys
import unittest
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
