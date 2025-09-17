from typing import Iterable, List

from elasticsearch import Elasticsearch, helpers

from ..config import get_settings


_client: Elasticsearch | None = None


def get_client() -> Elasticsearch:
    global _client
    if _client is None:
        settings = get_settings()
        _client = Elasticsearch(settings.elasticsearch_url)
    return _client


def ensure_index(index: str):
    es = get_client()
    if es.indices.exists(index=index):
        return
    es.indices.create(
        index=index,
        body={
            "settings": {
                "analysis": {
                    "analyzer": {
                        "autocomplete": {
                            "tokenizer": "autocomplete",
                            "filter": ["lowercase"],
                        }
                    },
                    "tokenizer": {
                        "autocomplete": {
                            "type": "edge_ngram",
                            "min_gram": 2,
                            "max_gram": 20,
                            "token_chars": ["letter", "digit", "whitespace"],
                        }
                    },
                }
            },
            "mappings": {
                "properties": {
                    "system": {"type": "keyword"},
                    "code": {"type": "keyword"},
                    "display": {
                        "type": "text",
                        "analyzer": "autocomplete",
                        "search_analyzer": "standard",
                    },
                    "synonyms": {"type": "text", "analyzer": "autocomplete"},
                }
            },
        },
    )


def bulk_index(index: str, docs: Iterable[dict]):
    es = get_client()
    ensure_index(index)
    actions = [{"_index": index, "_source": d} for d in docs]
    helpers.bulk(es, actions)


def autocomplete(index: str, term: str, size: int = 10) -> List[dict]:
    es = get_client()
    query = {
        "size": size,
        "query": {
            "multi_match": {
                "query": term,
                "type": "bool_prefix",
                "fields": [
                    "display^3",
                    "display._2gram",
                    "display._3gram",
                    "synonyms^2",
                ],
            }
        },
    }
    res = es.search(index=index, body=query)
    return [hit["_source"] for hit in res.get("hits", {}).get("hits", [])]
