import importlib.util
import asyncio
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace

from homestyle_shared.domain.indexing import SectionDocument


def load_script() -> ModuleType:
    path = Path("scripts/evaluate_ask_grounded_qa.py")
    spec = importlib.util.spec_from_file_location("evaluate_ask_grounded_qa", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_questions_reads_observability_shape(tmp_path: Path) -> None:
    script = load_script()
    questions_path = tmp_path / "questions.json"
    questions_path.write_text(
        '{"endpoint":"http://127.0.0.1:8080/ask",'
        '"questions":[{"id":"obs-001","question":"질문"}]}',
        encoding="utf-8",
    )

    questions, endpoint = script.load_questions(questions_path)

    assert endpoint == "http://127.0.0.1:8080/ask"
    assert questions == [script.EvalQuestion(id="obs-001", query="질문")]


def test_build_context_preserves_source_metadata_and_caps_content() -> None:
    script = load_script()
    section = SectionDocument(
        chunk_id="chunk-1",
        page_url="https://homestyle.lge.co.kr/item?productId=1",
        locale="ko",
        title="상품명",
        breadcrumb=("홈", "상품"),
        section_heading="소재",
        content="가" * 2_500,
        confidence_score=0.95,
        reviewer_approved=True,
    )

    context = script.build_context([section], max_context_chars=12_000)

    assert "title: 상품명" in context
    assert "heading: 소재" in context
    assert "breadcrumb: 홈 > 상품" in context
    assert "url: https://homestyle.lge.co.kr/item?productId=1" in context
    assert context.count("가") == 2_000


def test_build_ask_headers_uses_bearer_token_without_logging_value() -> None:
    script = load_script()

    headers = script.build_ask_headers({"HOMESTYLE_AGENT_BEARER_TOKEN": " token-value "})

    assert headers == {"Authorization": "Bearer token-value"}


def test_read_evaluation_api_key_prefers_dedicated_eval_key() -> None:
    script = load_script()

    api_key = script.read_evaluation_api_key(
        {
            "AZURE_AI_EVALUATION_OPENAI_API_KEY": " eval-key ",
            "AZURE_OPENAI_API_KEY": "chat-key",
        }
    )

    assert api_key == "eval-key"


def test_read_evaluation_api_key_falls_back_to_openai_key() -> None:
    script = load_script()

    api_key = script.read_evaluation_api_key({"AZURE_OPENAI_API_KEY": " chat-key "})

    assert api_key == "chat-key"


def test_read_evaluation_deployment_prefers_dedicated_judge_deployment() -> None:
    script = load_script()

    settings = script.AzureRagSettings(
        azure_openai_endpoint="https://openai.example",
        azure_openai_api_version="2024-10-01-preview",
        azure_openai_chat_deployment="gpt-5-chat",
        azure_openai_embedding_deployment="embedding",
        azure_openai_vision_deployment="vision",
        azure_search_endpoint="https://search.example",
        azure_search_index_name="index",
    )

    deployment = script.read_evaluation_deployment(
        {"AZURE_AI_EVALUATION_OPENAI_DEPLOYMENT": " gpt-4o-mini-judge "},
        settings,
    )

    assert deployment == "gpt-4o-mini-judge"


def test_read_azure_ai_project_prefers_project_endpoint() -> None:
    script = load_script()

    project = script.read_azure_ai_project(
        {
            "AZURE_AI_PROJECT_ENDPOINT": " https://foundry.example/projects/project-1 ",
            "AZURE_AI_PROJECT_URL": "https://ignored.example/projects/project-2",
        }
    )

    assert project == "https://foundry.example/projects/project-1"


def test_run_evaluation_uploads_to_foundry_when_project_endpoint_is_configured(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script = load_script()
    captured_kwargs: dict[str, object] = {}
    fake_upload_credential = object()
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.setattr(script, "build_sync_azure_credential", lambda _: fake_upload_credential)

    class FakeModelConfiguration:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeEvaluator:
        def __init__(self, model_config: object, **kwargs: object) -> None:
            self.model_config = model_config
            self.kwargs = kwargs

    def fake_evaluate(**kwargs: object) -> dict[str, object]:
        captured_kwargs.update(kwargs)
        return {"metrics": {"groundedness": 4.0}}

    fake_module = SimpleNamespace(
        AzureOpenAIModelConfiguration=FakeModelConfiguration,
        CoherenceEvaluator=FakeEvaluator,
        FluencyEvaluator=FakeEvaluator,
        GroundednessEvaluator=FakeEvaluator,
        RelevanceEvaluator=FakeEvaluator,
        SimilarityEvaluator=FakeEvaluator,
        evaluate=fake_evaluate,
    )
    monkeypatch.setitem(sys.modules, "azure.ai.evaluation", fake_module)
    settings = script.AzureRagSettings(
        azure_openai_endpoint="https://openai.example",
        azure_openai_api_version="2024-10-01-preview",
        azure_openai_chat_deployment="gpt-4o-mini",
        azure_openai_embedding_deployment="embedding",
        azure_openai_vision_deployment="vision",
        azure_search_endpoint="https://search.example",
        azure_search_index_name="index",
    )

    result = script.run_evaluation(
        dataset_path=tmp_path / "dataset.jsonl",
        results_path=tmp_path / "results.json",
        settings=settings,
        env={
            "AZURE_AI_EVALUATION_OPENAI_API_KEY": "eval-key",
            "AZURE_AI_PROJECT_ENDPOINT": "https://foundry.example/projects/project-1",
            "AZURE_TENANT_ID": "tenant-id",
        },
        evaluator_names=["groundedness"],
        foundry_upload_mode="classic",
    )

    assert result == {"metrics": {"groundedness": 4.0}}
    assert captured_kwargs["evaluation_name"] == "ask_grounded_qa"
    assert captured_kwargs["azure_ai_project"] == "https://foundry.example/projects/project-1"
    assert captured_kwargs["credential"] is fake_upload_credential
    assert captured_kwargs["output_path"] == str(tmp_path / "results.json")
    assert os.environ["AZURE_TENANT_ID"] == "tenant-id"


def test_run_evaluation_does_not_use_classic_foundry_upload_by_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script = load_script()
    captured_kwargs: dict[str, object] = {}

    class FakeModelConfiguration:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeEvaluator:
        def __init__(self, model_config: object, **kwargs: object) -> None:
            self.model_config = model_config
            self.kwargs = kwargs

    def fake_evaluate(**kwargs: object) -> dict[str, object]:
        captured_kwargs.update(kwargs)
        return {"metrics": {}}

    monkeypatch.setitem(
        sys.modules,
        "azure.ai.evaluation",
        SimpleNamespace(
            AzureOpenAIModelConfiguration=FakeModelConfiguration,
            CoherenceEvaluator=FakeEvaluator,
            FluencyEvaluator=FakeEvaluator,
            GroundednessEvaluator=FakeEvaluator,
            RelevanceEvaluator=FakeEvaluator,
            SimilarityEvaluator=FakeEvaluator,
            evaluate=fake_evaluate,
        ),
    )
    settings = script.AzureRagSettings(
        azure_openai_endpoint="https://openai.example",
        azure_openai_api_version="2024-10-01-preview",
        azure_openai_chat_deployment="gpt-4o-mini",
        azure_openai_embedding_deployment="embedding",
        azure_openai_vision_deployment="vision",
        azure_search_endpoint="https://search.example",
        azure_search_index_name="index",
    )

    script.run_evaluation(
        dataset_path=tmp_path / "dataset.jsonl",
        results_path=tmp_path / "results.json",
        settings=settings,
        env={
            "AZURE_AI_EVALUATION_OPENAI_API_KEY": "eval-key",
            "AZURE_AI_PROJECT_ENDPOINT": "https://foundry.example/projects/project-1",
        },
        evaluator_names=["groundedness"],
    )

    assert "azure_ai_project" not in captured_kwargs


def test_run_evaluation_keeps_foundry_upload_disabled_without_project_endpoint(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script = load_script()
    captured_kwargs: dict[str, object] = {}

    class FakeModelConfiguration:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeEvaluator:
        def __init__(self, model_config: object, **kwargs: object) -> None:
            self.model_config = model_config
            self.kwargs = kwargs

    def fake_evaluate(**kwargs: object) -> dict[str, object]:
        captured_kwargs.update(kwargs)
        return {"metrics": {}}

    monkeypatch.setitem(
        sys.modules,
        "azure.ai.evaluation",
        SimpleNamespace(
            AzureOpenAIModelConfiguration=FakeModelConfiguration,
            CoherenceEvaluator=FakeEvaluator,
            FluencyEvaluator=FakeEvaluator,
            GroundednessEvaluator=FakeEvaluator,
            RelevanceEvaluator=FakeEvaluator,
            SimilarityEvaluator=FakeEvaluator,
            evaluate=fake_evaluate,
        ),
    )
    settings = script.AzureRagSettings(
        azure_openai_endpoint="https://openai.example",
        azure_openai_api_version="2024-10-01-preview",
        azure_openai_chat_deployment="gpt-4o-mini",
        azure_openai_embedding_deployment="embedding",
        azure_openai_vision_deployment="vision",
        azure_search_endpoint="https://search.example",
        azure_search_index_name="index",
    )

    script.run_evaluation(
        dataset_path=tmp_path / "dataset.jsonl",
        results_path=tmp_path / "results.json",
        settings=settings,
        env={"AZURE_AI_EVALUATION_OPENAI_API_KEY": "eval-key"},
        evaluator_names=["groundedness"],
    )

    assert "azure_ai_project" not in captured_kwargs


def test_main_reuse_dataset_skips_dataset_generation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script = load_script()
    dataset_path = tmp_path / "ask_grounded_qa_dataset.jsonl"
    dataset_path.write_text(
        '{"id":"q1","query":"질문1","context":"문맥1","ground_truth":"문맥1","response":"답변1"}\n'
        '{"id":"q2","query":"질문2","context":"문맥2","ground_truth":"문맥2","response":"답변2"}\n',
        encoding="utf-8",
    )
    settings = script.AzureRagSettings(
        azure_openai_endpoint="https://openai.example",
        azure_openai_api_version="2024-10-01-preview",
        azure_openai_chat_deployment="gpt-4o-mini",
        azure_openai_embedding_deployment="embedding",
        azure_openai_vision_deployment="vision",
        azure_search_endpoint="https://search.example",
        azure_search_index_name="index",
    )
    captured_evaluation: dict[str, object] = {}
    captured_telemetry: dict[str, object] = {}

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_ask_grounded_qa.py",
            "--output-dir",
            str(tmp_path),
            "--reuse-dataset",
            "--foundry-upload-mode",
            "disabled",
        ],
    )
    monkeypatch.setattr(script, "load_environment", lambda: {})
    monkeypatch.setattr(script.AzureRagSettings, "from_env", lambda _: settings)
    monkeypatch.setattr(script, "configure_process_observability", lambda **_: None)
    monkeypatch.setattr(script, "build_logger", lambda _: object())
    monkeypatch.setattr(script, "load_questions", lambda _: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(script, "build_azure_credential", lambda **_: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(script, "build_eval_rows", lambda **_: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(script, "write_jsonl", lambda *_: (_ for _ in ()).throw(AssertionError()))

    def fake_run_evaluation(**kwargs: object) -> dict[str, object]:
        captured_evaluation.update(kwargs)
        return {"metrics": {"groundedness": 4.0}}

    def fake_emit_evaluation_telemetry(**kwargs: object) -> None:
        captured_telemetry.update(kwargs)

    monkeypatch.setattr(script, "run_evaluation", fake_run_evaluation)
    monkeypatch.setattr(script, "emit_evaluation_telemetry", fake_emit_evaluation_telemetry)
    monkeypatch.setattr(script, "flush_observability", lambda: None)

    asyncio.run(script.main())

    assert captured_evaluation["dataset_path"] == dataset_path
    assert captured_evaluation["results_path"] == tmp_path / "ask_grounded_qa_results.json"
    assert captured_telemetry["row_count"] == 2


def test_apply_azure_identity_environment_maps_managed_identity_client_id(
    monkeypatch,
) -> None:
    script = load_script()
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)

    script.apply_azure_identity_environment(
        {
            "AZURE_TENANT_ID": " tenant-id ",
            "MANAGED_IDENTITY_CLIENT_ID": " managed-client-id ",
        }
    )

    assert os.environ["AZURE_TENANT_ID"] == "tenant-id"
    assert os.environ["AZURE_CLIENT_ID"] == "managed-client-id"


def test_is_reasoning_evaluator_model_uses_env_override_or_name_heuristic() -> None:
    script = load_script()

    assert script.is_reasoning_evaluator_model({}, "gpt-5-chat") is True
    assert script.is_reasoning_evaluator_model({}, "gpt-4o-mini") is False
    assert script.is_reasoning_evaluator_model(
        {"AZURE_AI_EVALUATION_REASONING_MODEL": "false"},
        "gpt-5-chat",
    ) is False


def test_collect_numeric_metrics_flattens_finite_numbers_only() -> None:
    script = load_script()

    metrics = script.collect_numeric_metrics(
        {
            "groundedness": 4,
            "relevance": {"mean": 3.5},
            "flag": True,
            "missing": None,
            "not_number": "4",
            "infinite": float("inf"),
        }
    )

    assert metrics == {
        "groundedness": 4.0,
        "relevance.mean": 3.5,
    }


def test_emit_evaluation_telemetry_sends_summary_without_row_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script = load_script()
    captured_spans: list[dict[str, object]] = []
    captured_events: list[tuple[str, dict[str, object]]] = []
    captured_logs: list[tuple[str, dict[str, object]]] = []

    class FakeSpan:
        def add_event(self, name: str, attributes: dict[str, object]) -> None:
            captured_events.append((name, attributes))

    @contextmanager
    def fake_start_request_span(name: str, *, tracer_name: str, attributes: dict[str, object]):
        captured_spans.append(
            {
                "name": name,
                "tracer_name": tracer_name,
                "attributes": attributes,
            }
        )
        yield FakeSpan()

    class FakeLogger:
        def info(self, event: str, **event_kw: object) -> None:
            captured_logs.append((event, event_kw))

    monkeypatch.setattr(script, "start_request_span", fake_start_request_span)
    result = {
        "metrics": {"groundedness": 4.0, "relevance": {"mean": 3.5}},
        "rows": [{"query": "민감한 질문", "response": "민감한 답변"}],
    }

    script.emit_evaluation_telemetry(
        result=result,
        dataset_path=tmp_path / "dataset.jsonl",
        results_path=tmp_path / "results.json",
        evaluator_names=["groundedness", "relevance"],
        row_count=2,
        logger=FakeLogger(),
    )

    assert captured_spans[0]["name"] == "homestyle.eval.grounded_qa"
    attributes = captured_spans[0]["attributes"]
    assert attributes["homestyle.eval.row_count"] == 2
    assert attributes["homestyle.eval.evaluators"] == "groundedness,relevance"
    assert attributes["homestyle.eval.metric.groundedness"] == 4.0
    assert attributes["homestyle.eval.metric.relevance_mean"] == 3.5
    assert captured_events == [
        (
            "homestyle.eval.metric",
            {
                "homestyle.eval.metric.name": "groundedness",
                "homestyle.eval.metric.value": 4.0,
            },
        ),
        (
            "homestyle.eval.metric",
            {
                "homestyle.eval.metric.name": "relevance.mean",
                "homestyle.eval.metric.value": 3.5,
            },
        ),
    ]
    assert captured_logs[0][0] == "grounded_qa_evaluation_completed"
    assert "민감한 질문" not in str(captured_logs)
    assert "민감한 답변" not in str(captured_logs)


def test_run_foundry_dataset_evaluation_uploads_jsonl_and_creates_cloud_run(
    monkeypatch,
    tmp_path: Path,
) -> None:
    script = load_script()
    dataset_path = tmp_path / "dataset.jsonl"
    dataset_path.write_text('{"query":"q","context":"c","response":"r"}\n', encoding="utf-8")
    fake_credential = object()
    created_eval_kwargs: dict[str, object] = {}
    created_run_kwargs: dict[str, object] = {}
    uploaded_files: list[dict[str, str]] = []
    deleted_datasets: list[dict[str, str]] = []
    monkeypatch.setattr(script, "build_sync_azure_credential", lambda _: fake_credential)

    class FakeDatasets:
        def delete(self, *, name: str, version: str) -> None:
            deleted_datasets.append({"name": name, "version": version})

        def upload_file(self, *, name: str, version: str, file_path: str) -> object:
            uploaded_files.append({"name": name, "version": version, "file_path": file_path})
            return SimpleNamespace(id="dataset-1")

    class FakeRuns:
        def create(self, **kwargs: object) -> object:
            created_run_kwargs.update(kwargs)
            return SimpleNamespace(id="run-1", status="queued", report_url="https://report.example")

    class FakeEvals:
        def __init__(self) -> None:
            self.runs = FakeRuns()

        def create(self, **kwargs: object) -> object:
            created_eval_kwargs.update(kwargs)
            return SimpleNamespace(id="eval-1")

    class FakeOpenAIClient:
        def __init__(self) -> None:
            self.evals = FakeEvals()

    class FakeAIProjectClient:
        def __init__(self, *, endpoint: str, credential: object) -> None:
            self.endpoint = endpoint
            self.credential = credential
            self.datasets = FakeDatasets()

        def get_openai_client(self) -> FakeOpenAIClient:
            return FakeOpenAIClient()

    monkeypatch.setitem(
        sys.modules,
        "azure.ai.projects",
        SimpleNamespace(AIProjectClient=FakeAIProjectClient),
    )
    settings = script.AzureRagSettings(
        azure_openai_endpoint="https://openai.example",
        azure_openai_api_version="2024-10-01-preview",
        azure_openai_chat_deployment="gpt-4o-mini",
        azure_openai_embedding_deployment="embedding",
        azure_openai_vision_deployment="vision",
        azure_search_endpoint="https://search.example",
        azure_search_index_name="index",
    )

    summary = script.run_foundry_dataset_evaluation(
        dataset_path=dataset_path,
        settings=settings,
        env={
            "AZURE_AI_PROJECT_ENDPOINT": "https://foundry.example/projects/project-1",
            "AZURE_AI_EVALUATION_OPENAI_DEPLOYMENT": "gpt-4.1",
            "AZURE_AI_EVALUATION_DATASET_NAME": "ask-dataset",
            "AZURE_AI_EVALUATION_DATASET_VERSION": "2",
            "AZURE_AI_EVALUATION_RUN_NAME": "ask-run",
        },
        evaluator_names=["groundedness", "similarity"],
    )

    assert summary == script.FoundryRunSummary(
        eval_id="eval-1",
        run_id="run-1",
        status="queued",
        report_url="https://report.example",
        dataset_id="dataset-1",
    )
    assert deleted_datasets == [{"name": "ask-dataset", "version": "2"}]
    assert uploaded_files == [
        {"name": "ask-dataset", "version": "2", "file_path": str(dataset_path)}
    ]
    assert created_eval_kwargs["name"] == "ask_grounded_qa"
    criteria = created_eval_kwargs["testing_criteria"]
    assert criteria[0]["evaluator_name"] == "builtin.groundedness"
    assert criteria[0]["data_mapping"]["context"] == "{{item.context}}"
    assert criteria[1]["evaluator_name"] == "builtin.similarity"
    assert criteria[1]["data_mapping"]["ground_truth"] == "{{item.ground_truth}}"
    assert created_run_kwargs == {
        "eval_id": "eval-1",
        "name": "ask-run",
        "data_source": {
            "type": "jsonl",
            "source": {"type": "file_id", "id": "dataset-1"},
        },
    }


def test_run_foundry_trace_evaluation_creates_agent_filter_run(monkeypatch) -> None:
    script = load_script()
    fake_credential = object()
    created_eval_kwargs: dict[str, object] = {}
    created_run_kwargs: dict[str, object] = {}
    monkeypatch.setattr(script, "build_sync_azure_credential", lambda _: fake_credential)

    class FakeRuns:
        def create(self, **kwargs: object) -> object:
            created_run_kwargs.update(kwargs)
            return SimpleNamespace(id="run-1", status="queued", report_url=None)

    class FakeEvals:
        def __init__(self) -> None:
            self.runs = FakeRuns()

        def create(self, **kwargs: object) -> object:
            created_eval_kwargs.update(kwargs)
            return SimpleNamespace(id="eval-1")

    class FakeOpenAIClient:
        def __init__(self) -> None:
            self.evals = FakeEvals()

    class FakeAIProjectClient:
        def __init__(self, *, endpoint: str, credential: object) -> None:
            self.endpoint = endpoint
            self.credential = credential

        def get_openai_client(self) -> FakeOpenAIClient:
            return FakeOpenAIClient()

    monkeypatch.setitem(
        sys.modules,
        "azure.ai.projects",
        SimpleNamespace(AIProjectClient=FakeAIProjectClient),
    )
    settings = script.AzureRagSettings(
        azure_openai_endpoint="https://openai.example",
        azure_openai_api_version="2024-10-01-preview",
        azure_openai_chat_deployment="gpt-4o-mini",
        azure_openai_embedding_deployment="embedding",
        azure_openai_vision_deployment="vision",
        azure_search_endpoint="https://search.example",
        azure_search_index_name="index",
    )

    summary = script.run_foundry_trace_evaluation(
        settings=settings,
        env={
            "AZURE_AI_PROJECT_ENDPOINT": "https://foundry.example/projects/project-1",
            "AZURE_AI_EVALUATION_OPENAI_DEPLOYMENT": "gpt-4.1",
            "AZURE_AI_EVALUATION_TRACE_AGENT_ID": "homestyle-agent:1",
            "AZURE_AI_EVALUATION_TRACE_LOOKBACK_HOURS": "6",
            "AZURE_AI_EVALUATION_TRACE_MAX_TRACES": "25",
        },
        evaluator_names=["relevance", "intent_resolution"],
        agent_id=None,
        lookback_hours=None,
        max_traces=None,
    )

    assert summary.eval_id == "eval-1"
    assert created_eval_kwargs["data_source_config"] == {
        "type": "azure_ai_source",
        "scenario": "traces",
    }
    criteria = created_eval_kwargs["testing_criteria"]
    assert criteria[0]["data_mapping"] == {
        "query": "{{item.query}}",
        "response": "{{item.response}}",
    }
    assert criteria[1]["evaluator_name"] == "builtin.intent_resolution"
    assert criteria[1]["data_mapping"]["tool_definitions"] == "{{item.tool_definitions}}"
    assert created_run_kwargs["data_source"] == {
        "type": "azure_ai_traces",
        "agent_id": "homestyle-agent:1",
        "max_traces": 25,
        "lookback_hours": 6,
    }