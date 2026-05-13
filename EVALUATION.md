# 평가 가이드

이 문서는 이 저장소의 평가 파이프라인이 어떻게 동작하는지, 로컬에서 어떻게 실행하는지, 그리고 결과를 Azure AI Foundry 프로젝트 및 Aspire Dashboard로 어떻게 전송하는지를 정리합니다.

## 1. 범위

평가 워크플로우는 아래 스크립트로 구현되어 있습니다.
- scripts/evaluate_ask_grounded_qa.py

핵심 목적:
- 실행 중인 /ask 엔드포인트를 기준으로 grounded QA 평가 데이터셋 생성
- Azure AI Evaluation evaluator 실행
- 결과 아티팩트 로컬 저장
- 필요 시 새 Azure AI Foundry 포털에 cloud evaluation run 생성
- 필요 시 Application Insights에 저장된 운영 trace를 Foundry trace evaluation으로 평가
- Aspire Dashboard 같은 OTLP 백엔드로 요약 telemetry 전송

## 2. 동작 메커니즘

전체 흐름:
1. .env와 프로세스 환경 변수를 로드
2. tests/e2e/observability_questions.json(또는 사용자 지정 파일)에서 질문 로드
3. 각 질문에 대해 Azure AI Search에서 관련 섹션 조회
4. 조회된 섹션으로 context 텍스트 생성
5. /ask 엔드포인트 호출 후 응답 수집
6. 데이터셋 JSONL 저장
7. Azure AI Evaluation evaluator 실행
8. 평가 결과 JSON 저장
9. 평가 요약 span/log telemetry 전송
10. Foundry 프로젝트 endpoint가 설정되어 있으면 기본적으로 cloud dataset evaluation run 생성

참고:
- 기본 Foundry 업로드 방식은 새 포털에서 보이는 cloud evaluation입니다.
- 이전 classic 포털 호환 업로드가 필요하면 `--foundry-upload-mode classic`을 명시합니다.

## 3. 생성 아티팩트

기본 출력 디렉터리:
- .eval/grounded-qa

생성 파일:
- ask_grounded_qa_dataset.jsonl
- ask_grounded_qa_results.json

Telemetry 신호명:
- Span: homestyle.eval.grounded_qa
- Log event: grounded_qa_evaluation_completed

## 4. Evaluator 구성

기본 evaluator:
- groundedness
- relevance
- coherence
- fluency

선택 evaluator:
- similarity

CLI 예시:
- --evaluators groundedness relevance coherence fluency similarity

## 5. 환경 변수

### 5.1 런타임/검색 기본 변수
retrieval과 /ask 연동에 필요:
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_API_VERSION
- AZURE_OPENAI_CHAT_DEPLOYMENT
- AZURE_OPENAI_EMBEDDING_DEPLOYMENT
- AZURE_OPENAI_VISION_DEPLOYMENT
- AZURE_SEARCH_ENDPOINT
- AZURE_SEARCH_INDEX_NAME

선택:
- AZURE_SEARCH_ADMIN_KEY
- USE_DEVELOPER_CREDENTIALS
- AZURE_TENANT_ID
- MANAGED_IDENTITY_CLIENT_ID
- HOMESTYLE_AGENT_BEARER_TOKEN

### 5.2 평가 모델 선택
권장 선택 변수:
- AZURE_AI_EVALUATION_OPENAI_DEPLOYMENT
  - evaluator(judge) 모델 배포명을 강제로 지정
  - 예: gpt-4.1

API key 기반 evaluator 인증(선택):
- AZURE_AI_EVALUATION_OPENAI_API_KEY
- AZURE_OPENAI_API_KEY

추론 모델 힌트(선택):
- AZURE_AI_EVALUATION_REASONING_MODEL

