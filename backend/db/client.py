import asyncpg

from app.config import get_settings

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None or _pool._closed:
        settings = get_settings()
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            statement_cache_size=0,  # required for Supabase pgBouncer compatibility
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool and not _pool._closed:
        await _pool.close()
    _pool = None
