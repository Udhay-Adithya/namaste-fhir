# NAMASTE FHIR Terminology Microservice

FastAPI-based FHIR R4 terminology microservice integrating NAMASTE (AYUSH) codes with WHO ICD‑11 (TM2 and MMS). Provides autocomplete ($expand), translation ($translate), exact lookup ($lookup), code validation ($validate-code), and CodeSystem read, with OAuth2 (mock ABHA), PostgreSQL, Redis caching, and Elasticsearch.

## Features

- FHIR R4 endpoints under `/fhir`:
	- `ValueSet/$expand`: autocomplete from Elasticsearch and DB fallback
	- `ConceptMap/$translate`: NAMASTE → ICD‑11 best-effort via WHO ICD‑API autocode, plus curated mappings if present
	- `CodeSystem/$lookup`: exact code lookup — ICD‑11 via `codeinfo`, local systems via DB
	- `CodeSystem/$validate-code`: verify existence of a code in a system
	- `CodeSystem/{id}`: retrieve stored CodeSystem JSON
	- `Bundle` (POST): validate and echo summary
- WHO ICD‑API v2 headers and release-aware client with Redis caching
- Ingestion pipeline for AYUSH XLS/XLSX into DB and Elasticsearch
- OAuth2 password flow with mock ABHA, JWTs
- Middleware: request-id, simple rate-limit/audit stubs, CORS

## Architecture

- FastAPI app in `app/main.py`; FHIR routes in `app/fhir/endpoints.py`
- Config in `app/config.py` (loads from environment)
- DB models and async session in `app/db` (SQLAlchemy + asyncpg)
- WHO ICD‑API client in `app/services/icd11.py`
- Search/ES utilities in `app/services/search.py`
- Ingestion in `app/services/ingest.py` and `scripts/ingest_local_data.py`

## Prerequisites

- Python 3.11+
- Poetry
- Postgres, Redis, Elasticsearch (or use Docker Compose)

## Setup

1) Install dependencies

```bash
poetry install
```

2) Copy and edit environment

```bash
cp .env.example .env
```

Important variables:

- `DATABASE_URL` e.g. `postgresql+asyncpg://postgres:postgres@localhost:5432/namaste_fhir`
- `ELASTICSEARCH_URL` e.g. `http://localhost:9200`
- `REDIS_URL` e.g. `redis://localhost:6379/0`
- WHO ICD‑API
	- `WHO_API_BASE` e.g. `https://id.who.int/icd/release/11/2025-01`
	- `WHO_API_VERSION` e.g. `v2`
	- `WHO_LANGUAGE` e.g. `en`
	- `WHO_RELEASE_ID` e.g. `2025-01`
	- Auth: either set `WHO_API_TOKEN` directly or configure `WHO_TOKEN_URL`, `WHO_CLIENT_ID`, `WHO_CLIENT_SECRET`, `WHO_SCOPE`

3) Start dependencies (optional via Docker Compose)

```bash
docker compose -f docker/docker-compose.yml up -d
```

4) Ingest local NAMASTE data and create ES index

```bash
poetry run python scripts/ingest_local_data.py
```

5) Run the API

```bash
poetry run uvicorn app.main:app --reload
```

6) Get a token (mock ABHA)

```bash
curl -s -X POST http://localhost:8000/auth/token \
	-H 'Content-Type: application/x-www-form-urlencoded' \
	-d 'username=demo&password=demo' | jq -r .access_token
```

Export `TOKEN` and use with requests:

```bash
export TOKEN=... # paste the token
```

## Quick API Examples

- ValueSet $expand (autocomplete)

```bash
curl -s --get 'http://localhost:8000/fhir/ValueSet/$expand' \
	-H "Authorization: Bearer $TOKEN" \
	--data-urlencode 'url=https://namaste.ayush.gov.in/fhir/ValueSet/ayush' \
	--data-urlencode 'filter=Vata' | jq .
```

- ConceptMap $translate (best-effort NAMASTE → ICD‑11)

```bash
curl -s -X POST 'http://localhost:8000/fhir/ConceptMap/$translate' \
	-H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
	-d '{
		"resourceType": "Parameters",
		"parameter": [
			{"name": "url", "valueUri": "https://namaste.ayush.gov.in/fhir/ConceptMap/namaste-to-icd11"},
			{"name": "system", "valueUri": "https://namaste.ayush.gov.in/fhir/CodeSystem/ayurveda"},
			{"name": "code", "valueCode": "SR11(AAA-1)"}
		]
	}' | jq .
```

- CodeSystem $lookup (exact)

```bash
# ICD-11 MMS
curl -s 'http://localhost:8000/fhir/CodeSystem/$lookup?system=http://id.who.int/icd/release/11/mms&code=1F40.Z' \
	-H "Authorization: Bearer $TOKEN" | jq .

# NAMASTE Ayurveda
curl -s --get 'http://localhost:8000/fhir/CodeSystem/$lookup' \
	-H "Authorization: Bearer $TOKEN" \
	--data-urlencode 'system=https://namaste.ayush.gov.in/fhir/CodeSystem/ayurveda' \
	--data-urlencode 'code=SR11(AAA-1)' | jq .
```

- CodeSystem $validate-code

```bash
curl -s 'http://localhost:8000/fhir/CodeSystem/$validate-code?system=http://id.who.int/icd/release/11/mms&code=1F40.Z' \
	-H "Authorization: Bearer $TOKEN" | jq .
```

More detailed docs and sample responses are in `docs/DOCS.md`.

## License

Proprietary — internal use only unless otherwise noted.