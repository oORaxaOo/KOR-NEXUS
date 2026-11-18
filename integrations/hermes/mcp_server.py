"""MCP stdio server exposing read-only KOR-NEXUS tools to Hermes Agent."""
from __future__ import annotations

from pathlib import Path
from typing import Literal
import sys

from mcp.server import MCPServer

if __package__ in (None, ""):
    # Hermes launches this file directly; make the repository/app root importable
    # regardless of the gateway's working directory.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from integrations.hermes.kor_client import KorNexusClient

RecordModule = Literal["atlas", "projects", "archive", "simulation", "database"]
ProjectStatus = Literal["", "geplant", "aktiv", "blockiert", "abgeschlossen", "unbekannt", "gemischt"]


def build_server(client: KorNexusClient | None = None) -> MCPServer:
    """Create an MCP server; injectable client keeps the tool layer testable."""
    kor = client or KorNexusClient()
    server = MCPServer("KOR-NEXUS")

    @server.tool()
    def kor_get_status() -> dict:
        """Read KOR-NEXUS application version, database status, backups and system summary."""
        return kor.get_status()

    @server.tool()
    def kor_get_system_health() -> dict:
        """Read local system health metrics reported by KOR-NEXUS."""
        return kor.get_system_health()

    @server.tool()
    def kor_list_tasks(limit: int = 50) -> dict:
        """List KOR-NEXUS tasks. The result is capped to 100 entries."""
        return kor.list_tasks(limit)

    @server.tool()
    def kor_list_projects(
        region: str = "",
        status: ProjectStatus = "",
        project_id: int = 0,
        limit: int = 50,
    ) -> dict:
        """List projects and their dashboard summaries, optionally filtered by region, status or ID."""
        return kor.list_projects(region, status, project_id, limit)

    @server.tool()
    def kor_list_records(module: RecordModule = "archive", limit: int = 30) -> dict:
        """Read KOR-NEXUS records from one module; valid modules are atlas, projects, archive, simulation and database."""
        return kor.list_records(module, limit)

    @server.tool()
    def kor_list_resources(limit: int = 50) -> dict:
        """List KOR-NEXUS resources and their current quantities."""
        return kor.list_resources(limit)

    @server.tool()
    def kor_list_news(limit: int = 20) -> dict:
        """Read the locally cached KOR-NEXUS RSS headlines without refreshing external feeds."""
        return kor.list_news(limit)

    return server


if __name__ == "__main__":
    # MCP stdio owns stdout; do not print application logs there.
    build_server().run()
