import os
import uuid

import pytest
from redis.asyncio import Redis

from modest_chic_backend.core.rate_limit import RateLimiter, RateLimiterUnavailable

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_REDIS_URL"), reason="TEST_REDIS_URL is required for Redis tests"
)


@pytest.mark.asyncio
async def test_sliding_window_limits_normalized_identity_and_network() -> None:
    redis = Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
    limiter = RateLimiter(redis)
    key_prefix = f"auth-login-test:{uuid.uuid4()}"
    try:
        results = [
            await limiter.consume(
                "auth-login",
                "Staff@Example.COM",
                "203.0.113.7",
                limit=2,
                window_seconds=60,
                key_prefix=key_prefix,
            )
            for _ in range(3)
        ]
        assert results == [True, True, False]
        stored_keys = await redis.keys(f"{key_prefix}:*")
        assert len(stored_keys) == 2
        assert all("staff@example.com" not in stored_key for stored_key in stored_keys)
    finally:
        await redis.delete(*await redis.keys(f"{key_prefix}:*"))
        await redis.aclose()


@pytest.mark.asyncio
async def test_rate_limiter_fails_closed_when_redis_is_unavailable() -> None:
    redis = Redis.from_url("redis://localhost:1/0", socket_connect_timeout=0.05)
    limiter = RateLimiter(redis)

    with pytest.raises(RateLimiterUnavailable):
        await limiter.consume("auth-login", "staff@example.com", "203.0.113.7", 5, 60)

    await redis.aclose()


@pytest.mark.asyncio
async def test_sliding_window_also_limits_source_network_across_identities() -> None:
    redis = Redis.from_url(os.environ["TEST_REDIS_URL"], decode_responses=True)
    limiter = RateLimiter(redis)
    key_prefix = f"auth-login-network-test:{uuid.uuid4()}"
    try:
        first = await limiter.consume(
            "auth-login", "first@example.com", "203.0.113.8", 1, 60, key_prefix=key_prefix
        )
        second = await limiter.consume(
            "auth-login", "second@example.com", "203.0.113.8", 1, 60, key_prefix=key_prefix
        )
        assert first is True
        assert second is False
    finally:
        await redis.delete(*await redis.keys(f"{key_prefix}:*"))
        await redis.aclose()
