# AGENTS

이 저장소는 역할이 분리된 멀티에이전트 워크플로로 작업한다.

## Agent Routing

- 설계 에이전트: Claude Opus 4.6
- 코딩 에이전트: GPT-5.4-high
- 검증 에이전트: Claude Sonnet 4.6

## Agents

- `multi-agent-orchestrator`: 전체 흐름을 조율하고 설계 -> 구현 -> 검증 순서를 강제한다.
- `design-architect`: 요구사항을 정리하고 아키텍처, 구현 단계, 위험 요소를 설계한다. 코드는 작성하지 않는다.
- `coding-agent`: 설계 산출물을 기준으로 코드를 구현하고 필요한 최소 범위만 수정한다.
- `validation-agent`: 구현된 동작을 테스트로 검증한다. 외부 API, 외부 SaaS, 외부 네트워크 호출만 mock 한다.

## Operating Contract

1. 모든 비단순 작업은 먼저 `design-architect`가 설계 문서를 만든다.
2. `coding-agent`는 설계 범위 내에서만 구현한다. 설계와 다른 방향이 필요하면 차이를 명시한다.
3. `validation-agent`는 변경된 동작을 검증하는 테스트를 추가하거나 검증 전략을 정리한다.
4. 검증 단계에서는 외부 API, 외부 SaaS, 외부 네트워크 호출만 mock 한다.
5. 도메인 로직, 내부 모듈, 내부 서비스 간 계약은 가능한 한 실제 구현으로 검증한다.

## Source Of Truth

- 실제 에이전트 정의는 `.github/agents/*.agent.md` 파일들에 있다.
- 자동 감지 도구는 각 `.agent.md` 파일의 YAML frontmatter를 기준으로 agent 이름, 설명, 모델을 읽는다.
- 이 파일은 저장소 차원의 운영 규칙과 에이전트 라우팅 의도를 설명한다.

## Expected Files

- `.github/agents/multi-agent-orchestrator.agent.md`
- `.github/agents/design-architect.agent.md`
- `.github/agents/coding-agent.agent.md`
- `.github/agents/validation-agent.agent.md`

## Notes

- 런타임이 특정 모델 라벨을 지원하지 않으면 `.github/agents/*.agent.md` frontmatter의 `model` 값을 해당 환경이 지원하는 라벨로 맞춘다.
- 이 파일명은 반드시 `AGENTS.md`를 사용한다.