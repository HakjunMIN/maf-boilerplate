# PRD: LG 홈스타일 콘텐츠 기반 RAG 에이전트

## Problem Statement

LG 홈스타일 관련 웹 콘텐츠를 바탕으로 질문에 답하는 에이전트를 만들고 싶지만, 대상 사이트의 핵심 정보가 일반 HTML 텍스트뿐 아니라 이미지 내부 카피, 배너 문구, 카드형 섹션 구성에도 포함되어 있다. 공개 API가 없기 때문에 공개 웹 페이지를 직접 수집해야 하고, 초기 대량 적재 이후에는 변경된 콘텐츠만 효율적으로 다시 수집해야 한다. 최종적으로는 이 데이터를 Azure AI Search에 인덱싱하고, Microsoft Agent Framework 기반 에이전트가 근거 중심으로 응답하도록 만들어야 한다.

## Solution

`https://homestyle.lge.co.kr/home`를 기준으로 한 한국어 LG 홈스타일 공개 페이지를 대상으로, 사이트맵 기반 URL discovery와 조건부 HTTP 요청 기반 증분 수집을 수행한다. 본문 추출은 Playwright headless browser로 동적 렌더링 후 DOM에서 콘텐츠를 추출하되, 텍스트 밀도가 낮고 이미지 비중이 높은 블록에는 선택적으로 Azure OpenAI의 **GPT-5.4 vision-capable deployment**를 적용해 페이지 단위 Markdown을 생성한다. 생성된 Markdown은 페이지 단위로 보관하고, 검색 품질을 위해 Azure AI Search 인덱싱 단계에서 헤딩 기반으로 섹션 분할 후 하이브리드 검색(키워드 + 벡터)으로 인덱싱한다. 에이전트는 Microsoft Agent Framework 기반으로 검색된 근거와 출처 URL만 사용해 한국어로 답변하고, 근거가 없으면 추측하지 않는다.

## User Stories

1. As a Korean-speaking end user, I want to ask questions about LG 홈스타일 콘텐츠 in Korean, so that I can get answers in my preferred language.
2. As an end user, I want the agent to answer only from LG 홈스타일 source content, so that I can trust the response.
3. As an end user, I want every answer to include source URLs and relevant sections, so that I can verify the claim.
4. As an end user, I want the agent to say it does not know when evidence is missing, so that it does not hallucinate.
5. As a product owner, I want the system to crawl only public HTML pages, so that the solution stays within the intended access boundary.
6. As a product owner, I want the first release limited to the `ko` locale, so that scope, cost, and duplicate handling remain manageable.
7. As a product owner, I want the crawler to focus only on 홈스타일 가구-related content, so that irrelevant LG pages do not pollute the corpus.
8. As a platform engineer, I want sitemap-driven discovery, so that the system can scale to a large URL inventory without blind crawling.
9. As a platform engineer, I want incremental recrawling based on `ETag`, `Last-Modified`, and content hashes, so that daily refreshes are efficient.
10. As a platform engineer, I want the system to preserve fetch metadata and extraction versions, so that changes and regressions can be traced.
11. As a content pipeline engineer, I want DOM extraction to run before VLM extraction, so that the cheaper and more deterministic signal is used first.
12. As a content pipeline engineer, I want VLM to run only on image-heavy or text-poor blocks, so that extraction cost stays controlled.
13. As a content pipeline engineer, I want page-level Markdown outputs, so that the raw retrieval corpus is easy to inspect and manage.
14. As a search engineer, I want page Markdown to be split into sections only at indexing time, so that retrieval quality improves without losing page-level provenance.
15. As a search engineer, I want each indexed chunk to carry URL, locale, title, breadcrumb, confidence, and image-derived flags, so that filters and ranking can use them.
16. As a quality owner, I want low-confidence VLM results excluded from the searchable index, so that weak evidence does not degrade answer quality.
17. As a reviewer, I want low-confidence extractions routed to a review queue, so that questionable content can be inspected before use.
18. As an operator, I want failed fetches, parse failures, and VLM failures logged separately, so that operational issues can be triaged quickly.
19. As an operator, I want the ingestion pipeline to be idempotent, so that retries do not create duplicate content or inconsistent state.
20. As a developer, I want the retrieval layer and agent layer to be loosely coupled, so that indexing or answer orchestration can evolve independently.
21. As a developer, I want the agent implemented with Microsoft Agent Framework, so that it can use structured orchestration, tool integration, and production-ready patterns.
22. As a developer, I want the retrieval results injected into the agent as explicit grounding context, so that answer generation remains constrained by evidence.
23. As a future maintainer, I want locale handling to be explicit in metadata and discovery rules, so that additional locales can be added later without redesigning the system.
24. As a future maintainer, I want extraction and indexing versions tracked, so that corpus rebuilds can be targeted when logic changes.

