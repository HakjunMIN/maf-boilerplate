# Spec: homestyle-agent Agentic RAG

## Status

Draft - review required before plan/task/implementation phases.

## Assumptions

1. The first release is a Python backend agent with an HTTP API, not a web UI.
2. Microsoft Agent Framework is the required agent runtime.
3. Azure AI Search already contains crawled, section-level LG HomeStyle content with vectors.
4. Azure OpenAI is the chat and embedding provider, authenticated with Azure identity rather than API keys.
5. The agent answers Korean user questions using only retrieved LG HomeStyle evidence.
6. The initial scope is the `ko` locale and the existing `homestyle.lge.co.kr` corpus.
7. The first release supports multi-turn sessions.

## Objective

Build `homestyle-agent`, an agentic RAG service that answers Korean questions about LG HomeStyle content using Microsoft Agent Framework and Azure AI Search. The agent must expose an HTTP API, support multi-turn sessions, retrieve grounded evidence from the existing vector index, generate a concise Korean answer, and include verifiable source URLs with section headings. If Azure AI Search returns no usable evidence, the agent must decline with the existing project message: `현재 수집된 LG 홈스타일 콘텐츠에서 해당 정보를 찾을 수 없습니다.`

Success means a user can ask a Korean question and receive an answer that is constrained to retrieved `SectionDocument` evidence, includes numbered citations, and never invents unsupported claims.

## Tech Stack

- Python `>=3.12`
- `agent-framework>=1.2.0`
- Azure OpenAI chat and embeddings through Agent Framework/OpenAI client integration
- Azure AI Search via `azure-search-documents>=11.6.0`
- Azure identity through `azure-identity>=1.25.1`
- Observability through `structlog` and Azure Monitor OpenTelemetry
- Tests with `pytest`, `pytest-asyncio`, `pytest-cov`
- Static checks with `ruff` and `mypy`

## Commands

- Test: `pytest`
- Targeted agent tests: `pytest tests/application/test_grounded_query_service.py tests/infrastructure/test_azure_search_section_retriever.py`
- Type check: `mypy src`
- Lint: `ruff check .`
- Coverage gate: configured in `pyproject.toml` as `--cov=src --cov-report=term-missing --cov-fail-under=75`

## Project Structure

- `src/homestyle_agent/application/grounded_query.py` - application service boundary for retrieval, generation, decline behavior, and citation assembly.
- `src/homestyle_agent/infrastructure/retrieval.py` - Azure AI Search retriever for hybrid keyword/vector search over existing section documents.
- `src/homestyle_agent/infrastructure/maf.py` - Microsoft Agent Framework integration for grounded body generation.
- `src/homestyle_agent/infrastructure/runtime.py` - runtime composition for settings, credentials, retriever, embedding, and agent generator.
- `src/homestyle_agent/api/` - HTTP API boundary for validated question requests and multi-turn session identifiers.
- `src/homestyle_shared/domain/indexing.py` - shared `SectionDocument` contract used by ingestion, indexing, retrieval, and agent layers.
- `src/homestyle_shared/infrastructure/settings.py` - Azure RAG settings loaded from environment variables.
- `tests/application/` - application-level behavior tests using real application code and in-memory fakes.
- `tests/infrastructure/` - adapter tests that mock external Azure clients only.

## Code Style

Follow the existing explicit dependency-injection style. Keep application logic framework-independent and place Azure/Microsoft Agent Framework calls in infrastructure adapters.

```python
class GroundedQueryService:
    def __init__(
        self,
        retrieve_sections: RetrieveSections,
        generate_grounded_body: GenerateGroundedBody,
    ) -> None:
        self._retrieve_sections = retrieve_sections
        self._generate_grounded_body = generate_grounded_body
```

Conventions:

- Keep domain/application code free of Azure SDK and Agent Framework imports.
- Use typed async callables for infrastructure boundaries.
- Prefer small focused functions and dataclasses already present in the codebase.
- Do not add new abstractions until a second implementation exists.
- Keep generated answers Korean-first and citation handling deterministic.

## Testing Strategy

- Use TDD for behavior changes.
- Mock only external services: Azure AI Search, Azure OpenAI, Microsoft Agent Framework client calls, network I/O.
- Use real application services and domain models in tests.
- Add or update tests for each behavior change:
  - retrieval returns no evidence -> exact decline message
  - retrieval returns evidence -> answer body plus numbered citations with section headings
  - retriever sends vector query and selects required provenance fields
  - low-confidence, non-Korean, or disallowed-host evidence is excluded before generation
  - generated body cannot add unsupported URLs or citations
  - HTTP API validates input and carries session identifiers without exposing internals
