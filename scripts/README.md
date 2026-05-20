# scripts

## scripts/measure_lsp_context_impact.py — LSP 컨텍스트 절감 측정

grep으로 심볼이 포함된 파일 전체를 읽는 방식과 LSP reference 목록만 읽는 방식을 같은 토큰 추정식으로 비교한다. LSP 출력은 VS Code symbol references 또는 에이전트의 `vscode_listCodeUsages` 결과를 텍스트 파일로 저장해 입력한다.

```bash
uv run python scripts/measure_lsp_context_impact.py DiscoveredUrl \
  --lsp-usages-file /path/to/discovered-url-usages.txt
```

출력 JSON의 주요 필드는 다음과 같다.

| 필드 | 설명 |
|------|------|
| `grep_tokens` | grep식 전체 파일 컨텍스트의 추정 토큰 수 |
| `lsp_tokens` | LSP usage line 컨텍스트의 추정 토큰 수 |
| `token_reduction_percent` | LSP 사용으로 줄어든 추정 토큰 비율 |
| `scanned_lines` | grep식 접근에서 읽는 전체 라인 수 |
| `focus_lines` | LSP가 지목한 usage 라인 수 |
| `focus_multiplier` | 전체 라인 수가 usage 라인 수보다 몇 배 큰지 |

## scripts/sample_vlm_index.py — 수동 E2E 테스트

### 목적

인제스천 파이프라인 전체를 로컬에서 수동으로 검증하는 스크립트.  
실제 사이트(`homestyle.lge.co.kr`)에서 최대 10페이지를 크롤링하고,  
VLM(Vision Language Model)으로 이미지 enrichment를 수행한 뒤 Azure AI Search에 인덱싱한다.

```
robots.txt → URL 수집 → Playwright 렌더링 → DOM 추출
→ VLM enrichment(이미지 → 한국어 markdown) → 섹션 분할 → 임베딩 → Search 인덱스 업로드
```

---

### 사전 조건

| 항목 | 최소 버전 / 설정 |
|------|-----------------|
| Python | 3.12 |
| Playwright 브라우저 | `uv run playwright install chromium` |
| Azure CLI (`az`) | 로그인 완료 (`az login`) |
| `.env` | 아래 환경변수 설정 완료 |

---

### .env 설정

`.env.example`을 복사해 `.env`로 만든 뒤 아래 값을 채운다.

```dotenv
# Azure AI Services (OpenAI) 엔드포인트
AZURE_OPENAI_ENDPOINT=https://<resource>.services.ai.azure.com
AZURE_OPENAI_API_VERSION=2024-10-01-preview

# 배포 이름
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small   # 1536-dim
AZURE_OPENAI_VISION_DEPLOYMENT=gpt-4o                      # vision 지원 모델

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://<service>.search.windows.net
AZURE_SEARCH_INDEX_NAME=homestyle-product-sample

# 로컬 개발 시 DefaultAzureCredential 사용
USE_DEVELOPER_CREDENTIALS=true
MANAGED_IDENTITY_CLIENT_ID=

# (권장) Search 문서 업로드용 Admin Key
# RBAC "Search Index Data Contributor" 역할이 없으면 반드시 설정
AZURE_SEARCH_ADMIN_KEY=<admin-key>
```

---

### 실행

```bash
# 가상환경 활성화
source .venv/bin/activate

# 기본 실행 (robots.txt 기반 10페이지)
PYTHONPATH=src python scripts/sample_vlm_index.py

# 선택 옵션
PYTHONPATH=src python scripts/sample_vlm_index.py \
  --max-urls 5 \
  --output-dir .my-crawl \
  --extraction-version my-v1
```

### CLI 옵션

| 옵션 | 기본값 | 설명 |
|------|--------|------|
| `--robots-url` | `https://homestyle.lge.co.kr/robots.txt` | 크롤 시작 robots.txt |
| `--config` | `config/discovery.toml` | URL 필터 설정 파일 |
| `--output-dir` | `.sample-vlm-crawl` | 결과 저장 디렉터리 |
| `--max-urls` | `10` | 최대 크롤링 URL 수 |
| `--user-agent` | `LGHomeStyleBot/1.0` | HTTP User-Agent |
| `--extraction-version` | `sample-vlm-v1` | 인덱싱 버전 태그 |

---

### 출력물

실행 후 `--output-dir`(기본 `.sample-vlm-crawl`) 아래에 생성된다.

```
.sample-vlm-crawl/
├── markdown/
│   ├── <product-id>.md          # DOM + VLM 결합 markdown
│   └── <product-id>.json        # 세그먼트 메타데이터
├── pages/
│   └── ...                      # LocalPageStore 원본 HTML 캐시
└── review/
    └── run-summary.json         # 실행 요약 (인덱싱된 chunk_id 목록 포함)
```

Azure AI Search `AZURE_SEARCH_INDEX_NAME` 인덱스에 섹션 단위 벡터 문서가 업로드된다.

---

### 재실행 동작

`pages/` 캐시에 저장된 페이지는 conditional fetch(ETag / content hash)로 변경 여부를 확인한다.  
변경이 없으면 스킵되므로 0 chunks가 인덱싱될 수 있다.  
전체를 다시 인덱싱하려면 캐시를 삭제한다.

```bash
rm -rf .sample-vlm-crawl
```

---

### 검증 포인트

| 단계 | 정상 로그 예시 |
|------|---------------|
| 렌더링 | `Rendering [N/10] https://...` |
| VLM enrichment | `All 9 pages enriched with VLM` |
| 임베딩 | `Embedding N sections for <product-id>` |
| 업로드 | `Indexed N documents` |
| 최종 출력 | `Indexed N chunks into <index-name>` |

---