### 5.3 Azure AI Foundry 업로드
Foundry 평가 업로드를 켜려면 아래 중 하나를 설정:
- AZURE_AI_PROJECT_ENDPOINT
- AZURE_AI_PROJECT_URL
- AZURE_AI_FOUNDRY_PROJECT_ENDPOINT

예시:
- AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>

중요:
- Foundry 업로드는 Azure identity 토큰 인증을 사용합니다.
- AZURE_TENANT_ID는 Foundry 프로젝트 리소스의 tenant와 일치해야 합니다.
- 기본 업로드는 `azure-ai-projects`의 cloud dataset evaluation run을 생성합니다.
- `--foundry-upload-mode classic` 또는 `both`를 쓰면 Azure AI Evaluation classic tracking에도 명시 credential을 전달합니다.
- 그래도 tenant mismatch가 나면 Azure CLI를 대상 tenant로 재로그인해야 합니다.

새 Foundry cloud evaluation 선택 변수:
- AZURE_AI_EVALUATION_DATASET_NAME
- AZURE_AI_EVALUATION_DATASET_VERSION
- AZURE_AI_EVALUATION_RUN_NAME

운영 trace evaluation 선택 변수:
- ENABLE_FOUNDRY_TRACE_EVALUATION
  - `/ask` 요청 경로에서 Foundry trace evaluation용 GenAI semantic span을 내보낼지 결정합니다.
  - query/response 원문이 Application Insights trace 속성에 포함될 수 있으므로 기본값은 false입니다.
- AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING
  - Azure Monitor exporter가 GenAI trace 속성을 전송하도록 켭니다.
  - 운영 trace evaluation을 실행하려면 `ENABLE_FOUNDRY_TRACE_EVALUATION=true`와 함께 true로 둡니다.
- AZURE_AI_EVALUATION_TRACE_AGENT_ID
  - trace span의 `gen_ai.agent.id` 값입니다. 예: `homestyle-agent:1`
- AZURE_AI_EVALUATION_TRACE_LOOKBACK_HOURS
- AZURE_AI_EVALUATION_TRACE_MAX_TRACES

### 5.4 Aspire/OTLP Telemetry
Aspire 또는 기타 OTLP 백엔드 전송:
- ENABLE_INSTRUMENTATION=true
- OTEL_SERVICE_NAME=homestyle-agent
- OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:18889

선택:
- OTEL_RESOURCE_ATTRIBUTES
- OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
- OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
- OTEL_EXPORTER_OTLP_LOGS_ENDPOINT

## 6. CLI 사용법

기본 실행:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py
```

주요 옵션:
- --questions <path>
- --ask-endpoint <url>
- --output-dir <path>
- --timeout-seconds <float>
- --max-context-chars <int>
- --evaluators <list>
- --skip-evaluate
- --reuse-dataset
- --foundry-upload-mode cloud|classic|both|disabled
- --foundry-trace-evaluate
- --foundry-trace-only
- --trace-agent-id <agent-id>
- --trace-lookback-hours <int>
- --trace-max-traces <int>
- --trace-evaluators <list>

예시:

데이터셋만 생성:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py --skip-evaluate
```

이미 생성된 데이터셋으로 평가만 실행:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py --reuse-dataset
```

`--reuse-dataset`은 `--output-dir` 아래의 `ask_grounded_qa_dataset.jsonl`을 그대로 사용합니다. 이때 Azure AI Search 조회와 `/ask` 호출, 데이터셋 재작성은 수행하지 않습니다.

similarity 포함 실행:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py --evaluators groundedness relevance coherence fluency similarity
```

기본값이 아닌 /ask endpoint 사용:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py --ask-endpoint http://127.0.0.1:8080/ask
```

## 7. 실행 시나리오

### 7.1 로컬 평가만 실행(Foundry/Aspire 미사용)
1. Foundry endpoint 변수 미설정
2. OTLP exporter 변수 미설정
3. 스크립트 실행

결과:
- 로컬 dataset/result 파일 생성
- Foundry 업로드 없음
- OTLP 전송 없음

### 7.2 평가 + Aspire Dashboard
1. Aspire Dashboard 실행

```bash
docker run --rm -it -d \
  -p 18888:18888 \
  -p 4317:18889 \
  --name aspire-dashboard \
  mcr.microsoft.com/dotnet/aspire-dashboard:latest
