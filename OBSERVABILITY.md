# Observability

이 저장소의 observability 초기화는 `src/homestyle_shared/infrastructure/observability.py`에서 공통으로 처리합니다.
목표는 다음과 같습니다.

- 기본적으로 구조화된 JSON 애플리케이션 로그를 출력한다.
- OTLP 백엔드가 설정되면 Microsoft Agent Framework telemetry를 활성화한다.
- `APPLICATION_INSIGHTS_CONNECTION_STRING`이 설정되면 Azure Monitor / Application Insights를 활성화한다.
- 민감한 에이전트 payload 수집은 기본적으로 비활성화한다.

이 문서는 이 저장소에 새 에이전트, CLI, 워커를 추가할 때 observability를 동일한 방식으로 붙이기 위한 기준 문서입니다.

## 현재 구현

### 공통 진입점

프로세스 시작 시점에 `configure_process_observability(...)`를 한 번 호출합니다.

현재 적용 위치:

- `src/homestyle_agent/infrastructure/runtime.py`
- `src/homestyle_ingestion/manual_crawl_cli.py`
- `scripts/sample_vlm_index.py`

### `configure_process_observability(...)`가 하는 일

1. Python logging을 stdout으로 설정합니다.
2. `structlog`를 JSON 로그 출력으로 설정합니다.
3. 로드된 환경값에서 `OTEL_*`, `ENABLE_*` observability 변수를 프로세스 환경 변수로 복사합니다. 이 함수는 프로세스 전역 observability bootstrap이므로 이 부작용을 의도적으로 포함합니다.
4. telemetry 백엔드 경로를 정확히 하나만 선택합니다.
    - **Application Insights 경로**: `azure.monitor.opentelemetry.configure_azure_monitor(...)`를 호출한 뒤 `ENABLE_SENSITIVE_DATA` 값을 반영해 Agent Framework instrumentation을 켭니다.
    - **OTLP 경로**: `agent_framework.observability.configure_otel_providers()`를 호출한 뒤 애플리케이션 로그용 OpenTelemetry logging handler를 붙입니다.
    - **백엔드 미설정**: JSON 로그만 유지합니다.
5. 혼합 설정을 거부합니다. `APPLICATION_INSIGHTS_CONNECTION_STRING`과 OTLP exporter 변수는 함께 사용할 수 없습니다.

### 로그 동작

애플리케이션 로그는 아래 헬퍼로 구조화 JSON 로그를 생성합니다.

- `build_logger(name)`
- `bind_correlation_id(logger, correlation_id=None)`

현재 runtime은 요청 단위 로그에 correlation ID를 바인딩해서 trace와 로그를 함께 추적하기 쉽게 합니다.

## 백엔드 선택 규칙

### 1. Application Insights

Azure Monitor / Application Insights를 telemetry 백엔드로 쓸 때 사용합니다.

필수 설정:

```dotenv
APPLICATION_INSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=...
```

동작:

- Azure Monitor OpenTelemetry 파이프라인을 구성합니다.
- Agent Framework instrumentation을 활성화합니다.
- 민감한 데이터 수집은 기본적으로 꺼진 상태를 유지합니다. 로컬/테스트에서 `ENABLE_SENSITIVE_DATA=true`를 명시한 경우에만 Agent Framework의 prompt, completion 등 민감 payload 수집을 허용합니다.
- OTLP exporter 변수는 모두 비워야 합니다.

### 2. OTLP 백엔드

Aspire Dashboard 또는 OTLP 호환 백엔드를 사용할 때 사용합니다.

아래 변수 중 하나 이상이 설정되어 있어야 합니다.

- `OTEL_EXPORTER_OTLP_ENDPOINT`
- `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`
- `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`
- `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`

최소 설정 예시:

```dotenv
ENABLE_INSTRUMENTATION=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

동작:

- Agent Framework가 OTEL provider를 구성합니다.
- 애플리케이션 로그를 OTEL logger provider로 전달합니다.
- 내부 OpenTelemetry / gRPC exporter 로그는 애플리케이션 telemetry 스트림에서 제외합니다.

### 3. 로그만 사용

Application Insights와 OTLP가 모두 설정되지 않더라도 애플리케이션은 stdout으로 구조화 JSON 로그를 출력합니다.

telemetry 백엔드가 없는 로컬 개발 기본값으로 안전한 구성입니다.

## 환경 변수

### 저장소에서 사용하는 observability 변수

현재 공통 bootstrap이 인식하고 전달하는 변수는 다음과 같습니다.

```dotenv
LOG_LEVEL=INFO

APPLICATION_INSIGHTS_CONNECTION_STRING=

ENABLE_INSTRUMENTATION=true
ENABLE_CONSOLE_EXPORTERS=false
ENABLE_SENSITIVE_DATA=false

