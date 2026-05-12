from typing import Any

import asyncpg


async def upsert_interaction(pool: asyncpg.Pool, record: dict[str, Any]) -> None:
    await pool.execute(
        """
        INSERT INTO drug_interactions
            (rxcui_a, rxcui_b, drug_a_name, drug_b_name, severity, description, drugbank_id, source)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (LEAST(rxcui_a, rxcui_b), GREATEST(rxcui_a, rxcui_b))
        DO UPDATE SET
            severity    = EXCLUDED.severity,
            description = EXCLUDED.description,
            drugbank_id = EXCLUDED.drugbank_id
        """,
        record["rxcui_a"],
        record["rxcui_b"],
        record.get("drug_a_name"),
        record.get("drug_b_name"),
        record.get("severity", "unknown"),
        record.get("description"),
        record.get("drugbank_id"),
        record.get("source", "drugbank"),
    )


async def lookup_interaction(
    pool: asyncpg.Pool, rxcui_a: str, rxcui_b: str
) -> dict[str, Any] | None:
    row = await pool.fetchrow(
        """
        SELECT rxcui_a, rxcui_b, drug_a_name, drug_b_name, severity, description, drugbank_id, source
        FROM drug_interactions
        WHERE (rxcui_a = $1 AND rxcui_b = $2)
           OR (rxcui_a = $2 AND rxcui_b = $1)
        LIMIT 1
        """,
        rxcui_a,
        rxcui_b,
    )
    return dict(row) if row else None


async def list_all_interactions(pool: asyncpg.Pool) -> list[dict[str, Any]]:
    rows = await pool.fetch(
        "SELECT rxcui_a, rxcui_b, drug_a_name, drug_b_name, severity, description, drugbank_id FROM drug_interactions"
    )
    return [dict(r) for r in rows]