```

2. OTLP 환경 변수 설정
3. 평가 스크립트 실행

결과:
- 로컬 결과 파일 생성
- Aspire에서 평가 요약 span/log 확인 가능

### 7.3 평가 + Azure AI Foundry 업로드
1. Foundry endpoint 설정
2. AZURE_TENANT_ID 정합성 확인
3. 필요 시 tenant 재로그인

```bash
az login --tenant <target-tenant-id>
```

4. 평가 스크립트 실행

결과:
- 로컬 결과 파일 생성
- 새 Foundry 포털의 Evaluation에 cloud dataset evaluation run 생성

스크립트는 현재처럼 먼저 `/ask`를 직접 호출해 `query`, `context`, `response`, `ground_truth`가 들어 있는 JSONL을 만든 뒤, 그 JSONL을 Foundry dataset으로 업로드하고 evaluation run을 시작합니다.

동일한 `AZURE_AI_EVALUATION_DATASET_NAME`과 `AZURE_AI_EVALUATION_DATASET_VERSION`이 이미 Foundry에 있으면, 기존 dataset version을 삭제한 뒤 현재 JSONL을 다시 업로드합니다.

이전 classic 포털에도 남기려면:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py --foundry-upload-mode both
```

Foundry 업로드를 끄려면:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py --foundry-upload-mode disabled
```

### 7.5 운영 trace evaluation
운영 트래픽은 요청을 재실행하지 않고 Application Insights에 저장된 trace를 Foundry cloud evaluation으로 평가합니다.

전제 조건:
- Foundry 프로젝트에 Application Insights가 연결되어 있어야 합니다.
- 프로젝트 managed identity가 Application Insights와 연결된 Log Analytics workspace에 Log Analytics Reader 권한을 가져야 합니다.
- 운영 서버에서 `ENABLE_FOUNDRY_TRACE_EVALUATION=true`를 명시해야 `/ask` trace에 평가용 payload가 포함됩니다.
- Azure Monitor exporter가 GenAI 속성을 전송하도록 `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`도 설정합니다.
- 평가 대상 trace에는 GenAI semantic convention 속성이 있어야 합니다.
  - `gen_ai.operation.name=invoke_agent`
  - `gen_ai.agent.id=<agent-id>`
  - `gen_ai.input.messages`
  - `gen_ai.output.messages`

최근 trace만 평가:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py \
  --foundry-trace-only \
  --trace-agent-id homestyle-agent:1 \
  --trace-lookback-hours 6 \
  --trace-max-traces 25
```

데이터셋 평가 후 trace evaluation도 같이 시작:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py \
  --foundry-trace-evaluate \
  --trace-agent-id homestyle-agent:1
