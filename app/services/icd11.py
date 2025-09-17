import json
from typing import Any

import httpx
import redis

from ..config import get_settings


settings = get_settings()
_redis = redis.from_url(settings.redis_url) if settings.redis_url else None


def _cache_get(key: str) -> Any | None:
    if not _redis:
        return None
    raw = _redis.get(key)
    return json.loads(raw) if raw else None


def _cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    if not _redis:
        return
    _redis.setex(key, ttl, json.dumps(value))


def fetch_icd11_concept(code: str) -> dict | None:
    cache_key = f"icd11:{code}"
    if cached := _cache_get(cache_key):
        return cached

    headers = {}
    if settings.who_api_token:
        headers["Authorization"] = f"Bearer {settings.who_api_token}"
    url = f"{settings.who_api_base}/mms/{code}"
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            _cache_set(cache_key, data, ttl=6 * 3600)
            return data
    return None