## Implementation Decisions

### URL Discovery & Scope

- The first release targets a single locale: `ko`.
- The first release targets only public HTML pages published under `https://homestyle.lge.co.kr`.
- URL discovery begins from the sitemap entrypoint declared in `https://homestyle.lge.co.kr/robots.txt` (`https://static-store.lge.co.kr/sitemap/sitemap.xml`), follows the category/page-type sub-sitemaps under `https://homestyle.lge.co.kr/sitemap/`, then keeps only product detail URLs.
- A URL is in scope only when the host is `homestyle.lge.co.kr`, the path is exactly `/item`, and the query string contains a non-empty `productId` parameter. Additional query parameters are allowed.
- URLs outside the `homestyle.lge.co.kr` host or outside the product detail rule are excluded from the first release.
- Sitemap entries without `<lastmod>` are **always fetched** (change detection relies on conditional HTTP headers, not sitemap timestamps alone).

### Crawling & Incremental Refresh

- `robots.txt` is **mandatory to respect**, including any `Crawl-delay` directives.
- Request throttling: **0.5-second delay** between requests, up to **5 concurrent requests**.
- User-Agent: a project-identifying string (e.g., `LGHomeStyleBot/1.0`).
- Conditional fetch logic prioritizes `ETag` and `Last-Modified`, with normalized content hashing as the fallback change detector.
- Individual URL fetch failures retry up to **3 times** with exponential backoff + jitter, then skip with `fetch_failed: true` in metadata.
- Execution: **Azure Container App Job** (Timer trigger, daily).
- Full crawl and incremental refresh use the **same pipeline** with a `--mode full|incremental` flag.
- Deleted page detection: URLs that disappear from the sitemap are **soft-deleted** from the index (excluded from search immediately, hard-deleted after 7 days).

### Content Extraction

- Pages are rendered using **Playwright headless browser** to capture JavaScript-rendered content, then parsed with **BeautifulSoup4 + lxml**.
- Content area identification uses **CSS selector allowlist** (`main`, `article`, `[role="main"]`) with a **boilerplate blocklist** (`nav`, `footer`, `header`, `.cookie-banner`).
- Breadcrumb extraction from DOM elements (`breadcrumb`-related selectors), falling back to URL path analysis.
- DOM extraction runs **before** VLM extraction (cheaper, more deterministic).

### VLM (Vision Language Model) Extraction

- VLM model: **Azure OpenAI GPT-5.4** deployment with vision input enabled.
- VLM trigger conditions (all must be met):
  - Extracted text within a block < **50 characters**
  - At least one meaningful image present (width ≥ **200px**)
  - Icons and decorative images excluded: width < 100px, `role="presentation"`, or `aria-hidden="true"`.
- Images resized to **1024px on the longest side** before VLM submission (token cost control).
- Per-page VLM call limit: **maximum 10 invocations**.
- VLM confidence scoring: self-assessment score (0.0–1.0) requested in the VLM prompt, combined with extracted text length heuristic.
- Confidence threshold: **< 0.7 = low-confidence**.
- Low-confidence results: persisted in storage with `low_confidence: true` for audit, **excluded from search indexing**.
- VLM failures: 3 retries, then skip with `vlm_failed: true` in metadata.
- All trigger thresholds are **configurable** via settings.
- Azure OpenAI authentication is **keyless by default**: local development uses `DefaultAzureCredential`, and deployed workloads use **Managed Identity**.