```

기본 trace evaluator:
- relevance
- coherence
- fluency

추가 선택:
- intent_resolution

### 7.4 평가 + Foundry + Aspire 동시 사용
Foundry endpoint와 OTLP 설정을 동시에 켜면 됩니다.

결과:
- 로컬 아티팩트 생성
- Foundry 업로드
- Aspire telemetry 확인

## 8. 트러블슈팅

### Tenant provided in token does not match resource token
의미:
- 업로드에 사용된 토큰의 tenant와 Foundry 리소스 tenant가 다릅니다.

확인 순서:
1. AZURE_AI_PROJECT_ENDPOINT가 맞는 프로젝트를 가리키는지 확인
2. AZURE_TENANT_ID가 대상 tenant인지 확인
3. az account show로 현재 tenant/subscription 확인
4. 필요 시 az login --tenant <target-tenant-id> 재실행
5. 평가 스크립트 재실행

참고:
- 이 문제는 API 서버 재시작으로 해결되지 않습니다.
- evaluate 스크립트는 실행할 때마다 별도 프로세스로 시작됩니다.

### Install azure-ai-evaluation before running evaluation
- 현재 가상환경에 의존성이 없다는 의미입니다. 의존성 설치 후 재실행하세요.

### Aspire에 telemetry가 보이지 않음
1. Aspire 컨테이너 실행 여부 확인
2. OTEL_EXPORTER_OTLP_ENDPOINT 도달 가능 여부 확인
3. ENABLE_INSTRUMENTATION=true 확인
4. 평가 단계까지 정상 완료됐는지 확인

### 새 Foundry 포털에 평가 결과가 보이지 않음
1. `--foundry-upload-mode`가 `cloud` 또는 `both`인지 확인
2. AZURE_AI_PROJECT_ENDPOINT가 새 Foundry project endpoint인지 확인
3. 계정에 Azure AI User 역할이 있는지 확인
4. 출력된 Foundry report URL 또는 run ID로 run 상태 확인
5. `classic` 모드는 classic 포털 호환 업로드이므로 새 포털 Evaluation 목록에 보이지 않을 수 있습니다.

### Trace evaluation 결과가 비어 있거나 score=None임
1. Application Insights가 Foundry 프로젝트에 연결되어 있는지 확인
2. `AZURE_AI_EVALUATION_TRACE_AGENT_ID`가 trace의 `gen_ai.agent.id`와 일치하는지 확인
3. lookback 시간 안에 trace가 있는지 확인
4. trace span에 `gen_ai.operation.name=invoke_agent`, `gen_ai.input.messages`, `gen_ai.output.messages`가 있는지 확인

## 9. 보안 및 데이터 취급

- 평가 dataset row에는 query/response/context 원문이 포함될 수 있습니다.
- 출력 파일은 민감 데이터로 취급하세요.
- 이 스크립트 telemetry는 요약 중심으로 설계되어 있습니다.
- 운영 환경에서는 ENABLE_SENSITIVE_DATA를 기본적으로 비활성화하세요.
- .env의 비밀값은 저장소에 커밋하지 마세요.

## 10. 최소 .env 예시

```dotenv
AZURE_OPENAI_ENDPOINT=https://<resource>.services.ai.azure.com
AZURE_OPENAI_API_VERSION=2024-10-01-preview
AZURE_OPENAI_CHAT_DEPLOYMENT=<chat-deployment>
AZURE_AI_EVALUATION_OPENAI_DEPLOYMENT=gpt-4.1
AZURE_AI_EVALUATION_DATASET_NAME=ask_grounded_qa
AZURE_AI_EVALUATION_DATASET_VERSION=1
AZURE_AI_EVALUATION_RUN_NAME=ask_grounded_qa
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<embedding-deployment>
AZURE_OPENAI_VISION_DEPLOYMENT=<vision-deployment>
AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
AZURE_SEARCH_INDEX_NAME=<index-name>
USE_DEVELOPER_CREDENTIALS=true
AZURE_TENANT_ID=<tenant-id>

# Foundry 업로드(선택)
AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>

# Foundry 운영 trace evaluation(선택)
ENABLE_FOUNDRY_TRACE_EVALUATION=false
AZURE_AI_EVALUATION_TRACE_AGENT_ID=homestyle-agent:1
AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=false
AZURE_AI_EVALUATION_TRACE_LOOKBACK_HOURS=1
AZURE_AI_EVALUATION_TRACE_MAX_TRACES=50

# Aspire telemetry(선택)
ENABLE_INSTRUMENTATION=true
OTEL_SERVICE_NAME=homestyle-agent
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:18889
```

## 11. 관련 문서

- OBSERVABILITY.md
- scripts/README.md
- scripts/evaluate_ask_grounded_qa.py
