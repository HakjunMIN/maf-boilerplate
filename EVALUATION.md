# 평가 가이드

이 문서는 이 저장소의 평가 파이프라인이 어떻게 동작하는지, 로컬에서 어떻게 실행하는지, 그리고 결과를 Azure AI Foundry 프로젝트 및 Aspire Dashboard로 어떻게 전송하는지를 정리합니다.

## 1. 범위

평가 워크플로우는 아래 스크립트로 구현되어 있습니다.
- scripts/evaluate_ask_grounded_qa.py

핵심 목적:
- 실행 중인 /ask 엔드포인트를 기준으로 grounded QA 평가 데이터셋 생성
- Azure AI Evaluation evaluator 실행
- 결과 아티팩트 로컬 저장
- 필요 시 Azure AI Foundry 프로젝트로 평가 결과 업로드
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
10. Foundry 프로젝트 endpoint가 설정되어 있으면 평가 run 업로드

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
- 스크립트는 업로드 단계에서 Azure AI Evaluation에 명시 credential을 전달합니다.
- 그래도 tenant mismatch가 나면 Azure CLI를 대상 tenant로 재로그인해야 합니다.

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

예시:

데이터셋만 생성:

```bash
uv run python scripts/evaluate_ask_grounded_qa.py --skip-evaluate
```

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
- Foundry 프로젝트에 평가 run 업로드

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
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<embedding-deployment>
AZURE_OPENAI_VISION_DEPLOYMENT=<vision-deployment>
AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
AZURE_SEARCH_INDEX_NAME=<index-name>
USE_DEVELOPER_CREDENTIALS=true
AZURE_TENANT_ID=<tenant-id>

# Foundry 업로드(선택)
AZURE_AI_PROJECT_ENDPOINT=https://<resource>.services.ai.azure.com/api/projects/<project>

# Aspire telemetry(선택)
ENABLE_INSTRUMENTATION=true
OTEL_SERVICE_NAME=homestyle-agent
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:18889
```

## 11. 관련 문서

- OBSERVABILITY.md
- scripts/README.md
- scripts/evaluate_ask_grounded_qa.py
