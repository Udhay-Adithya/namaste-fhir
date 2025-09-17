import json
from typing import Any, List, Dict, Optional

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


def _get_access_token() -> str | None:
    # Prefer static token if provided
    if settings.who_api_token:
        return settings.who_api_token
    if not (
        settings.who_token_url and settings.who_client_id and settings.who_client_secret
    ):
        return None
    cache_key = "who:access_token"
    if token := _cache_get(cache_key):
        return token
    data = {
        "grant_type": "client_credentials",
        "client_id": settings.who_client_id,
        "client_secret": settings.who_client_secret,
        "scope": settings.who_scope,
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.post(settings.who_token_url, data=data)
        if resp.status_code == 200:
            tok = resp.json().get("access_token")
            if tok:
                _cache_set(cache_key, tok, ttl=3300)
                return tok
    return None


def fetch_icd11_concept(code: str) -> dict | None:
    cache_key = f"icd11:{code}"
    if cached := _cache_get(cache_key):
        return cached

    headers = {}
    token = _get_access_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{settings.who_api_base}/mms/{code}"
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            _cache_set(cache_key, data, ttl=6 * 3600)
            return data
    return None


def _headers() -> Dict[str, str]:
    h = {
        "API-Version": settings.who_api_version or "v2",
        "Accept-Language": settings.who_language or "en",
    }
    tok = _get_access_token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def search_icd11(
    term: str,
    linearization: str = "mms",
    size: int = 1,
    release_id: Optional[str] = None,
) -> List[Dict]:
    if not term:
        return []
    rel = release_id or settings.who_release_id
    cache_key = f"icd11:search:{rel}:{linearization}:{term}:{size}"
    if cached := _cache_get(cache_key):
        return cached

    url = f"{settings.who_api_base}/{linearization}/search"
    params = {
        "q": term,
        "useFlexisearch": "true",
        "flatResults": "true",
        "propertiesToBeSearched": "Title,IndexTerm,FullySpecifiedName",
        "returnType": "json",
        "limit": str(size),
    }
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, params=params, headers=_headers())
        if resp.status_code == 200:
            data = resp.json()
            # API may return {"destinationEntities": [...]} or {"results": [...]}
            items = (
                data.get("destinationEntities")
                or data.get("results")
                or data.get("words")
                or []
            )
            if isinstance(items, list):
                _cache_set(cache_key, items, ttl=3600)
                return items
    return []


def autocode_icd11(
    text: str,
    linearization: str = "mms",
    release_id: Optional[str] = None,
) -> Dict | None:
    if not text:
        return None
    rel = release_id or settings.who_release_id
    cache_key = f"icd11:autocode:{rel}:{linearization}:{text}"
    if cached := _cache_get(cache_key):
        return cached
    url = f"{settings.who_api_base}/{linearization}/autocode"
    params = {"searchText": text}
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, params=params, headers=_headers())
        if resp.status_code == 200:
            data = resp.json()
            _cache_set(cache_key, data, ttl=1800)
            return data
    return None


def codeinfo_icd11(
    code: str,
    linearization: str = "mms",
    release_id: Optional[str] = None,
) -> Dict | None:
    if not code:
        return None
    rel = release_id or settings.who_release_id
    cache_key = f"icd11:codeinfo:{rel}:{linearization}:{code}"
    if cached := _cache_get(cache_key):
        return cached
    url = f"{settings.who_api_base}/{linearization}/codeinfo/{code}"
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(url, headers=_headers())
        if resp.status_code == 200:
            data = resp.json()
            _cache_set(cache_key, data, ttl=6 * 3600)
            return data
    return None
