# Implementation Plan: homestyle-agent Agentic RAG

## Status

Draft - review required before implementation.

## Overview

Build the existing `homestyle_agent` package into a constrained Microsoft Agent Framework based agentic RAG service over the already-indexed Azure AI Search corpus. The work should preserve the current application boundary (`GroundedQueryService`), strengthen retrieval and evidence filtering, keep answer generation grounded, and verify the behavior with small tests that mock only external Azure and model clients.

## Resolved Planning Decisions

- The first callable surface is an HTTP API.
- Answers include numbered source URLs plus section headings.
- Duplicate source URLs are deduplicated in citations.
- `search_top` maximum is `5`.
- Low-confidence filtering uses `confidence_score >= 0.7` and `locale == "ko"`; `reviewer_approved` remains metadata.
- The first release supports multi-turn sessions.
- Add minimal README usage documentation.

## Dependency Graph

```text
SectionDocument contract
    |
    +-- Evidence acceptance rules
    |       |
    |       +-- GroundedQueryService filtering and citation behavior
    |               |
    |               +-- AzureRagRuntime answer path
    |                       |
    |                       +-- HTTP API request/response boundary
    |                               |
    |                               +-- Multi-turn session handling
    |
    +-- AzureSearchSectionRetriever query shape
            |
            +-- AzureRagRuntime composition

MAF grounded generator prompt
    |
    +-- Grounded answer body generation
            |
            +-- Application-level answer tests

Observability and settings
    |
    +-- Runtime logging and close behavior
```

## Architecture Decisions

- Keep `GroundedQueryService` as the stable application contract. This keeps domain/application code independent from Azure SDK and Microsoft Agent Framework imports.
- Put evidence filtering in the application layer before generation. The retriever can use Azure filters for efficiency, but the application service still enforces the trust boundary.
- Keep one retrieval path for the first release. A separate MAF tool wrapper can be added only if implementation proves the current direct retrieval/generation composition is insufficient.
- Use deterministic citation assembly outside the model. The model writes only the answer body; URLs are appended by application code.
- Expose the first release through an HTTP API with validated request/response models and multi-turn session identifiers.
- Keep infrastructure adapter tests focused on query shape and client normalization, with external clients faked.

## Task List

### Phase 1: Foundation

## Task 1: Define Evidence Acceptance Rules

**Description:** Add a small application-level evidence filtering path that accepts only sections from the approved corpus before answer generation.

**Acceptance criteria:**
- [ ] Sections with `locale != "ko"` are excluded.
- [ ] Sections with `confidence_score < 0.7` are excluded.
- [ ] Sections whose URL host is not `homestyle.lge.co.kr` are excluded.
- [ ] If every section is excluded, `GroundedQueryService.answer()` returns the existing decline message and does not call the generator.

**Verification:**
- [ ] `pytest tests/application/test_grounded_query_service.py`

**Dependencies:** None

**Files likely touched:**
- `src/homestyle_agent/application/grounded_query.py`
- `tests/application/test_grounded_query_service.py`

**Estimated scope:** Small: 2 files

## Task 2: Constrain Retriever Query Shape

**Description:** Ensure Azure Search retrieval requests include the corpus constraints that can be pushed down to Azure Search without changing the application-layer trust boundary.

**Acceptance criteria:**
- [ ] Retriever query requests `locale eq 'ko'` filtering when supported by the existing index fields.
- [ ] Retriever keeps hybrid search: keyword `search_text` plus `VectorizedQuery` over `content_vector`.
- [ ] Retriever selects all fields required to rebuild `SectionDocument` provenance, including `section_heading` if the index exposes it.
- [ ] `top` is bounded to a maximum of `5`.

**Verification:**
- [ ] `pytest tests/infrastructure/test_azure_search_section_retriever.py`

**Dependencies:** Task 1 can run in parallel, but complete before final checkpoint.

**Files likely touched:**
- `src/homestyle_agent/infrastructure/retrieval.py`
- `tests/infrastructure/test_azure_search_section_retriever.py`

**Estimated scope:** Small: 2 files

### Checkpoint: Foundation

