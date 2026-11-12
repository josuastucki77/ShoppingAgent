import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from bootstrap import configure, has_daily_job
from check_services import load_dotenv
from mcp_client import MCPClient


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "data"
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "SOUL.md").write_text("Original personality", encoding="utf-8")

    def test_second_setup_preserves_personality_memory_and_custom_settings(self):
        configure(self.home, self.project, {})
        (self.home / "SOUL.md").write_text("Personalized", encoding="utf-8")
        (self.home / "shopping" / "history.txt").write_text("existing memory", encoding="utf-8")
        config_path = self.home / "config.yaml"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["mcp_servers"]["other"] = {"url": "https://example.org"}
        config["custom_setting"] = 42
        config_path.write_text(json.dumps(config), encoding="utf-8")
        configure(self.home, self.project, {})
        before = {p.name: p.read_bytes() for p in self.home.iterdir() if p.is_file()}
        configure(self.home, self.project, {})
        after = {p.name: p.read_bytes() for p in self.home.iterdir() if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual((self.home / "SOUL.md").read_text(encoding="utf-8"), "Personalized")
        self.assertEqual((self.home / "shopping" / "history.txt").read_text(), "existing memory")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["custom_setting"], 42)
        self.assertIn("other", config["mcp_servers"])

    def test_identity_change_fails_before_mutation(self):
        configure(self.home, self.project, {"SHOPPING_USER": "alice"})
        before = (self.home / "config.yaml").read_bytes()
        with self.assertRaisesRegex(ValueError, "Identitaet"):
            configure(self.home, self.project, {"SHOPPING_USER": "bob"})
        self.assertEqual((self.home / "config.yaml").read_bytes(), before)

    def test_official_entrypoint_stock_personality_is_replaced(self):
        stock = self.root / "stock-soul.md"
        stock.write_text("Image default", encoding="utf-8")
        self.home.mkdir()
        (self.home / "SOUL.md").write_text("Image default", encoding="utf-8")
        configure(self.home, self.project, {}, stock_soul=stock)
        self.assertEqual((self.home / "SOUL.md").read_text(), "Original personality")

    def test_existing_job_is_detected_without_rewriting_store(self):
        path = self.root / "jobs.json"
        data = {"jobs": [{"name": "other"}, {"name": "shopping-daily", "enabled": False}]}
        path.write_text(json.dumps(data), encoding="utf-8")
        before = path.read_bytes()
        self.assertTrue(has_daily_job(path))
        self.assertEqual(before, path.read_bytes())
        path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            has_daily_job(path)

    def test_mcp_sse_handles_notifications_and_correlates_response(self):
        response = ('event: message\r\ndata: {"jsonrpc":"2.0","method":"progress"}\r\n\r\n'
                    'event: message\r\ndata: {"id":7,"result":{"tools":[]}}\r\n\r\n')
        self.assertEqual(MCPClient.decode(response, 7), {"tools": []})
        with self.assertRaises(RuntimeError):
            MCPClient.decode('{"id":7,"error":{"code":-1,"message":"failure"}}', 7)

    def test_dotenv_treats_shell_expressions_as_data_and_keeps_environment(self):
        path = self.root / ".env"
        path.write_text('SHOPPING_CRON="0 9 * * *"\nVALUE=$(do-not-execute)\nEXISTING=new\n')
        with patch.dict(os.environ, {"EXISTING": "old"}, clear=True):
            load_dotenv(path)
            self.assertEqual(os.environ["SHOPPING_CRON"], "0 9 * * *")
            self.assertEqual(os.environ["VALUE"], "$(do-not-execute)")
            self.assertEqual(os.environ["EXISTING"], "old")


if __name__ == "__main__":
    unittest.main()
