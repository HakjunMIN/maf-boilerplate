import importlib.util
from pathlib import Path
from types import ModuleType

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


def test_is_reasoning_evaluator_model_uses_env_override_or_name_heuristic() -> None:
    script = load_script()

    assert script.is_reasoning_evaluator_model({}, "gpt-5-chat") is True
    assert script.is_reasoning_evaluator_model({}, "gpt-4o-mini") is False
    assert script.is_reasoning_evaluator_model(
        {"AZURE_AI_EVALUATION_REASONING_MODEL": "false"},
        "gpt-5-chat",
    ) is False