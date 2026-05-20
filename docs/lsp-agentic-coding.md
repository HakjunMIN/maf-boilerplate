# Python LSP 기반 에이전틱 코딩 환경

이 저장소는 `src` 레이아웃과 `uv` 가상환경을 사용한다. grep 기반 탐색만으로는 심볼의 정의, 참조, 타입 흐름을 정확히 따라가기 어렵기 때문에 VS Code Python/Pylance LSP와 Ruff language server를 기본 개발 환경으로 둔다.

## 구성 파일

- `.vscode/settings.json`: VS Code가 이 워크스페이스에서 Pylance, pytest, Ruff를 같은 기준으로 실행하도록 고정한다.
- `.vscode/extensions.json`: Python, Pylance, Ruff 확장을 추천한다.
- `pyrightconfig.json`: Pylance/Pyright가 `src`, `tests`, `scripts`를 분석하고 `src`를 import 경로로 인식하도록 한다.
- `pyproject.toml`: Ruff, Mypy, pytest의 CLI 기준을 유지한다. LSP는 빠른 피드백용이고 CI 성격의 검증은 기존 CLI 도구가 담당한다.

## 로컬 준비

```bash
uv sync --group dev
```

VS Code에서 권장 확장을 설치한 뒤 Python 인터프리터가 `.venv/bin/python`으로 잡혔는지 확인한다. 워크스페이스 설정은 기본값을 이미 지정하므로 보통 별도 선택 없이 동작한다.

## 에이전틱 코딩에서의 이점

LSP는 코드 탐색을 텍스트 검색에서 의미 기반 탐색으로 바꾼다.

- 토큰 절감: 파일 전체를 읽기 전에 `go to definition`, `find references`, symbol rename 결과로 필요한 위치만 좁힌다.
- 오탐 감소: 같은 문자열을 가진 다른 함수, 테스트 fixture, 문서가 섞이는 grep 문제를 줄인다.
- 변경 영향 파악: 공개 함수나 도메인 모델을 고치기 전에 실제 참조 목록을 확인해 수정 범위를 작게 유지한다.
- 타입 기반 피드백: import 경로, Optional 처리, 잘못된 attribute 접근을 실행 전 editor diagnostics로 빠르게 잡는다.
- 안전한 리네임: 심볼 단위 rename으로 문자열 치환보다 테스트/문서/다른 이름 충돌 위험이 낮다.

## 권장 활용 방식

1. 새 작업을 시작하면 grep보다 먼저 관련 진입점의 심볼 참조를 확인한다.
2. 구현 파일을 읽을 때는 파일 전체를 읽기보다 class/function 정의와 참조 위치를 우선 본다.
3. 변경 전에는 수정하려는 public method, dataclass, protocol 역할의 객체에 대해 references를 확인한다.
4. 이름 변경은 가능한 한 LSP rename을 사용하고, 설정 파일이나 문서 문자열처럼 LSP가 다루지 않는 곳만 별도 검색한다.
5. LSP diagnostics로 빠른 오류를 정리한 뒤 `uv run ruff check .`, `uv run mypy src`, 필요한 `uv run pytest --no-cov ...`로 최종 검증한다.

## 효과 측정

`scripts/measure_lsp_context_impact.py`는 grep식 전체 파일 컨텍스트와 LSP reference 컨텍스트를 같은 추정식으로 비교한다. 실제 LSP 사용 결과는 VS Code의 symbol references 출력 또는 에이전트의 `vscode_listCodeUsages` 결과를 텍스트 파일로 저장해 입력한다.

```bash
uv run python scripts/measure_lsp_context_impact.py DiscoveredUrl \
	--lsp-usages-file /path/to/discovered-url-usages.txt
```

출력값은 `grep_tokens`, `lsp_tokens`, `token_reduction_percent`, `scanned_lines`, `focus_lines`, `focus_multiplier`를 포함한다. `token_reduction_percent`는 전체 파일을 읽는 방식 대비 줄어든 추정 토큰 비율이고, `focus_multiplier`는 에이전트가 훑어야 하는 전체 라인 수가 LSP가 지목한 라인 수보다 몇 배 큰지를 뜻한다.

## 이 저장소에서 특히 유용한 지점

- `homestyle_ingestion.application`에서 use case orchestration이 여러 도메인 객체와 인프라 어댑터를 연결하므로 references 기반 탐색이 효과적이다.
- `homestyle_ingestion.domain`의 dataclass와 value object는 타입 흐름을 따라가면 변경 범위가 빨리 드러난다.
- `homestyle_agent.infrastructure`는 Azure Search, Microsoft Agent Framework 같은 외부 SDK 경계가 있어, import 오류와 attribute 접근 진단이 빠른 피드백을 준다.
- 테스트가 `tests/application`과 `tests/infrastructure`로 나뉘어 있어, 변경 심볼의 references를 보면 어떤 테스트 계층을 먼저 볼지 정하기 쉽다.

## 역할 분담

LSP 설정은 개발 중 탐색과 빠른 피드백을 위한 것이다. 최종 품질 기준은 기존 프로젝트 명령을 따른다.

```bash
uv run ruff check .
uv run mypy src
uv run pytest --no-cov <selected tests>
```

전체 회귀가 필요하면 README의 빠른 시작처럼 `uv run pytest`를 사용한다. 다만 커버리지 게이트가 켜져 있으므로 좁은 변경 검증에는 `--no-cov`를 붙인 선택 테스트가 더 적합하다.
