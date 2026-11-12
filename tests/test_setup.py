import json
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from bootstrap import configure, has_daily_job
from check_services import check_ollama, load_dotenv
from mcp_client import MCPClient
from cron_context import collect
from urllib.error import HTTPError


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "data"
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "SOUL.md").write_text("Original personality", encoding="utf-8")
        (self.project / "prompts").mkdir()
        (self.project / "prompts" / "shopping-guide.md").write_text(
            '<!-- shopping-agent-managed-context -->\nModel {{MODEL}}\n', encoding='utf-8')

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

    def test_custom_workspace_instructions_are_preserved(self):
        self.home.mkdir()
        instructions = self.home / 'AGENTS.md'
        instructions.write_text('Personal workspace instructions', encoding='utf-8')
        configure(self.home, self.project, {})
        self.assertEqual(instructions.read_text(), 'Personal workspace instructions')

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

    def test_preflight_rejects_context_too_small_for_hermes(self):
        with patch.dict(os.environ, {"OLLAMA_MODEL": "test-model:latest"}, clear=True), patch('check_services.json_request') as request:
            request.side_effect = [
                {"models": [{"name": "test-model:latest"}, {"name": "nomic-embed-text:latest"}]},
                {"capabilities": ["completion", "tools"], "parameters": "num_ctx 32768\n"},
            ]
            with self.assertRaisesRegex(RuntimeError, "64000"):
                check_ollama()

    def test_cron_receives_honcho_data_and_only_response_product_links(self):
        configure(self.home, self.project, {})
        output = self.home / 'cron' / 'output' / 'test-job'
        output.mkdir()
        url = 'https://www.galaxus.ch/de/s1/product/example-123'
        (output / 'report.md').write_text(
            'Prompt: https://www.galaxus.ch/ignore-template-999\n'
            '## Response\nRecommended: [' + url + '](' + url + ')', encoding='utf-8')
        context = {'representation': 'Budget CHF 149, Smart Home'}
        with patch('cron_context.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(context).encode())):
            result = collect(self.home)
        self.assertEqual(result['honcho_context'], context)
        self.assertEqual(result['previous_product_urls_30_days'], [url])

    def test_cron_does_not_disguise_honcho_outage_as_empty_profile(self):
        configure(self.home, self.project, {})
        missing = HTTPError('http://honcho/peer', 404, 'new user', {}, None)
        with patch('cron_context.urllib.request.urlopen', side_effect=[missing, io.BytesIO(b'{}')]):
            self.assertTrue(collect(self.home)['honcho_context']['empty_profile'])
        unavailable = HTTPError('http://honcho/peer', 503, 'unavailable', {}, None)
        with patch('cron_context.urllib.request.urlopen', side_effect=unavailable):
            with self.assertRaises(HTTPError):
                collect(self.home)


if __name__ == "__main__":
    unittest.main()
