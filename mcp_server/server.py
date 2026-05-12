"""
MedSafe MCP Server — stdio transport for Claude Desktop.

Exposes shared-core tools directly to Claude. Claude acts as the orchestrator
in this path; the server only provides tools, resources, and prompt templates.

Usage (Claude Desktop config):
  {
    "mcpServers": {
      "medsafe": {
        "command": "/path/to/medsafe/backend/.venv/bin/python",
        "args": ["/path/to/medsafe/mcp_server/server.py"],
        "env": {
          "ANTHROPIC_API_KEY": "...",
          "OPENAI_API_KEY": "...",
          "DATABASE_URL": "...",
          "CHROMA_PERSIST_PATH": "/path/to/medsafe/data/chroma"
        }
      }
    }
  }
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Add backend to sys.path so shared-core modules are importable
_BACKEND = Path(__file__).parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_server.tools import register_tools
from mcp_server.resources import register_resources
from mcp_server.prompts import register_prompts


def _add_mcp_server_to_path() -> None:
    """Ensure mcp_server package itself is importable (needed for relative imports above)."""
    mcp_server_parent = Path(__file__).parent.parent
    if str(mcp_server_parent) not in sys.path:
        sys.path.insert(0, str(mcp_server_parent))


_add_mcp_server_to_path()

server = Server("medsafe")
register_tools(server)
register_resources(server)
register_prompts(server)


async def main() -> None:
    # Warm up ChromaDB and DB pool before accepting connections
    from rag.ingest import init_chroma
    init_chroma()

    from app.config import get_settings
    settings = get_settings()
    if settings.database_url:
        from db.client import get_pool
        await get_pool()

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
