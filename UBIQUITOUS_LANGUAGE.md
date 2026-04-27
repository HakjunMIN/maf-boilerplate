# Ubiquitous Language

## Discovery

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Sitemap Index** | `https://homestyle.lge.co.kr/robots.txt`가 가리키는 최상위 XML 문서(`https://static-store.lge.co.kr/sitemap/sitemap.xml`)로, category/page-type별 Sub-sitemap URL을 나열한다 | root sitemap, master sitemap |
| **Sub-sitemap** | Sitemap Index가 참조하는 category/page-type별 하위 사이트맵 XML 문서 (예: `sitemap_product-list.xml`) | child sitemap, category sitemap |
| **Path/Query Allowlist** | 크롤 대상 URL의 경로와 주요 쿼리 패턴을 결정하는 설정 파일 기반 허용 목록 (예: `/home`, `/collection`, `/shop?`) | whitelist, URL filter, include list |
| **Discovery** | Sitemap Index → Sub-sitemap → Path/Query Allowlist 순으로 크롤 대상 URL을 식별하는 과정 | URL scanning, site scanning |
| **Discovered URL** | Discovery를 통과하여 Fetch 후보가 된 `homestyle.lge.co.kr` 단일 URL | target URL, candidate URL |
| **Locale** | 콘텐츠의 언어·지역 범위를 나타내는 식별자 (1차 릴리스: `ko`, 현재 소스 사이트는 한국어 단일 사이트) | language, region, country |

## Crawling

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Fetch** | 단일 Discovered URL에 대한 HTTP 요청으로 원시 HTML(또는 렌더링된 DOM)을 가져오는 행위 | download, request, crawl (단수) |
| **Conditional Fetch** | `ETag`·`Last-Modified` 헤더를 이용해 변경 여부를 판단한 뒤, 변경된 경우에만 본문을 받는 Fetch | incremental fetch, smart fetch |
| **Content Hash** | 페이지 본문을 정규화한 뒤 생성한 해시값으로, ETag·Last-Modified가 없을 때 변경 감지의 마지막 수단 | fingerprint, digest, checksum |
| **Full Crawl** | 모든 Discovered URL을 변경 여부와 관계없이 Fetch하는 파이프라인 실행 모드 | initial crawl, seed crawl, full sync |
| **Incremental Refresh** | 변경되었거나 새로 발견된 URL만 Fetch하는 파이프라인 실행 모드 (일일 기본 운영) | delta crawl, incremental sync, daily refresh |
| **Fetch Metadata** | Fetch 시점에 기록되는 per-page 메타 정보 (`url`, `etag`, `last_modified`, `content_hash`, `fetch_timestamp`) | crawl state, HTTP metadata |

## Extraction

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Page** | 단일 URL로 식별되는 웹 페이지; 크롤링·저장·추출의 원자 단위 | document (저장 맥락과 혼동), web page, site |
| **Block** | Page 내에서 시각적으로 구분되는 DOM 영역 (히어로 배너, 카드, 섹션 등) | component, region, element, area |
| **Content Area** | Page DOM에서 콘텐츠 본문이 위치하는 영역 (`main`, `article`, `[role="main"]`) | main content, body area |
| **Boilerplate** | 모든 Page에 공통으로 반복되는 비콘텐츠 영역 (`nav`, `footer`, `header`, `.cookie-banner`) | chrome, navigation, decoration |
| **DOM Extraction** | Playwright로 렌더링한 Page DOM에서 CSS selector 기반으로 텍스트를 추출하는 단계 | HTML parsing, text extraction, scraping |
| **VLM Extraction** | 텍스트가 부족하고 이미지가 많은 Block에 GPT-4o를 적용하여 이미지 속 텍스트·의미를 추출하는 단계 | image extraction, OCR, vision extraction |
| **Meaningful Image** | 콘텐츠 정보를 담을 가능성이 있는 이미지 (width ≥ 200px, 아이콘·장식 이미지 제외) | content image, significant image |
| **Decorative Image** | 콘텐츠 정보가 없는 아이콘·스페이서·장식 이미지 (width < 100px 또는 `aria-hidden`) | icon, spacer, presentational image |
| **Breadcrumb** | Page의 사이트 내 위치를 나타내는 계층 경로 (DOM에서 추출, fallback으로 URL 경로 분석) | navigation path, page path |
| **Extraction Version** | 추출 로직(DOM 파서 + VLM 프롬프트)의 버전 식별자; 로직 변경 시 재처리 범위를 결정한다 | parser version, pipeline version |

