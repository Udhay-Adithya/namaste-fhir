# NAMASTE FHIR Terminology Service — Documentation

This document describes the architecture, configuration, and API of the NAMASTE FHIR terminology microservice. The service provides FHIR R4 endpoints for autocomplete, translation, lookup, and validation across NAMASTE (AYUSH) and WHO ICD‑11 (TM2, MMS).

## Overview

- Framework: FastAPI (Python 3.11)
- Storage: PostgreSQL (SQLAlchemy 2.x async)
- Cache: Redis
- Search: Elasticsearch (autocomplete)
- External: WHO ICD‑API v2 (ICD‑11) with OAuth/token
- Auth: OAuth2 password flow (mock ABHA) issuing JWTs

## Components

- `app/main.py`: FastAPI app wiring, middleware, auth endpoints
- `app/fhir/endpoints.py`: FHIR endpoints ($expand, $translate, $lookup, $validate-code, CodeSystem, Bundle)
- `app/services/icd11.py`: ICD‑11 client (search, autocode, codeinfo) with headers and release
- `app/services/search.py`: ES index creation and autocomplete
- `app/services/ingest.py`: AYUSH XLS/XLSX ingestion helpers
- `scripts/ingest_local_data.py`: One-shot script to ingest and index local data
- `app/db/models.py`, `app/db/session.py`: Models and async session
- `app/config.py`: Settings via environment (.env)

## Configuration

Copy `.env.example` to `.env` and set the following.

- App
  - `APP_HOST`, `APP_PORT`, `LOG_LEVEL`, `ALLOWED_ORIGINS`
- Auth
  - `JWT_SECRET`, `JWT_ALG`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- Database
  - `DATABASE_URL` (asyncpg DSN)
- Elasticsearch
  - `ELASTICSEARCH_URL`
- Redis
  - `REDIS_URL`
- WHO ICD‑API
  - `WHO_API_BASE` (e.g., `https://id.who.int/icd/release/11/2025-01`)
  - `WHO_API_VERSION` (e.g., `v2`)
  - `WHO_LANGUAGE` (e.g., `en`)
  - `WHO_RELEASE_ID` (e.g., `2025-01`)
  - Authentication: Either provide `WHO_API_TOKEN` or set `WHO_TOKEN_URL`, `WHO_CLIENT_ID`, `WHO_CLIENT_SECRET`, `WHO_SCOPE` for client credentials.

## Running

- Install: `poetry install`
- Start deps (optional): `docker compose -f docker/docker-compose.yml up -d`
- Ingest data: `poetry run python scripts/ingest_local_data.py`
- Run API: `poetry run uvicorn app.main:app --reload`
- Get token: `curl -s -X POST http://localhost:8000/auth/token -d 'username=demo&password=demo' -H 'Content-Type: application/x-www-form-urlencoded' | jq -r .access_token`

Export `TOKEN` before calling APIs: `export TOKEN=...`

## Data Ingestion

- Sources: `data/` folder (AYUSH spreadsheets and legacy WHO ICD‑10 listing)
- The service ingests NAMASTE CodeSystems from provided XLS/XLSX files and indexes names/synonyms into Elasticsearch for autocomplete.
- ICD‑10 file is not used for crosswalks; ICD‑11 is retrieved dynamically via WHO ICD‑API.

## FHIR API

Base path: `/fhir`. All endpoints require `Authorization: Bearer <token>`.

### ValueSet $expand (autocomplete)

- `GET /fhir/ValueSet/$expand?url=<vs-url>&filter=<text>&count=<n>`
- Behavior: Queries Elasticsearch with edge-ngram analyzer; falls back to DB LIKE search.
- Response (example):

```json
{
  "resourceType": "ValueSet",
  "url": "https://namaste.ayush.gov.in/fhir/ValueSet/ayush",
  "status": "active",
  "expansion": {
    "identifier": "<request-id>",
    "timestamp": "2025-09-18T12:34:56Z",
    "total": 2,
    "contains": [
      {"system": "https://namaste.ayush.gov.in/fhir/CodeSystem/ayurveda", "code": "SR11(AAA-1)", "display": "Accumulation of Vata pattern (TM2)"},
      {"system": "https://namaste.ayush.gov.in/fhir/CodeSystem/siddha", "code": "...", "display": "..."}
    ]
  }
}
```