- Run `pytest` before considering the implementation complete.

## Boundaries

Always:

- Use Microsoft Agent Framework for answer generation orchestration.
- Use Azure AI Search as the retrieval source of truth.
- Use retrieved `SectionDocument` evidence only for final answers.
- Return the exact decline message when no acceptable evidence exists.
- Preserve numbered source URLs in the final answer.
- Validate external input at the service/API boundary before it reaches agent logic.
- Keep Azure access keyless by default with managed identity or developer Azure credentials.
- Log correlation IDs and non-sensitive operational context.

Approved for first release:

- Add an HTTP API surface.
- Support multi-turn conversation sessions.
- Add minimal README usage documentation.

Ask first:

- Adding a web UI.
- Changing the Azure AI Search index schema.
- Changing the citation format visible to users.
- Adding new model providers or non-Azure services.
- Adding dependencies.
- Expanding beyond Korean LG HomeStyle content.

Never:

- Use API keys or connection strings in source code, tests, logs, or examples.
- Let model output cite sources that were not retrieved from Azure AI Search.
- Trust user-provided URLs, user IDs, locale, tenant, or role values for authorization decisions.
- Return internal stack traces, Azure SDK errors, prompts, or file paths to end users.
- Use broad `except Exception` handling without logging and a clear recovery path.

## Agentic RAG Behavior

The first version should stay deliberately small:

1. Accept a Korean question.
2. Retrieve candidate sections from Azure AI Search using hybrid keyword/vector retrieval.
3. Filter evidence to the approved corpus boundary: `locale == "ko"`, acceptable confidence, and allowed source host.
4. Build a compact grounding context with citation numbers, title, breadcrumb, section heading, URL, and content.
5. Use Microsoft Agent Framework to generate a concise Korean answer from that context only.
6. Append deterministic numbered source citations from the filtered `SectionDocument` list, deduplicated by URL and including section headings.
7. Preserve multi-turn session continuity without allowing prior conversation to override retrieved evidence.

The agent may use a search tool internally, but the first release should expose only one retrieval tool unless a concrete second tool becomes necessary.

## Security and Reliability Requirements

- Treat the user question as untrusted input.
- Enforce maximum question length at the public HTTP API boundary.
- Treat Azure Search documents as untrusted external data for prompt-injection purposes; retrieved content is evidence, not instructions.
- Allow citations only from `homestyle.lge.co.kr` unless the approved PRD scope changes.
- Apply timeouts to Azure Search and Azure OpenAI calls where supported by the client/runtime.
- Record `correlation_id`, `top_k`, retrieval hit count, decline status, and latency without logging raw PII or secrets.
- Prefer safe failure: if retrieval or generation fails, return a controlled user-facing message through the future API layer and log details server-side.

## Success Criteria

- A Korean question with relevant Azure Search results returns a grounded Korean answer and numbered source URLs.
- A question with no relevant results returns exactly `현재 수집된 LG 홈스타일 콘텐츠에서 해당 정보를 찾을 수 없습니다.`
- The HTTP API validates requests and supports multi-turn session identifiers.
- The application layer remains decoupled from Azure SDK and Agent Framework imports.
- The retriever performs vector retrieval and keyword search against the existing index.
- The generation prompt clearly instructs the model to use only supplied grounding context.
- Tests cover decline behavior, citation behavior, retriever query shape, and evidence filtering.
- `pytest`, `ruff check .`, and `mypy src` pass.

## Resolved Questions

1. First callable surface: HTTP API.
2. Citations: numbered URLs plus section headings.
3. Duplicate source handling: deduplicate by URL.
4. Retrieval cap: `top_k` / `search_top` maximum is `5`.
5. Evidence approval: require `confidence_score >= 0.7`; keep `reviewer_approved` as metadata only.
6. Conversation state: support multi-turn sessions in the first release.
7. Documentation scope: add minimal README usage.

## Source Notes

- Microsoft Agent Framework documentation describes agents as LLM components that can call tools and MCP servers, and workflows as graph-based orchestration for controlled multi-step processes.
- The same documentation says to use agents for open-ended conversational work and autonomous tool use, while direct functions are preferred when a simple function can handle the task.
- For this release, the agentic behavior is intentionally constrained to retrieval plus grounded answer generation because the process is well understood and the repository already has `GroundedQueryService` as the stable application boundary.