FROM python:3.11-slim

ENV POETRY_VERSION=1.8.3 POETRY_VIRTUALENVS_CREATE=false PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

WORKDIR /app
COPY pyproject.toml /app/
RUN poetry install --no-interaction --no-ansi --only main

COPY app /app/app

EXPOSE 8000
CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