- [ ] `pytest tests/application/test_grounded_query_service.py tests/infrastructure/test_azure_search_section_retriever.py`
- [ ] Application layer still has no Azure SDK or Microsoft Agent Framework imports.
- [ ] Decline behavior remains exact.

### Phase 2: Core RAG Behavior

## Task 3: Tighten Grounding Context Construction

**Description:** Make the MAF prompt context compact and citation-numbered so the generated answer body can only refer to supplied evidence.

**Acceptance criteria:**
- [ ] Prompt includes each section's citation number, title, breadcrumb, section heading, URL, and content.
- [ ] Prompt clearly states retrieved content is evidence, not instructions.
- [ ] Prompt instructs the model not to create citations, footnotes, or URLs.
- [ ] Section content is trimmed to a bounded length per section to avoid flooding context.

**Verification:**
- [ ] Add or update infrastructure tests for `MafGroundedBodyGenerator._build_prompt()` without calling a real model.
- [ ] `pytest tests/infrastructure/test_maf_grounded_body_generator.py` if a new test file is added, or the existing relevant test file if reused.

**Dependencies:** Task 1

**Files likely touched:**
- `src/homestyle_agent/infrastructure/maf.py`
- `tests/infrastructure/test_maf_grounded_body_generator.py`

**Estimated scope:** Small: 2 files

## Task 4: Guard Final Answer Citations

**Description:** Keep final source citations deterministic and prevent model-generated unsupported URLs from appearing in the final response.

**Acceptance criteria:**
- [ ] Final citations are built only from filtered `SectionDocument.page_url` and section heading values.
- [ ] Duplicate source URLs are not repeated.
- [ ] The answer body is stripped of unsupported visible URLs if the model returns them.
- [ ] Citation numbering remains stable after filtering and deduplication.

**Verification:**
- [ ] `pytest tests/application/test_grounded_query_service.py`

**Dependencies:** Task 1

**Files likely touched:**
- `src/homestyle_agent/application/grounded_query.py`
- `tests/application/test_grounded_query_service.py`

**Estimated scope:** Small: 2 files

## Task 5: Verify Runtime Composition

**Description:** Ensure `AzureRagRuntime` composes credential, embedder, retriever, MAF generator, and application service with the tightened contracts.

**Acceptance criteria:**
- [ ] Runtime passes bounded `search_top` into the retriever.
- [ ] Runtime keeps one shared Azure credential across embedder, retriever, and generator.
- [ ] Runtime answer path logs start and completion with correlation ID, question length, answer length, and decline status if available.
- [ ] Runtime close still closes retriever, embedder, and credential.

**Verification:**
- [ ] `pytest tests/infrastructure/test_runtime.py`

**Dependencies:** Tasks 1 and 2

**Files likely touched:**
- `src/homestyle_agent/infrastructure/runtime.py`
- `tests/infrastructure/test_runtime.py`

**Estimated scope:** Small: 2 files

### Checkpoint: Core RAG

- [ ] `pytest tests/application/test_grounded_query_service.py tests/infrastructure/test_azure_search_section_retriever.py tests/infrastructure/test_runtime.py`
- [ ] If created, `pytest tests/infrastructure/test_maf_grounded_body_generator.py`
- [ ] No new dependencies added.
- [ ] No secrets or connection strings introduced.

### Phase 3: User-Facing Entry Point

## Task 6: Add HTTP Ask API

**Description:** Add an HTTP API boundary for asking a question through `AzureRagRuntime` with validated request and response shapes.

**Acceptance criteria:**
- [ ] An HTTP endpoint accepts a question string and optional session identifier.
- [ ] Request validation rejects empty or overly long questions.
- [ ] Settings are loaded through `AzureRagSettings.from_env()`.
- [ ] Runtime resources are closed even when the answer call fails.
- [ ] User-facing errors do not expose stack traces, prompts, Azure SDK internals, or file paths.

**Verification:**
- [ ] Add focused API tests with faked runtime dependencies.

**Dependencies:** Task 5

**Files likely touched:**
- `src/homestyle_agent/api/`
- `tests/` matching the HTTP API entry point

**Estimated scope:** Medium: 3-5 files

## Task 7: Add Multi-Turn Session Handling

