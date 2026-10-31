"""Redis-backed atomic sliding-window throttling for authentication operations."""

import hashlib
import secrets
import time
from collections.abc import Awaitable
from typing import Any, cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from modest_chic_backend.modules.auth.security import normalize_email

SLIDING_WINDOW_SCRIPT = """
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local member = ARGV[3]
local limit = tonumber(ARGV[4])
local limited = 0
for _, key in ipairs(KEYS) do
  redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
  redis.call('ZADD', key, now, member)
  local count = redis.call('ZCARD', key)
  redis.call('PEXPIRE', key, window)
  if count > limit then
    limited = 1
  end
end
return {1 - limited, 0}
"""


class RateLimiterUnavailable(RuntimeError):
    """Raised when auth cannot enforce its required request limit."""


class RateLimiter:
    """Apply distributed limits without putting raw identifiers in Redis keys."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def consume(
        self,
        operation: str,
        email: str,
        source_network: str,
        limit: int,
        window_seconds: int,
        *,
        key_prefix: str = "auth-rate-limit",
    ) -> bool:
        """Record an auth attempt and return whether it remains within the limit."""
        normalized_email = normalize_email(email)
        identity_digest = hashlib.sha256(normalized_email.encode()).hexdigest()
        network_digest = hashlib.sha256(source_network.encode()).hexdigest()
        keys = (
            f"{key_prefix}:{operation}:identity:{identity_digest}",
            f"{key_prefix}:{operation}:network:{network_digest}",
        )
        now = int(time.time() * 1000)
        try:
            result = await cast(
                Awaitable[Any],
                self._redis.eval(
                    SLIDING_WINDOW_SCRIPT,
                    len(keys),
                    *keys,
                    str(now),
                    str(window_seconds * 1000),
                    secrets.token_urlsafe(12),
                    str(limit),
                ),
            )
        except RedisError as error:
            raise RateLimiterUnavailable("authentication rate limiter is unavailable") from error
        return bool(int(result[0]))
