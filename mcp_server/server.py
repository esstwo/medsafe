"""
MedSafe MCP Server — stdio transport for Claude Desktop.

Exposes shared-core tools directly to Claude. Claude acts as the orchestrator
in this path; the server only provides tools, resources, and prompt templates.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── Path setup (must happen before any local imports) ──────────────────────
_HERE = Path(__file__).parent          # mcp_server/
_BACKEND = _HERE.parent / "backend"   # backend/
_ROOT = _HERE.parent                  # repo root

# Insert in reverse priority so _HERE ends up at index 0
for _p in [str(_ROOT), str(_BACKEND), str(_HERE)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
# sys.path[0] is now _HERE (mcp_server/), so `from tools import` finds
# mcp_server/tools.py before backend/tools/__init__.py
# ───────────────────────────────────────────────────────────────────────────

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_tools import register_tools          # mcp_server/mcp_tools.py
from mcp_resources import register_resources  # mcp_server/mcp_resources.py
from mcp_prompts import register_prompts      # mcp_server/mcp_prompts.py

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
