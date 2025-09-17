from typing import List

from elasticsearch import Elasticsearch

from ..config import get_settings


_client: Elasticsearch | None = None


def get_client() -> Elasticsearch:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Elasticsearch(settings.elasticsearch_url)
    return _client


def autocomplete(index: str, term: str, size: int = 10) -> List[dict]:
    es = get_client()
    query = {
        "size": size,
        "query": {
            "multi_match": {
                "query": term,
                "type": "bool_prefix",
                "fields": [
                    "display.suggest",
                    "display.suggest._2gram",
                    "display.suggest._3gram",
                    "synonyms^2",
                ],
            }
        },
    }
    res = es.search(index=index, body=query)
    return [hit["_source"] for hit in res.get("hits", {}).get("hits", [])]
