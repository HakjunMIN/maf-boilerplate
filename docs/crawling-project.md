# 구현된 크롤링 프로젝트

이 문서는 현재 저장소에 실제로 구현된 크롤링 프로젝트의 범위와 흐름만 정리한다. 개발 프로세스나 작업 방식은 [README](../README.md)를 기준으로 보고, 여기서는 구현 산출물 자체에 집중한다.

## 프로젝트 목표

LG 홈스타일 공개 웹 콘텐츠를 수집해 페이지 단위 Markdown으로 저장하고, 이를 Azure AI Search에 섹션 단위로 인덱싱한 뒤, Microsoft Agent Framework 기반 응답 계층에서 근거로 재사용할 수 있게 만드는 것이다.

## 현재 구현된 파이프라인

```text
robots.txt / sitemap
  -> URL discovery
  -> conditional fetch
  -> Playwright rendering
  -> DOM extraction
  -> selective VLM enrichment
  -> page markdown 저장
  -> section splitting
  -> Azure AI Search indexing
  -> grounded query runtime 연결
```

## 구현 포인트

### 1. Discovery

- `robots.txt`에서 sitemap 진입점을 찾는다.
- sitemap을 따라가며 대상 URL을 수집한다.
- 현재 설정은 `config/discovery.toml` 기준으로 `homestyle.lge.co.kr` 호스트와 `ko` 로케일을 중심으로 동작한다.

### 2. Fetch

- 변경 감지를 위해 `ETag`, `Last-Modified`, `content hash`를 사용한다.
- Full crawl과 incremental refresh가 같은 파이프라인을 공유하도록 설계되어 있다.
- 재실행 시 중복 적재보다 idempotent 동작을 우선한다.

### 3. Rendering / Extraction

- Playwright headless browser로 렌더링한다.
- DOM에서 먼저 본문을 추출한다.
- 텍스트가 부족하고 이미지 비중이 높은 블록만 선택적으로 VLM 보강을 수행한다.
- 결과는 페이지 단위 Markdown과 메타데이터로 남긴다.

### 4. Indexing

- 페이지 단위 Markdown을 저장한 뒤, 인덱싱 시점에만 섹션으로 분할한다.
- Azure AI Search에는 검색용 텍스트와 벡터를 함께 올린다.
- 저신뢰 결과는 검토 큐로 보내고 검색 인덱스에서는 제외하는 흐름을 염두에 두고 구조를 잡았다.

### 5. Agent 연결

- 검색 계층과 에이전트 계층은 느슨하게 결합되어 있다.
- 검색 결과는 Agent Framework 런타임에 명시적인 grounding context로 전달된다.
- 응답은 수집된 근거 바깥으로 확장하지 않는 것을 원칙으로 한다.

## 코드 맵

- `src/homestyle_ingestion/application`: discovery, ingestion, manual crawl orchestration
- `src/homestyle_ingestion/domain`: fetch/extraction/rendering/review queue 도메인 모델
- `src/homestyle_ingestion/infrastructure`: fetcher, renderer, storage, indexer 구현
- `src/homestyle_agent/application`: grounded query 유스케이스
- `src/homestyle_agent/infrastructure`: retrieval 및 Agent Framework 연결
- `tests/application`: 파이프라인과 서비스 테스트
- `tests/infrastructure`: Azure, Playwright, local storage 경계 테스트

## 수동 검증 경로

현재 저장소에는 구현을 손으로 검증할 수 있는 경로도 포함되어 있다.

- `scripts/sample_vlm_index.py`: 실제 사이트를 제한적으로 크롤링하고 VLM 보강 후 인덱싱하는 스크립트
- `src/homestyle_ingestion/manual_crawl_cli.py`: 수동 크롤을 위한 CLI 진입점
- [scripts/README.md](../scripts/README.md): 실행 전제와 옵션 설명

## 테스트 관점

테스트는 내부 구현 디테일보다 외부에서 보이는 동작을 고정하는 데 초점을 둔다.

- discovery 필터링이 기대대로 동작하는지
- conditional fetch가 변경 여부를 올바르게 판단하는지
- DOM 추출과 VLM 트리거 정책이 의도대로 나뉘는지
- section splitting과 index 문서 생성이 안정적인지
- grounded query가 근거 부족 시 안전하게 decline하는지

## 현재 범위와 경계

- 로그인이나 비공개 페이지는 다루지 않는다.
- 1차 범위는 한국어 콘텐츠다.
- PDF나 임의 첨부파일 처리는 포함하지 않는다.
- 저신뢰 VLM 결과를 자동으로 검색 인덱스에 넣지 않는다.
- review queue UI는 아직 만들지 않았다.

## 함께 보면 좋은 문서

- [README](../README.md)
- [PRD.md](../PRD.md)
- [UBIQUITOUS_LANGUAGE.md](../UBIQUITOUS_LANGUAGE.md)
- [scripts/README.md](../scripts/README.md)