### ConceptMap $translate

- `POST /fhir/ConceptMap/$translate`
- Body (Parameters):

```json
{
  "resourceType": "Parameters",
  "parameter": [
    {"name": "url", "valueUri": "https://namaste.ayush.gov.in/fhir/ConceptMap/namaste-to-icd11"},
    {"name": "system", "valueUri": "https://namaste.ayush.gov.in/fhir/CodeSystem/ayurveda"},
    {"name": "code", "valueCode": "SR11(AAA-1)"}
  ]
}
```

- Behavior: Returns curated mapping if present. Otherwise, fetches the source display and uses WHO ICD‑API autocode (tries TM2, then MMS) to return best-effort match with equivalence `relatedto` and optional score.
- Response (example):

```json
{
  "resourceType": "Parameters",
  "parameter": [
    {"name": "result", "valueBoolean": true},
    {
      "name": "match",
      "part": [
        {"name": "equivalence", "valueCode": "relatedto"},
        {"name": "concept", "valueCoding": {"system": "http://id.who.int/icd/release/11/mms", "code": "1F40.Z", "display": "Disorders of multiple glycosylation or other pathways"}},
        {"name": "score", "valueDecimal": 0.72}
      ]
    },
    {"name": "message", "valueString": "Returned ICD-11 best-effort match via WHO ICD-API autocode."}
  ]
}
```

### CodeSystem $lookup

- `GET /fhir/CodeSystem/$lookup?system=<system-uri>&code=<code>`
- Behavior:
  - ICD‑11 systems: Uses `codeinfo` for exact match; if title is missing, falls back to a 1-result search to derive display.
  - Local NAMASTE systems: Looks up concept in stored CodeSystem content.
- Response (example):

```json
{
  "resourceType": "Parameters",
  "parameter": [
    {"name": "name", "valueString": "http://id.who.int/icd/release/11/mms"},
    {"name": "version", "valueString": "mms"},
    {"name": "display", "valueString": "Disorders of multiple glycosylation or other pathways"}
  ]
}
```

- Errors: `404 Code not found in ICD-11` if codeinfo fails and no exact code.

### CodeSystem $validate-code

- `GET /fhir/CodeSystem/$validate-code?system=<system-uri>&code=<code>`
- Behavior:
  - ICD‑11: Exact validation via `codeinfo`.
  - Local: Validation against stored CodeSystem.
- Response (example):

```json
{
  "resourceType": "Parameters",
  "parameter": [
    {"name": "result", "valueBoolean": true},
    {"name": "system", "valueUri": "http://id.who.int/icd/release/11/mms"},
    {"name": "code", "valueCode": "1F40.Z"},
    {"name": "display", "valueString": "Disorders of multiple glycosylation or other pathways"}
  ]
}
```

### CodeSystem read

- `GET /fhir/CodeSystem/{id}` — returns the stored CodeSystem JSON.

### Bundle (POST)

- `POST /fhir/Bundle` — validates using FHIR model and echoes basic summary.
- Response example:

```json
{"resourceType": "Bundle", "type": "transaction", "total": 2}
```

## Authentication

- Obtain a JWT via `/auth/token` with password grant. The token must be sent as `Authorization: Bearer <token>` to access `/fhir/*` endpoints.

## Notes & Limitations

- ICD‑11 `$lookup` is strict (exact codes only). For suggestions, use `$translate` or implement a search endpoint.
- Some AYUSH spreadsheets may contain non-standard XLSX; ingestion handles `.xls` via `xlrd` and `.xlsx` via `pandas/openpyxl`.
- Rate limiting and audit middleware are basic stubs; adapt per deployment.

## Troubleshooting

- Startup issues: verify Postgres, Redis, and Elasticsearch are reachable per `.env`.
- WHO ICD‑API: ensure `WHO_API_TOKEN` or client credentials are valid and that `WHO_API_VERSION`, `WHO_RELEASE_ID`, and `WHO_LANGUAGE` are correct.
- Autocomplete empty: confirm `scripts/ingest_local_data.py` has run and ES index exists.

## License

Proprietary — internal use only unless otherwise noted.