OTEL_SERVICE_NAME=homestyle-agent
OTEL_SERVICE_VERSION=0.1.0
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=local

OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_EXPORTER_OTLP_TRACES_ENDPOINT=
OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=
OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=
OTEL_EXPORTER_OTLP_PROTOCOL=
OTEL_EXPORTER_OTLP_HEADERS=
```

주의:

- 모든 `OTEL_*` 및 `ENABLE_*` observability 변수는 Agent Framework OTEL 설정 전에 프로세스 환경 변수로 전달됩니다.
- `ENABLE_SENSITIVE_DATA`는 명시적인 로컬/테스트 opt-in 용도로만 둡니다. Application Insights 경로에서는 `1`, `true`, `yes`, `on` 값을 `enable_sensitive_data=True`로 반영하고, 그 외 값은 비활성으로 처리합니다.
- `APPLICATION_INSIGHTS_CONNECTION_STRING`과 OTLP exporter 변수는 함께 설정하지 마세요.

## 새 에이전트에서의 startup 패턴

새 에이전트, CLI, 워커, HTTP 엔트리포인트는 runtime, client, tool, workflow를 만들기 전에 observability를 초기화해야 합니다.

### 권장 bootstrap

```python
import os

from homestyle_shared.infrastructure.observability import configure_process_observability


def main() -> None:
    configure_process_observability(
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        application_insights_connection_string=os.environ.get(
            "APPLICATION_INSIGHTS_CONNECTION_STRING"
        ),
    )
    # 여기서 runtime, tool, workflow를 생성하고 실행한다.
```

### 엔트리포인트가 병합된 환경값을 이미 로드하는 경우

엔트리포인트가 `load_environment(...)`를 쓰고 있다면 `.env`에서 읽은 OTEL 값이 유지되도록 그 mapping을 runtime까지 전달합니다.

```python
from homestyle_agent.infrastructure.runtime import AzureRagRuntime
from homestyle_shared.infrastructure.settings import AzureRagSettings, load_environment


values = load_environment()
settings = AzureRagSettings.from_env(values)
runtime = AzureRagRuntime(settings, observability_environment=values)
```

이 패턴은 현재 `src/homestyle_agent/api/server.py`에서 사용 중입니다.

## 구성 샘플

### 로컬 Aspire Dashboard

Aspire Dashboard 실행:

```bash
docker run --rm -it -d \
  -p 18888:18888 \
  -p 4317:18889 \
  --name aspire-dashboard \
  mcr.microsoft.com/dotnet/aspire-dashboard:latest
```

로컬 환경 변수 예시:

```dotenv
LOG_LEVEL=INFO
ENABLE_INSTRUMENTATION=true
OTEL_SERVICE_NAME=homestyle-agent
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=local,service.namespace=homestyle
OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:18889
```

grounded QA 평가 결과도 같은 OTLP 설정을 사용합니다. 평가 스크립트는 결과 파일을 그대로 유지하면서 summary metric만 `homestyle.eval.grounded_qa` span과 `grounded_qa_evaluation_completed` log로 내보냅니다.

```bash
uv run python scripts/evaluate_ask_grounded_qa.py
```

Azure AI Foundry project에도 새 포털용 cloud evaluation run을 남기려면 project endpoint를 추가합니다.

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<foundry-project-endpoint>
```

`AZURE_AI_PROJECT_URL` 또는 `AZURE_AI_FOUNDRY_PROJECT_ENDPOINT`도 같은 용도로 사용할 수 있습니다.
평가 스크립트는 기본적으로 `/ask` 응답을 미리 생성한 JSONL을 Foundry dataset으로 올리고 `azure-ai-projects` cloud evaluation run을 시작합니다. 이전 classic 포털 호환 업로드가 필요하면 `--foundry-upload-mode classic` 또는 `both`를 사용합니다. 그래도 tenant mismatch가 나면 Azure CLI 계정이 해당 tenant에 로그인되어 있는지 확인하고 `az login --tenant <tenant-id>`로 다시 로그인합니다.

적합한 경우:

- 로컬 개발 중일 때
- 에이전트 실행의 trace, log, metric을 직접 확인하고 싶을 때
- grounded QA eval metric을 Aspire Dashboard에서 확인하고 싶을 때
- Azure Monitor 없이 tool span, model call을 검증하고 싶을 때

### Foundry trace evaluation

운영 트래픽은 요청을 재실행하지 않고 Application Insights에 저장된 trace를 Foundry cloud evaluation으로 평가할 수 있습니다.

```dotenv
AZURE_AI_PROJECT_ENDPOINT=https://<foundry-project-endpoint>
APPLICATION_INSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=...
ENABLE_FOUNDRY_TRACE_EVALUATION=true
AZURE_AI_EVALUATION_TRACE_AGENT_ID=homestyle-agent:1
AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true
AZURE_AI_EVALUATION_TRACE_LOOKBACK_HOURS=1
AZURE_AI_EVALUATION_TRACE_MAX_TRACES=50
```

