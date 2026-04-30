# homestyle-rag

![Engineering Quality](https://img.shields.io/badge/engineering%20quality-B%20(7.3%2F10)-yellowgreen)
![Pytest](https://img.shields.io/badge/pytest-78%2F79%20passing-yellow)
![Ruff](https://img.shields.io/badge/ruff-src%2Btests%20passing-brightgreen)

LG 홈스타일 공개 콘텐츠를 수집하고, Azure AI Search와 Microsoft Agent Framework를 이용해 근거 기반 한국어 응답을 제공하는 실험용 RAG 하네스다. 이 저장소는 기능 데모보다 소프트웨어 엔지니어링 기본기에 충실한 개발 하네스를 만드는 데 더 큰 비중을 두었다.

## 품질 스냅샷

현재 README의 배지는 2026-04-30에 로컬 워크스페이스에서 측정한 결과를 반영한다.

- 소프트웨어 공학 품질 평가: B, 7.3/10
- 테스트: 79개 중 78개 통과
- 린트: `ruff check src tests` 통과
- 참고: `ruff check .`는 샘플 스크립트 import 순서 이슈로 아직 실패한다.

## 이 저장소가 강조하는 것

- 인터뷰로 요구사항을 구체화한다.
- PRD를 먼저 만들고 범위를 고정한다.
- 유비쿼터스 언어를 정리해 용어 충돌을 줄인다.
- `application` / `domain` / `infrastructure`를 분리해 DDD 개념을 구조에 반영한다.
- TDD로 얇은 수직 슬라이스를 구현하며 verbose한 코딩을 줄인다.
- 작은 수정은 `triage-issue` 흐름으로 빠르게 다룬다.
- 병렬로 진행 가능한 작업은 `git worktree` 기반으로 분리한다.
- Azure AI와 Microsoft Agent Framework 관련 스킬을 적극 활용해 구현과 검증 속도를 높인다.

## 개발 방식

이 프로젝트의 개발 과정은 인터뷰를 통해 요구사항을 정밀화하고, 그 결과를 PRD와 유비쿼터스 언어로 고정한 뒤, 테스트를 먼저 세우고 구현을 얇게 전개하는 방식으로 진행했다. 흐름 자체는 사용자가 언급한 영상의 방식과 맞닿아 있지만, 이 저장소는 스펙을 단일 진실 공급원으로 삼는 개방형 운영 모델은 아니다. 즉, 스펙 문서는 중요한 경계이지만 코드, 테스트, 운영 판단이 함께 현실의 진실을 구성한다.

## 개발 라이프사이클

```mermaid
flowchart TD
  subgraph A[요구사항 정제]
    A1[인터뷰로 요구사항 구체화] --> A2[PRD 작성]
    A2 --> A3[유비쿼터스 언어 정리]
  end

  subgraph B[구현 준비]
    B1[테스트 시나리오 설계]
    B2[Azure AI / MAF 스킬 활용]
  end

  subgraph C[구현 루프]
    C1[TDD로 얇은 수직 슬라이스 구현] --> C2[리팩터링으로 verbose 감소]
    C2 --> C3[수동 E2E와 스모크 검증]
  end

  subgraph D[운영성 있는 개발]
    D1[작은 수정은 triage-issue]
    D2[병렬 작업은 git worktree]
  end

  A3 --> B1
  A2 -. 개발 보조 .-> B2
  A3 -. 용어 정렬 .-> B2
  B1 --> C1
  B2 -. 구현 가속 .-> C1
  C3 --> D1
  D1 --> D2
  C3 -. 실패 시 다시 고정 .-> B1

  classDef discovery fill:#eef6ff,stroke:#2457a6,stroke-width:2px,color:#16325c;
  classDef prep fill:#eefaf1,stroke:#2b7a46,stroke-width:2px,color:#184d2c;
  classDef build fill:#fff4e8,stroke:#b86a12,stroke-width:2px,color:#6b3a00;
  classDef ops fill:#fff0f3,stroke:#b2385a,stroke-width:2px,color:#741b36;
  classDef subgroup fill:#f8f9fb,stroke:#98a2b3,stroke-width:1px,color:#344054;

  class A1,A2,A3 discovery;
  class B1,B2 prep;
  class C1,C2,C3 build;
  class D1,D2 ops;
  class A,B,C,D subgroup;
```

## 구현 범위

현재 저장소는 다음 두 축으로 구성된다.

1. LG 홈스타일 공개 웹 페이지를 대상으로 한 크롤링 및 인덱싱 파이프라인
2. 검색 결과를 근거로만 답변하는 Microsoft Agent Framework 기반 QA 런타임

크롤링 구현 내용은 별도 문서로 정리했다.

- [구현된 크롤링 프로젝트 문서](./docs/crawling-project.md)

## 핵심 산출물

- [PRD.md](./PRD.md): 문제 정의, 운영 경계, 인덱싱/에이전트 결정 사항
- [UBIQUITOUS_LANGUAGE.md](./UBIQUITOUS_LANGUAGE.md): 팀 내 용어를 고정한 문서
- [scripts/README.md](./scripts/README.md): 수동 E2E 검증 스크립트 설명

## 저장소 구조

```text
src/
  homestyle_ingestion/
    application/      # discovery, ingestion, extraction orchestration
    domain/           # crawling, extraction, review queue 도메인 모델
    infrastructure/   # fetch, rendering, indexing, storage 구현
  homestyle_agent/
    application/      # grounded query orchestration
    infrastructure/   # Microsoft Agent Framework 런타임 및 retrieval 연결
  homestyle_shared/
    infrastructure/   # Azure Identity, OpenAI, observability, settings
tests/
  application/        # 유스케이스/파이프라인 테스트
  infrastructure/     # 외부 경계 어댑터 테스트
config/
  discovery.toml      # 크롤 대상 설정
```

이 구조는 단순한 폴더 분리가 아니라 DDD 개념을 코드 수준에 반영하려는 의도를 담고 있다. 도메인 규칙은 `domain`에, 유스케이스 조합은 `application`에, Azure/Playwright/Search 같은 외부 기술 의존성은 `infrastructure`에 두어 변경의 locality를 높이려 했다.

## 사용한 스킬과 도구

- `to-prd`: 인터뷰 결과를 PRD로 정리하는 시작점
- `ubiquitous-language`: 도메인 용어를 팀 공용 언어로 고정
- `improve-codebase-architecture`: DDD 개념이 드러나는 seam과 모듈 경계를 더 분명하게 다듬는 데 참고
- `tdd`: 테스트 우선 흐름 유지
- `triage-issue`: 단순 수정과 문제 분류를 빠르게 처리
- `using-git-worktrees`: 병렬 개발 분리
- `azure-ai`: Azure OpenAI, Azure AI Search 관련 구현 판단 지원
- `microsoft-agent-framework`: Agent Framework 기반 런타임 구현 지원

아키텍처 결정 기록을 더 명시적으로 남기기 위해 Architecture Decision Record 기반 스킬 도입도 검토 중이다. 다만 현재 저장소는 ADR을 단일 필수 흐름으로 강제하지는 않고, PRD와 유비쿼터스 언어 중심의 작업 방식을 우선하고 있다.

## 빠른 시작

```bash
uv sync --group dev
uv run playwright install chromium
uv run pytest
```

수동 크롤/인덱싱 검증은 아래 문서를 참고하면 된다.

- [scripts/README.md](./scripts/README.md)

## 현재 프로젝트 원칙

- 공개 HTML만 수집한다.
- 한국어(`ko`) 범위를 우선한다.
- 검색과 응답은 근거 중심으로 제한한다.
- 근거가 없으면 모른다고 답한다.
- 구현 변경은 가능한 한 테스트로 먼저 고정한다.
- 과한 추상화보다 명시적인 구조를 우선한다.

## 왜 README를 이렇게 구성했는가

이 저장소의 가치는 단순히 “크롤러 하나 만들기”에 있지 않다. 인터뷰, PRD, 유비쿼터스 언어, TDD, triage, worktree, Azure AI, Agent Framework를 하나의 실전 개발 하네스로 엮어, 기능 구현보다 재현 가능한 개발 과정 자체를 남기는 데 의미가 있다.