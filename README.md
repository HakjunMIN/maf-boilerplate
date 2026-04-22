# MAF Analysis Backend

Backend-only data analysis workflow built with Microsoft Agent Framework, Python, uv, and an isolated local Docker sandbox.

## Features

- FastAPI HTTP API
- One user-facing reasoning agent that orchestrates two subordinate agents
- Code interpreter agent backed by an isolated local Docker sandbox
- Web search agent backed by DuckDuckGo search
- In-memory job state for local development
- Provider support for Azure OpenAI, OpenAI, or Foundry Local
- Deny-by-default bearer token authentication

## Quick Start

```bash
uv sync --locked
cp .env.example .env
docker build -t maf-analysis-sandbox:latest docker/analysis-sandbox
uv run uvicorn maf_backend.main:app --host 127.0.0.1 --port 8000
```

## Environment

- `API_BEARER_TOKEN`: required bearer token for all `/api/v1/*` endpoints except `/api/v1/healthz`
- `MODEL_PROVIDER`: `azure_openai`, `openai`, or `foundry_local`
- `AZURE_OPENAI_ENDPOINT`, `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_OPENAI_MODEL`, `AZURE_OPENAI_CHAT_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`
- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `FOUNDRY_LOCAL_MODEL`
- `SANDBOX_IMAGE`, `SANDBOX_TIMEOUT_SECONDS`, `SANDBOX_MEMORY`, `SANDBOX_CPUS`, `SANDBOX_USER`, `SANDBOX_OUTPUT_LIMIT_BYTES`, `SANDBOX_DATA_ROOT`

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

## Manual Test Flow

Run the server in one terminal:

```bash
cd /Users/andy/works/ai/maf-boilerplate
uv run uvicorn maf_backend.main:app --host 127.0.0.1 --port 8000
```

Use a second terminal for the checks below.

### 1. Health Check

```bash
curl -sS http://127.0.0.1:8000/api/v1/healthz
```

Expected response:

```json
{"status":"ok","app":"MAF Analysis Backend"}
```

### 2. Auth Check

Requesting a protected endpoint without a bearer token should return `401 Unauthorized`.

```bash
curl -i http://127.0.0.1:8000/api/v1/jobs/test-job
```

### 3. Load Bearer Token From `.env`

```bash
export API_BEARER_TOKEN="$(grep '^API_BEARER_TOKEN=' .env | cut -d= -f2-)"
```

### 4. Create a Real Analysis Job

```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/jobs \
	-H "Authorization: Bearer $API_BEARER_TOKEN" \
	-H "Content-Type: application/json" \
	-d '{
		"query": "Summarize room extraction CSV columns and row count",
		"input_files": ["vlm_outputs/single_rooms_oneshot_20260421_113022.csv"]
	}'
```

Example response:

```json
{
	"job_id": "3733e3bdb35e4f66bb1ff073ac203c78",
	"status": "pending",
	"query": "Summarize room extraction CSV columns and row count",
	"input_files": ["vlm_outputs/single_rooms_oneshot_20260421_113022.csv"]
}
```

### 5. Poll Job Status

Replace `<JOB_ID>` with the `job_id` from the create response.

```bash
curl -sS http://127.0.0.1:8000/api/v1/jobs/<JOB_ID> \
	-H "Authorization: Bearer $API_BEARER_TOKEN"
```

You may see `pending` or `running` first. A successful run ends with `completed`.

To poll every 2 seconds:

```bash
JOB_ID="<JOB_ID>"
while true; do
	curl -sS "http://127.0.0.1:8000/api/v1/jobs/$JOB_ID" \
		-H "Authorization: Bearer $API_BEARER_TOKEN"
	echo
	sleep 2
done
```

### 6. Successful Result Shape

A successful response includes:

- `summary`
- `generated_code`
- `sandbox_result.stdout`
- `sandbox_result.exit_code`

Example successful sandbox output for the sample CSV:

```text
File: /inputs/vlm_outputs/single_rooms_oneshot_20260421_113022.csv
Row count: 13
Columns: id, label, confidence, x, y, width, height, notes
```

## Azure Authentication Notes

When using `MODEL_PROVIDER=azure_openai`, local development typically relies on `DefaultAzureCredential`. Make sure your local Azure login is valid before testing:

```bash
az account show
```

If needed:

```bash
az login
```

## Troubleshooting

- If `GET /api/v1/healthz` fails, confirm the server is running on `127.0.0.1:8000`.
- If protected endpoints return `401`, verify `API_BEARER_TOKEN` matches the value in `.env`.
- If jobs fail, inspect the server logs and the job response fields `error_message` and `sandbox_result`.
- If sandbox execution fails immediately, confirm the Docker image exists:

```bash
docker images maf-analysis-sandbox
```

## Notes

This version keeps state in memory and executes one process-local workflow per job. The only user-facing agent is the reasoning orchestrator; it may internally call the code interpreter agent and the DuckDuckGo-backed web search agent. Generated analysis code never runs in the API process; it runs inside a separate Docker container with network disabled and constrained CPU and memory limits.
