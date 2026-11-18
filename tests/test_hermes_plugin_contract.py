"""Static contract checks for the optional Hermes platform adapter."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "integrations" / "hermes" / "plugin" / "adapter.py"


class HermesPlatformContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = ADAPTER.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def test_gateway_message_handler_is_awaited(self):
        poll_loop = next(
            node for node in ast.walk(self.tree)
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == "_poll_loop"
        )
        awaited = [
            node for node in ast.walk(poll_loop)
            if isinstance(node, ast.Await)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "self"
            and node.value.func.attr == "handle_message"
        ]
        self.assertTrue(
            awaited,
            "Hermes BasePlatformAdapter.handle_message is async and must be awaited",
        )

    def test_platform_adapter_uses_private_bridge_and_rejects_redirects(self):
        self.assertIn('Authorization": f"Bearer {self.token}"', self.source)
        self.assertIn("class _NoRedirect", self.source)
        self.assertIn('parsed.hostname not in {"127.0.0.1", "localhost", "::1"}', self.source)
        self.assertIn('self._request_json, "POST", "/api/hermes/bridge/replies"', self.source)

    def test_platform_is_registered_as_a_separate_local_channel(self):
        self.assertIn('name="kor_nexus"', self.source)
        self.assertIn('allowed_users_env="KOR_NEXUS_ALLOWED_USERS"', self.source)
        self.assertIn('max_message_length=16000', self.source)


if __name__ == "__main__":
    unittest.main()