## Corpus & Storage

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Page Markdown** | 하나의 Page에서 추출한 콘텐츠를 Markdown으로 변환한 문서; Corpus의 원자 저장 단위 | raw Markdown, page document, extracted document |
| **Corpus** | 전체 Page Markdown + Fetch/Extraction 메타데이터의 집합; 검색 인덱스의 원천 | knowledge base, data store, content store |
| **Soft-Delete** | 사이트맵에서 사라진 Page를 검색에서 즉시 제외하되 7일간 데이터를 보존하는 상태 | logical delete, deactivation |
| **Hard-Delete** | Soft-Delete 후 7일이 경과한 Page의 데이터와 인덱스 항목을 영구 삭제하는 행위 | permanent delete, purge |

## Quality & Review

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Confidence Score** | VLM Extraction 결과의 신뢰도를 나타내는 0.0–1.0 점수 (VLM 자체 평가 + 추출 텍스트 길이 휴리스틱) | quality score, reliability score |
| **Low-Confidence** | Confidence Score < 0.7인 VLM Extraction 결과; 인덱싱에서 제외되고 Review Queue로 라우팅된다 | uncertain, unreliable, below threshold |
| **Review Queue** | Low-Confidence 추출 결과를 승인 대기 상태로 보관하는 저장소 (1차: DB 테이블, UI 없음) | moderation queue, approval queue |
| **Reviewer Approval** | Review Queue 항목을 수동 검토 후 인덱싱을 허용하는 행위 | manual approval, content approval |

## Search & Indexing

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Section** | Page Markdown을 h2/h3 헤딩 경계에서 분할한 단위; Azure AI Search 인덱스의 문서 단위 | chunk, segment, passage, fragment |
| **Section Splitting** | Page Markdown → Section 분할 과정 (인덱싱 단계에서만 수행, 저장은 Page 단위 유지) | chunking, segmentation |
| **Index** | Azure AI Search에 저장된 Section 문서의 집합; 에이전트가 검색하는 대상 | search index, vector store |
| **Hybrid Search** | 키워드 검색과 벡터 검색을 결합한 검색 방식 | combined search, multi-modal search |
| **Embedding** | Section의 텍스트를 `text-embedding-3-small` 모델로 변환한 1536차원 벡터 | vector, dense representation |
| **Provenance** | Section이 어떤 Page에서, 어떤 Extraction Version으로, 어떤 방식(DOM/VLM)으로 생성되었는지를 나타내는 출처 정보 | lineage, origin, source tracking |

## Agent & Grounding

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Agent** | Microsoft Agent Framework 기반으로 구현된 한국어 QA 런타임; 사용자 질문에 Grounded Answer를 반환한다 | chatbot, bot, assistant |
| **Grounding Context** | Agent의 응답 생성 시 프롬프트에 주입되는 검색된 Section 집합; Agent가 참조할 수 있는 유일한 근거 | retrieved context, search results, RAG context |
| **Grounded Answer** | Grounding Context에 포함된 증거만으로 구성된 Agent 응답; 증거 밖의 추론·합성을 금지한다 | factual answer, evidence-based answer, cited answer |
| **Citation** | Grounded Answer 말미에 번호 각주로 첨부되는 출처 URL과 Section 참조 (예: `[1] https://...`) | reference, source link, footnote |
| **Evidence** | 특정 답변 주장을 뒷받침하는 Grounding Context 내 Section 콘텐츠 | support, proof, backing |
| **Decline** | 충분한 Evidence가 없을 때 Agent가 답변을 거부하는 동작 ("현재 수집된 … 찾을 수 없습니다.") | fallback, "I don't know", refusal |

## Pipeline & Operations

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Ingestion Pipeline** | Discovery → Fetch → Extraction → Storage → Indexing의 전체 데이터 수집·처리 워크플로 | data pipeline, ETL, crawler pipeline |
| **Pipeline Run** | Ingestion Pipeline의 단일 실행 인스턴스 (Full Crawl 또는 Incremental Refresh) | batch run, job execution |
| **Correlation ID** | 하나의 Pipeline Run 또는 Agent 요청을 관통하여 로그·트레이스를 연결하는 고유 식별자 | request ID, trace ID, run ID |
| **Idempotency** | 같은 Pipeline Run을 재실행해도 중복 콘텐츠나 비일관 상태가 발생하지 않는 속성 | retry safety, duplicate prevention |

## Relationships

