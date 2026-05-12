"""MCP resources — URI-addressable drug profiles and interaction pairs."""

from __future__ import annotations

from mcp.server import Server
from mcp.types import Resource, TextContent


def register_resources(server: Server) -> None:

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [
            Resource(
                uri="medsafe://drug/{rxcui}",
                name="Drug Profile",
                description="Drug name, type, and known interaction count for an RXCUI",
                mimeType="application/json",
            ),
            Resource(
                uri="medsafe://interaction/{rxcui_a}/{rxcui_b}",
                name="Interaction Record",
                description="Known interaction between two drugs identified by RXCUI",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        import json
        from tools.rxnorm import get_drug_info

        if uri.startswith("medsafe://drug/"):
            rxcui = uri.removeprefix("medsafe://drug/")
            info = await get_drug_info(rxcui)
            if info:
                return json.dumps({
                    "rxcui": info["rxcui"],
                    "name": info["name"],
                    "tty": info["tty"],
                    "is_prescription": info["is_prescription"],
                    "brand_names": info["brand_names"][:5],
                })
            return json.dumps({"error": f"No drug found for RXCUI {rxcui}"})

        if uri.startswith("medsafe://interaction/"):
            parts = uri.removeprefix("medsafe://interaction/").split("/")
            if len(parts) != 2:
                return json.dumps({"error": "Invalid URI — expected medsafe://interaction/{rxcui_a}/{rxcui_b}"})
            rxcui_a, rxcui_b = parts
            try:
                from db.client import get_pool
                from db.interactions import lookup_interaction
                pool = await get_pool()
                row = await lookup_interaction(pool, rxcui_a, rxcui_b)
                if row:
                    return json.dumps(row)
                return json.dumps({"note": f"No known interaction between {rxcui_a} and {rxcui_b} in database."})
            except Exception as exc:
                return json.dumps({"error": str(exc)})

        return json.dumps({"error": f"Unknown resource URI: {uri}"})
