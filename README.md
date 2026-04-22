# MAF Analysis Backend

Backend-only data analysis workflow built with Microsoft Agent Framework, Python, uv, and an isolated local Docker sandbox.

## Features

- FastAPI HTTP API
- Microsoft Agent Framework analysis orchestration
- Isolated Python execution in a separate local Docker container
- In-memory job state for local development
- Provider support for Azure OpenAI, OpenAI, or Foundry Local
- Deny-by-default bearer token authentication

## Quick Start

```bash
uv sync
cp .env.example .env
docker build -t maf-analysis-sandbox:latest docker/analysis-sandbox
uv run uvicorn maf_backend.main:app --reload
```

## Environment

- `API_BEARER_TOKEN`: required bearer token for all `/api/v1/*` endpoints except `/api/v1/healthz`
- `MODEL_PROVIDER`: `azure_openai`, `openai`, or `foundry_local`
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_MODEL`
- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `FOUNDRY_LOCAL_MODEL`
- `SANDBOX_IMAGE`, `SANDBOX_TIMEOUT_SECONDS`, `SANDBOX_MEMORY`, `SANDBOX_CPUS`

## API

- `GET /api/v1/healthz`
- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs \
	-H "Authorization: Bearer change-me" \
	-H "Content-Type: application/json" \
	-d '{
		"query": "Summarize room extraction results by file",
		"input_files": ["vlm_outputs/single_rooms_oneshot_20260421_113022.csv"]
	}'
```

## Notes

This first version keeps state in memory and executes one process-local workflow per job. The generated analysis code never runs in the API process; it runs inside a separate Docker container with network disabled and constrained CPU and memory limits.