- 하나의 **Sitemap Index**는 여러 **Sub-sitemap**을 참조한다.
- **Sub-sitemap** 내 URL은 **Path/Query Allowlist**를 통과해야 **Discovered URL**이 된다.
- 하나의 **Discovered URL**은 **Fetch**를 거쳐 하나의 **Page**가 된다.
- 하나의 **Page**는 여러 **Block**으로 구성된다.
- 각 **Block**은 **DOM Extraction**을 거치며, 조건 충족 시 **VLM Extraction**도 적용된다.
- 하나의 **Page**에서 하나의 **Page Markdown**이 생성된다.
- **Page Markdown**은 **Section Splitting**을 거쳐 여러 **Section**으로 분할된다.
- **Section**은 **Embedding**과 함께 **Index**에 저장된다.
- **Agent**는 **Hybrid Search**로 **Index**에서 **Section**을 검색하여 **Grounding Context**를 구성한다.
- **Agent**는 **Grounding Context** 내 **Evidence**만으로 **Grounded Answer**를 생성하고, 각 주장에 **Citation**을 첨부한다.
- **Confidence Score**가 낮은(< 0.7) VLM Extraction 결과는 **Review Queue**로 라우팅되며, **Reviewer Approval** 전까지 **Index**에 포함되지 않는다.
- **Soft-Delete**된 **Page**의 **Section**은 **Index**에서 즉시 제외되고, 7일 후 **Hard-Delete**된다.

## Example dialogue

> **Dev:** "Incremental Refresh에서 Sub-sitemap에 있던 URL이 사라지면 어떻게 되나요?"
>
> **Domain expert:** "해당 **Page**가 **Soft-Delete** 상태가 됩니다. **Index**에서 관련 **Section**이 즉시 검색 제외되고, 7일 후 **Hard-Delete**로 영구 삭제됩니다."
>
> **Dev:** "**DOM Extraction** 결과가 있는데 **VLM Extraction**도 하는 경우는요?"
>
> **Domain expert:** "**Block** 단위로 판단합니다. 특정 **Block**의 텍스트가 50자 미만이고 **Meaningful Image**가 있으면 그 **Block**에만 **VLM Extraction**을 적용합니다. **DOM Extraction** 결과와 합쳐서 하나의 **Page Markdown**이 됩니다."
>
> **Dev:** "**VLM Extraction**에서 **Confidence Score**가 0.5가 나왔다면?"
>
> **Domain expert:** "0.7 미만이니 **Low-Confidence**입니다. 해당 추출 결과는 **Review Queue**에 들어가고, **Section Splitting**이나 **Index** 등록 대상에서 제외됩니다. **Reviewer Approval**을 받으면 그때 인덱싱됩니다."
>
> **Dev:** "**Agent**가 답변할 때 **Evidence**가 부족하면요?"
>
> **Domain expert:** "**Decline**합니다. '현재 수집된 LG 홈스타일 콘텐츠에서 해당 정보를 찾을 수 없습니다'라고 응답하고, 절대 **Grounding Context** 밖의 정보를 합성하지 않습니다."

## Flagged ambiguities

- **"chunk" vs "section"** — PRD에서 "indexed chunk"와 "section-level documents"가 혼용되었다. 코드와 대화에서는 **Section**을 정식 용어로 사용한다. "chunk"는 일반적인 NLP 용어이므로 혼동을 피하기 위해 이 프로젝트에서는 사용하지 않는다.
- **"crawl" vs "fetch"** — "crawl"은 전체 파이프라인(Discovery + Fetch)을 포괄하는 느슨한 표현이다. 단일 URL에 대한 HTTP 요청은 **Fetch**, 전체 워크플로는 **Ingestion Pipeline**(또는 Pipeline Run)으로 구분한다. "crawl"은 Full Crawl/Incremental Refresh의 모드 이름에만 사용한다.
- **"document" vs "page"** — "document"는 검색 인덱스의 단위(Section)로도, 저장된 Markdown(Page Markdown)으로도 해석될 수 있다. 웹 페이지를 가리킬 때는 **Page**, 인덱스 단위는 **Section**, 저장 단위는 **Page Markdown**으로 구분한다.
- **"content"** — "page content"(HTML 원문), "extracted content"(Markdown), "indexed content"(Section)가 모두 "content"로 불릴 수 있다. 맥락이 불분명할 때는 **원시 HTML**, **Page Markdown**, **Section** 중 정확한 단계를 명시한다.
- **"extraction" vs "parsing"** — "parsing"은 DOM 트리 구성을 의미할 수 있고, "extraction"은 의미 있는 텍스트를 뽑는 것을 의미한다. 이 프로젝트에서는 DOM에서 텍스트를 뽑는 전체 과정을 **DOM Extraction**, 이미지에서 텍스트를 뽑는 것을 **VLM Extraction**으로 통일한다. "parsing"은 사용하지 않는다.
- **"corpus" vs "index"** — **Corpus**는 Page Markdown + 메타데이터의 전체 집합(원천 데이터), **Index**는 Azure AI Search에 올라간 Section 집합(검색 대상)이다. Corpus에 있지만 Index에 없는 콘텐츠가 존재할 수 있다(Low-Confidence, Soft-Deleted).
