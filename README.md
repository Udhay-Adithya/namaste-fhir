# NAMASTE FHIR Terminology Microservice

FastAPI-based FHIR R4 terminology service integrating NAMASTE (AYUSH) with WHO ICD-11 TM2.

## Quick start

1. Install Poetry and dependencies

```bash
poetry install
```

2. Run locally

```bash
poetry run uvicorn app.main:app --reload
```

See `.env.example` for configuration.