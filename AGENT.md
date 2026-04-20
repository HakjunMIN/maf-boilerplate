# Multi-Agent Build Workflow

이 저장소는 역할이 분리된 멀티에이전트 흐름으로 작업하도록 구성한다.

## Agents

- `multi-agent-orchestrator`: 전체 흐름을 조율한다. 요구사항을 정리하고 설계 -> 구현 -> 검증 순서로 진행시킨다.
- `design-architect`: 앱 아키텍처를 설계하고 구현 계획을 만든다. 코드는 작성하지 않는다.
- `coding-agent`: 설계 산출물을 기준으로 코드를 작성하고 필요한 최소 범위만 수정한다.
- `validation-agent`: 변경사항을 검증하는 테스트를 작성하고 실행 전략을 정리한다. 외부 API만 mock 한다.

## Operating Contract

1. 모든 작업은 먼저 `design-architect`가 요구사항, 아키텍처, 구현 단계, 위험 요소를 정리한다.
2. `coding-agent`는 설계 문서 범위 내에서 코드를 구현한다. 설계와 다른 방향이 필요하면 그 차이를 명시한다.
3. `validation-agent`는 구현된 동작을 검증하는 테스트를 추가한다.
4. 검증 단계에서는 외부 API, 외부 SaaS, 외부 네트워크 호출만 mock 한다.
5. 도메인 로직, 내부 모듈, 내부 서비스 간 계약은 가능한 한 실제 구현을 사용해 검증한다.

## Files

실제 에이전트 정의는 `.github/agents/` 아래의 `.agent.md` 파일들에 있다.

## Model Intent

- 설계 에이전트: Claude Opus 4.6
- 코딩 에이전트: GPT-5.4-high
- 검증 에이전트: GPT-5.4-high

참고: 커스텀 에이전트의 모델 선택은 실행 환경이 지원하는 라벨에 따라 달라질 수 있다. 이 저장소에는 요청한 모델 의도를 반영해 두었고, 런타임이 해당 라벨을 인식하지 않으면 frontmatter의 `model` 값을 환경에 맞는 지원 라벨로 조정하면 된다.