### Review Queue

- Low-confidence VLM extractions are routed to a **review queue** (database table in Cosmos DB / local JSON for dev).
- 1st release: **no review UI**. Approvals handled via manual script that marks items as approved and triggers re-indexing.
- Post-approval, content is indexed with `reviewer_approved: true` flag.

### Storage

- **Development**: local file system (Markdown files + JSON metadata).
- **Production (1st release)**: Azure Blob Storage (Markdown originals) + Cosmos DB (crawl metadata, review queue, indexing state).
- Storage layer is **abstracted behind an interface** to enable seamless switching between local and cloud backends.
- Canonical stored corpus: page-level Markdown + fetch/extraction metadata.
- Metadata fields per page: `url`, `locale`, `fetch_timestamp`, `etag`, `last_modified`, `content_hash`, `extraction_version`, `vlm_used`, `vlm_confidence`, `vlm_failed`, `is_deleted`, `deleted_at`, `indexing_status`.

### Search & Indexing

- Search backend: **Azure AI Search** with **hybrid search** (keyword + vector).
- Embedding model: **Azure OpenAI `text-embedding-3-small`**.
- Azure AI Search access uses **Microsoft Entra ID / Azure RBAC**, not API keys.
- Chunk splitting strategy: **Markdown heading-based** (h2/h3 boundaries), with **800-token fallback** for sections without headings.
- Index schema fields per chunk:
  - `chunk_id` (unique, searchable)
  - `page_url` (filterable)
  - `locale` (filterable, fixed `ko` for now)
  - `title` (searchable)
  - `breadcrumb` (searchable)
  - `section_heading` (searchable)
  - `content` (searchable, full-text)
  - `content_vector` (vector field, 1536 dimensions)
  - `confidence_score` (filterable, double)
  - `is_image_derived` (filterable, boolean)
  - `extraction_version` (filterable)
  - `indexed_at` (filterable, datetime)
- Low-confidence content (< 0.7) is **never indexed** unless explicitly approved through the review queue.

### Agent

- Runtime: **Microsoft Agent Framework** (Python).
- LLM backend: **Azure OpenAI GPT-5.4** for grounded response generation.
- Deployment: **Azure Container App** with REST API endpoint.
- Azure service authentication: **Microsoft Entra ID keyless authentication** (`DefaultAzureCredential` for local development, **Managed Identity** in Azure).
- Response language: **Korean only** (1st release, `ko` locale).
- Response format:
  - Concise answers in **3–5 sentences**.
  - Source citations as **numbered footnotes** at the end (e.g., `[1] https://homestyle.lge.co.kr/shop?...`).
  - When evidence is insufficient: "현재 수집된 LG 홈스타일 콘텐츠에서 해당 정보를 찾을 수 없습니다."
- Grounding: retrieval results are injected as **explicit grounding context**. The agent must not synthesize beyond retrieved evidence.
- No follow-up question suggestions in the 1st release.
- The first implementation slice is a **thin vertical path**: sample Section documents are indexed into Azure AI Search, retrieved with hybrid search, then passed into the Microsoft Agent Framework runtime for grounded answer generation.

### Architecture & Coupling

- The ingestion pipeline (discovery → fetch → extraction → storage → indexing) is **independent** from the agent runtime.
- The retrieval layer and agent layer are **loosely coupled** so that indexing or answer orchestration can evolve independently.
- Future locale expansion is a **configuration and discovery concern**, not a structural rewrite.
- Async-friendly boundaries throughout: Microsoft Agent Framework and network-heavy ingestion both benefit from non-blocking operations.
- Versioned extraction behavior: parser or VLM changes can trigger **targeted reprocessing** of affected pages.

### Observability

