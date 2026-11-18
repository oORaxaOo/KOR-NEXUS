import asyncio
import json
import unittest

from mcp import Client

from integrations.hermes.mcp_server import build_server


class FakeKorClient:
    def get_status(self):
        return {"ok": True, "app": "KOR-NEXUS", "version": "test"}

    def get_system_health(self):
        return {"ram_used_pct": 12.5}

    def list_tasks(self, limit=50):
        return {"items": [], "returned": 0, "truncated": False}

    def list_projects(self, region="", status="", project_id=0, limit=50):
        return {"items": [], "returned": 0, "truncated": False}

    def list_records(self, module="archive", limit=30):
        return {"items": [], "returned": 0, "truncated": False, "module": module}

    def list_resources(self, limit=50):
        return {"items": [], "returned": 0, "truncated": False}

    def list_news(self, limit=20):
        return {"items": [], "returned": 0, "truncated": False}


class HermesMcpServerTests(unittest.TestCase):
    def test_server_exposes_expected_tools_over_mcp(self):
        async def exercise():
            server = build_server(FakeKorClient())
            async with Client(server, raise_exceptions=True) as client:
                result = await client.list_tools()
                names = {item.name for item in result.tools}
                self.assertTrue({
                    "kor_get_status",
                    "kor_get_system_health",
                    "kor_list_tasks",
                    "kor_list_projects",
                    "kor_list_records",
                    "kor_list_resources",
                    "kor_list_news",
                }.issubset(names))
                response = await client.call_tool("kor_get_status", {})
                self.assertFalse(response.is_error)
                self.assertEqual(json.loads(response.content[0].text)['app'], 'KOR-NEXUS')

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
