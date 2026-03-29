"""Redis-based caching for backtest results."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# Default TTL: 24 hours
CACHE_TTL_SECONDS = 86400
CACHE_KEY_PREFIX = "backtest:"


def _hash_config(config: dict) -> str:
    """Create a deterministic SHA256 hash of backtest config parameters."""
    # Sort keys for deterministic serialization
    canonical = json.dumps(config, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class BacktestCache:
    """Redis-backed cache for backtest results.

    Hashes config params with SHA256 to create cache keys.
    Stores results as JSON with 24h TTL.
    """

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        """Lazy-init Redis connection."""
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
        return self._redis

    async def get(self, config: dict) -> dict | None:
        """Look up a cached backtest result.

        Args:
            config: The backtest config dict.

        Returns:
            The cached result dict, or None if not found.
        """
        try:
            r = await self._get_redis()
            key = CACHE_KEY_PREFIX + _hash_config(config)
            data = await r.get(key)
            if data is not None:
                logger.debug("Cache HIT for key %s", key)
                return json.loads(data)
            logger.debug("Cache MISS for key %s", key)
            return None
        except Exception:
            logger.warning("Redis cache read failed, skipping cache", exc_info=True)
            return None

    async def set(self, config: dict, result: dict, ttl: int = CACHE_TTL_SECONDS) -> None:
        """Store a backtest result in cache.

        Args:
            config: The backtest config dict.
            result: The backtest result dict to cache.
            ttl: Time-to-live in seconds (default 24h).
        """
        try:
            r = await self._get_redis()
            key = CACHE_KEY_PREFIX + _hash_config(config)
            serialized = json.dumps(result, default=str)
            await r.set(key, serialized, ex=ttl)
            logger.debug("Cached result for key %s (TTL=%ds)", key, ttl)
        except Exception:
            logger.warning("Redis cache write failed, continuing without cache", exc_info=True)

    async def invalidate(self, config: dict) -> None:
        """Remove a specific cached result."""
        try:
            r = await self._get_redis()
            key = CACHE_KEY_PREFIX + _hash_config(config)
            await r.delete(key)
        except Exception:
            logger.warning("Redis cache invalidate failed", exc_info=True)

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
