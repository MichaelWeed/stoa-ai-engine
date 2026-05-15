FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY stoa/ ./stoa/
COPY .env.example .env.example

EXPOSE 8000
CMD ["uvicorn", "stoa.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
