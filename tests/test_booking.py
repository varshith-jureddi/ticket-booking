import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import redis

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture()
def redis_client():
    client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )
    try:
        client.ping()
    except redis.RedisError:
        pytest.skip("Redis is not running")
    client.flushdb()
    yield client
    client.flushdb()


def test_exactly_one_concurrent_hold_wins(redis_client):
    key = "seat:screen-1:A1"
    session_keys = []
    lock = threading.Lock()

    def attempt(user_number):
        session_id = f"test-{user_number}"
        booking = {
            "id": session_id,
            "movie_id": "screen-1",
            "seat_id": "A1",
            "user_id": session_id,
            "status": "held",
        }
        ok = redis_client.set(
            key,
            json.dumps(booking),
            nx=True,
            ex=120,
        )
        if ok:
            with lock:
                session_keys.append(session_id)
        return bool(ok)

    with ThreadPoolExecutor(max_workers=100) as executor:
        results = list(executor.map(attempt, range(1000)))

    assert sum(results) == 1
    assert len(session_keys) == 1