**Description:** Preserve multi-turn session continuity at the API/runtime boundary while keeping retrieved evidence authoritative for each answer.

**Acceptance criteria:**
- [ ] API responses include a session identifier when one is not supplied.
- [ ] Follow-up requests with the same session identifier retain conversation continuity.
- [ ] Session history cannot override the rule that final answers must be grounded in retrieved evidence.
- [ ] Session state storage is explicit and does not rely on hidden global mutable state.

**Verification:**
- [ ] Add focused session tests with faked runtime/model dependencies.

**Dependencies:** Tasks 3, 5, and 6

**Files likely touched:**
- `src/homestyle_agent/api/`
- `src/homestyle_agent/infrastructure/runtime.py`
- `tests/` matching the API/runtime session behavior

**Estimated scope:** Medium: 3-5 files

## Task 8: Add End-to-End Smoke Test With Fakes

**Description:** Add a no-network smoke test that exercises question -> retrieval fake -> MAF generator fake -> final answer through the public runtime or application boundary.

**Acceptance criteria:**
- [ ] Test uses real `GroundedQueryService` behavior.
- [ ] Test fakes only external Azure/model clients.
- [ ] Test verifies grounded answer, deterministic citations, filtering, and decline path.
- [ ] Test covers the HTTP API answer path and session identifier handling.
- [ ] Test does not require real Azure credentials or network access.

**Verification:**
- [ ] `pytest tests/application/test_ingestion_and_grounded_query_smoke.py tests/infrastructure/test_runtime.py`

**Dependencies:** Tasks 1, 3, 4, 5, 6, and 7

**Files likely touched:**
- Existing smoke test file or a new focused test file under `tests/application/`

**Estimated scope:** Small: 1-2 files

## Task 9: Add Minimal README Usage

**Description:** Document the minimum HTTP API usage path without adding broad operational documentation.

**Acceptance criteria:**
- [ ] README shows required environment variables by name only, with no secret values.
- [ ] README shows how to start the API and ask one question.
- [ ] README states answers are grounded in Azure AI Search and include source citations.

**Verification:**
- [ ] Documentation contains no credentials, tokens, connection strings, or real tenant-specific values.

**Dependencies:** Tasks 6 and 7

**Files likely touched:**
- `README.md`

**Estimated scope:** XS: 1 file

### Checkpoint: Complete

- [ ] `pytest`
- [ ] `ruff check .`
- [ ] `mypy src`
- [ ] Success criteria in `specs/homestyle-agent-agentic-rag.md` are met or explicitly marked out of scope.
- [ ] Resolved decisions in `specs/homestyle-agent-agentic-rag.md` are reflected in code and tests.

## Parallelization Opportunities

- Tasks 1 and 2 can be implemented in parallel after agreeing on the exact evidence fields.
- Task 3 can proceed once Task 1 defines the filtered evidence shape.
- Tasks 6 and 7 should wait until runtime composition is stable.
- Review of prompt wording can happen in parallel with retriever tests because it does not change Azure Search behavior.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Azure Search index lacks `section_heading` or filterable `locale` | Medium | Keep normalization defaults and enforce required trust checks in application code. |
| Model follows prompt-injection text inside retrieved content | High | State retrieved content is evidence, not instructions; deterministic citations outside model; filter unsupported URLs. |
| HTTP API and multi-turn state expand the first release | Medium | Keep the API minimal, validate inputs at the boundary, and avoid adding a web UI. |
| Tests over-mock internal logic | Medium | Use real `GroundedQueryService` and fake only Azure/model clients. |
| Context flooding from long section content | Medium | Trim per-section content in prompt construction and preserve citations/provenance. |

## Resolved Questions

1. Duplicate URLs are deduplicated in citations.
2. `reviewer_approved` remains metadata; filtering uses `confidence_score >= 0.7`.
3. The first user-facing entry point is an HTTP API.
4. Configured `search_top` is capped at `5`.
5. Add minimal README usage documentation.
6. Multi-turn sessions are included in the first release.

## Implementation Gate

Do not start implementation until this plan is reviewed. Each task should be executed with test-driven development: write or update the behavior test first, confirm the failure when practical, implement the smallest change, and run the task verification command.