- Logging: **structlog** (JSON-structured) for development, **Azure Application Insights** for production.
- Per-pipeline-run metrics logged: `pages_discovered`, `pages_crawled`, `pages_changed`, `pages_unchanged`, `pages_failed`, `vlm_calls`, `vlm_failures`, `vlm_low_confidence_count`, `index_docs_upserted`, `index_docs_deleted`.
- Every request/operation carries a **correlation ID** for tracing.
- **PII is excluded** from all logs and traces.
- Alerting and dashboards: **deferred to post-1st-release**.

### Project Setup

- Package manager: **uv**.
- Python version: **3.12**.
- Repository structure: **monorepo** (crawler pipeline + agent share domain models).
- Formatter & linter: **ruff**.
- CI: **GitHub Actions** (PR-triggered test + lint).

## Testing Decisions

- Test framework: **pytest** + **pytest-asyncio**.
- HTTP mocking: **respx** (for httpx-based HTTP clients).
- Playwright testing: **pytest-playwright** where needed for browser-rendered content validation.
- Good tests validate externally visible behavior: discovery filtering, change detection decisions, Markdown generation outcomes, index-ready section generation, citation behavior, and grounded-answer enforcement.
- Tests avoid coupling to internal implementation details such as exact parser helper composition, prompt wording internals, or transient DOM traversal strategies.
- The most important modules to test are sitemap discovery and filtering, conditional fetch and change detection, DOM-to-Markdown extraction, selective VLM triggering policy, index document generation, and grounded answer composition.
- Network-facing integrations are mocked at the HTTP boundary for sitemap, page fetch, and conditional request behavior.
- Azure AI Search interactions are tested with mocked client boundaries for contract validation and with a limited integration path where practical.
- VLM calls are mocked in most tests so that confidence handling, fallback behavior, and review-queue routing can be exercised deterministically.
- Microsoft Agent Framework behavior is tested at the application boundary by validating the agent's grounded output behavior rather than framework internals.
- Regression tests ensure that unchanged pages are skipped correctly during daily batch runs.
- Regression tests ensure that content changes caused only by parser normalization do not silently bypass required re-indexing decisions.
- Quality tests verify that low-confidence extracted content never enters the searchable corpus.
- End-to-end smoke coverage validates the happy path from discovered page to indexed content to cited answer.
- Coverage target: **no explicit percentage goal** for the 1st release; focus on thorough testing of core modules (discovery, extraction, indexing, agent grounding).

## Out of Scope

- Login-protected or otherwise non-public pages
- Use of unpublished or private APIs
- Multi-locale ingestion in the first release
- Full-image or full-page VLM analysis on every page
- Automatic indexing of low-confidence image-derived content (requires review queue approval)
- Non-HTML content types such as PDFs and arbitrary attachments in the first release
- Answering with general web knowledge outside the collected LG 홈스타일 corpus
- Broad LG-wide product knowledge beyond the 홈스타일 furniture scope
- Review queue UI (1st release uses manual script-based approval)
- Alerting and monitoring dashboards (1st release uses log-based manual monitoring)
- Follow-up question suggestions in agent responses
- Multi-language agent responses (Korean only in 1st release)

## Further Notes

- The site exposes crawler guidance in `https://homestyle.lge.co.kr/robots.txt` and declares `https://static-store.lge.co.kr/sitemap/sitemap.xml` as the authoritative sitemap entrypoint, which should be treated as the discovery root unless LG changes that contract.
- Because LG page structures may vary across campaigns and landing pages, extraction quality depends on preserving enough provenance to re-run specific pages or blocks after parser updates.
- Page-level Markdown storage plus index-time section splitting is the preferred compromise between corpus manageability and retrieval quality.
- This PRD assumes daily incremental refresh as the initial operating cadence.
- This PRD assumes Azure AI Search as the first search backend and Microsoft Agent Framework as the agent runtime for the grounded QA experience.
- Estimated initial corpus size: 500–2,000 URLs, with daily change rate of approximately 5–10%.
- Storage abstraction enables local development without cloud dependencies while maintaining production parity.
- VLM trigger thresholds and crawling parameters are intentionally configurable to allow operational tuning without code changes.