```bash
uv run python scripts/evaluate_ask_grounded_qa.py --foundry-trace-only
```

Foundry trace evaluation은 Application Insights에 `gen_ai.operation.name=invoke_agent`, `gen_ai.agent.id`, `gen_ai.input.messages`, `gen_ai.output.messages`가 있는 trace를 대상으로 합니다. 현재 저장소의 일반 summary eval telemetry와는 별개입니다. `/ask` 경로는 `ENABLE_FOUNDRY_TRACE_EVALUATION=true`일 때만 query/response 원문을 GenAI semantic convention 속성으로 내보냅니다. Azure Monitor exporter가 이 GenAI 속성을 전송하도록 `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true`도 함께 설정합니다.

### Console exporter만 사용

collector 없이 로컬에서 OTEL 출력을 보고 싶다면 아래처럼 설정합니다.

```dotenv
LOG_LEVEL=DEBUG
ENABLE_INSTRUMENTATION=true
ENABLE_CONSOLE_EXPORTERS=true
OTEL_SERVICE_NAME=homestyle-agent
```

### Azure Monitor / Application Insights

Azure 환경용 예시:

```dotenv
LOG_LEVEL=INFO
APPLICATION_INSIGHTS_CONNECTION_STRING=InstrumentationKey=...;IngestionEndpoint=...
OTEL_SERVICE_NAME=homestyle-agent
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=prod,service.namespace=homestyle
```

중요:

- Application Insights를 쓸 때는 `OTEL_EXPORTER_OTLP_*` 변수를 모두 제거합니다.
- `ENABLE_SENSITIVE_DATA`는 명시적으로 승인된 로컬/테스트 상황이 아니면 비활성 상태로 유지합니다.

### OTLP HTTP 백엔드 예시

Aspire가 아닌 HTTP OTLP 백엔드를 쓰는 경우:

```dotenv
LOG_LEVEL=INFO
ENABLE_INSTRUMENTATION=true
OTEL_SERVICE_NAME=homestyle-agent
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=https://your-otel-endpoint.example.com
OTEL_EXPORTER_OTLP_HEADERS=authorization=Bearer <token>
```

헤더나 토큰은 소스 코드에 하드코딩하지 마세요.

## 로그 사용 패턴

임의의 logging 설정 대신 공통 logger 헬퍼를 사용합니다.

```python
from homestyle_shared.infrastructure.observability import bind_correlation_id, build_logger


logger = build_logger("my_agent")
run_logger, correlation_id = bind_correlation_id(logger)
run_logger.info("my_agent_started", task="sample")
```

가이드:

- `grounded_answer_started`처럼 안정적인 event 이름을 사용합니다.
- 민감하지 않은 dimension만 기록합니다.
- raw prompt나 사용자 원문 대신 길이, 개수, 상태값, 리소스 이름을 우선 기록합니다.

## 검증 체크리스트

새 에이전트나 워커에 observability를 연결할 때 확인할 항목:

1. `configure_process_observability(...)`가 startup에서 한 번만 호출되는지 확인합니다.
2. JSON 로그가 stdout에 계속 출력되는지 확인합니다.
3. 백엔드 경로가 하나만 활성화되어 있는지 확인합니다.
   - Application Insights 또는
   - OTLP
4. 선택한 백엔드에 trace, log, metric이 도착하는지 확인합니다.
5. 애플리케이션 로그에 correlation ID가 포함되는지 확인합니다.
6. prompt, completion 등 민감한 payload가 기본값으로 export되지 않는지 확인합니다.

## 트러블슈팅

### Aspire 또는 다른 OTLP 백엔드에 telemetry가 보이지 않는 경우

다음을 확인합니다.

- `ENABLE_INSTRUMENTATION=true`
- OTLP endpoint 변수가 실제로 하나 이상 설정되어 있는지
- agent/runtime 생성 전에 `configure_process_observability(...)`가 호출되었는지

### `APPLICATION_INSIGHTS_CONNECTION_STRING` 관련 `ValueError`가 발생하는 경우

Application Insights와 OTLP exporter 설정이 동시에 켜진 상태입니다.
둘 중 하나만 남기고 나머지는 제거하세요.

### 로그는 나오는데 trace가 없는 경우

대개 telemetry 백엔드가 설정되지 않았거나, startup 시점에 OTEL 환경 변수가 보이지 않은 경우입니다.

### exporter 내부 로그가 중복되거나 너무 시끄러운 경우

공통 OTEL logging handler는 이미 `opentelemetry.*`, `grpc*` 내부 로그를 애플리케이션 telemetry에서 제외합니다.
별도의 root OTEL logging handler를 추가하지 말고 공통 bootstrap을 재사용하세요.

