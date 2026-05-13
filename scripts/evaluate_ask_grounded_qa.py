import argparse
import asyncio
import json
import math
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiohttp import ClientSession, ClientTimeout
from azure.core.credentials import AzureKeyCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.identity import AzureCliCredential as SyncAzureCliCredential
from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
from azure.identity import ManagedIdentityCredential as SyncManagedIdentityCredential

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIRECTORY = REPO_ROOT / "src"
if str(SRC_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SRC_DIRECTORY))

from homestyle_agent.application.grounded_query import select_grounding_sections  # noqa: E402
from homestyle_agent.infrastructure.retrieval import AzureSearchSectionRetriever  # noqa: E402
from homestyle_shared.domain.indexing import SectionDocument  # noqa: E402
from homestyle_shared.infrastructure.azure_identity import build_azure_credential  # noqa: E402
from homestyle_shared.infrastructure.observability import (  # noqa: E402
    StructuredLogger,
    build_logger,
    configure_process_observability,
    start_request_span,
)
from homestyle_shared.infrastructure.openai import AzureOpenAIEmbedder  # noqa: E402
from homestyle_shared.infrastructure.settings import AzureRagSettings, load_environment  # noqa: E402

DEFAULT_QUESTIONS_PATH = Path("tests/e2e/observability_questions.json")
DEFAULT_OUTPUT_DIR = Path(".eval/grounded-qa")
DEFAULT_EVALUATORS = ("groundedness", "relevance", "coherence", "fluency")
EVALUATOR_CHOICES = (*DEFAULT_EVALUATORS, "similarity")
EVALUATION_API_KEY_ENV_VARS = ("AZURE_AI_EVALUATION_OPENAI_API_KEY", "AZURE_OPENAI_API_KEY")
EVALUATION_DEPLOYMENT_ENV_VAR = "AZURE_AI_EVALUATION_OPENAI_DEPLOYMENT"
EVALUATION_REASONING_MODEL_ENV_VAR = "AZURE_AI_EVALUATION_REASONING_MODEL"
AZURE_AI_PROJECT_ENDPOINT_ENV_VARS = (
    "AZURE_AI_PROJECT_ENDPOINT",
    "AZURE_AI_PROJECT_URL",
    "AZURE_AI_FOUNDRY_PROJECT_ENDPOINT",
)
AZURE_IDENTITY_ENV_VARS = (
    "AZURE_TENANT_ID",
    "AZURE_CLIENT_ID",
    "AZURE_CLIENT_SECRET",
    "AZURE_CLIENT_CERTIFICATE_PATH",
    "AZURE_USERNAME",
    "AZURE_PASSWORD",
)
MAX_CONTEXT_CHARS = 12_000
MAX_SOURCE_CONTENT_CHARS = 2_000
EVALUATION_NAME = "ask_grounded_qa"
EVALUATION_SPAN_NAME = "homestyle.eval.grounded_qa"
EVALUATION_TRACER_NAME = "homestyle_agent.evaluation"


@dataclass(frozen=True)
class EvalQuestion:
    id: str
    query: str


@dataclass(frozen=True)
class EvalPaths:
    dataset_path: Path
    results_path: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a grounded QA eval dataset and evaluate /ask responses.",
    )
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--ask-endpoint", default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--max-context-chars", type=int, default=MAX_CONTEXT_CHARS)
    parser.add_argument(
        "--evaluators",
        nargs="+",
        choices=EVALUATOR_CHOICES,
        default=list(DEFAULT_EVALUATORS),
    )
    parser.add_argument(
        "--skip-evaluate",
        action="store_true",
        help="Only write the JSONL dataset; do not run Azure AI Evaluation.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    env = load_environment()
    settings = AzureRagSettings.from_env(env)
    configure_process_observability(
        log_level=settings.log_level,
        application_insights_connection_string=settings.application_insights_connection_string,
        env=env,
    )
    logger = build_logger("grounded_qa_evaluation")
    questions, configured_endpoint = load_questions(args.questions)
    endpoint = args.ask_endpoint or configured_endpoint or "http://127.0.0.1:8080/ask"
    paths = make_eval_paths(args.output_dir)

    async_credential = build_azure_credential(
        use_developer_credentials=settings.use_developer_credentials,
        azure_tenant_id=settings.azure_tenant_id,
        managed_identity_client_id=settings.managed_identity_client_id,
    )
    embedder = AzureOpenAIEmbedder(
        endpoint=settings.azure_openai_endpoint,
        deployment=settings.azure_openai_embedding_deployment,
        api_version=settings.azure_openai_api_version,
        credential=async_credential,
    )
    retriever = AzureSearchSectionRetriever(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index_name,
        credential=build_search_credential(settings, async_credential),
        embed_query=embedder.embed_text,
        top=settings.search_top,
    )

    try:
        rows = await build_eval_rows(
            questions=questions,
            endpoint=endpoint,
            env=env,
            retriever=retriever,
            timeout_seconds=args.timeout_seconds,
            max_context_chars=args.max_context_chars,
        )
    finally:
        await retriever.close()
        await embedder.close()
        await close_if_present(async_credential)

    write_jsonl(paths.dataset_path, rows)
    print(f"Wrote {len(rows)} eval rows to {paths.dataset_path}")

    if args.skip_evaluate:
        return

    result = run_evaluation(
        dataset_path=paths.dataset_path,
        results_path=paths.results_path,
        settings=settings,
        env=env,
        evaluator_names=args.evaluators,
    )
    emit_evaluation_telemetry(
        result=result,
        dataset_path=paths.dataset_path,
        results_path=paths.results_path,
        evaluator_names=args.evaluators,
        row_count=len(rows),
        logger=logger,
    )
    flush_observability()
    print(f"Wrote evaluation results to {paths.results_path}")
    print(json.dumps(result.get("metrics", {}), ensure_ascii=False, indent=2))


def load_questions(path: Path) -> tuple[list[EvalQuestion], str | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("questions file must contain a JSON object")
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list):
        raise ValueError("questions file must contain a questions array")

    questions: list[EvalQuestion] = []
    for raw_question in raw_questions:
        if not isinstance(raw_question, dict):
            raise ValueError("each question must be a JSON object")
        question_id = read_required_str(raw_question, "id")
        query = read_required_str(raw_question, "question")
        questions.append(EvalQuestion(id=question_id, query=query))

    endpoint = payload.get("endpoint")
    if endpoint is not None and not isinstance(endpoint, str):
        raise ValueError("endpoint must be a string when provided")
    return questions, endpoint


async def build_eval_rows(
    *,
    questions: Sequence[EvalQuestion],
    endpoint: str,
    env: Mapping[str, str],
    retriever: AzureSearchSectionRetriever,
    timeout_seconds: float,
    max_context_chars: int,
) -> list[dict[str, Any]]:
    timeout = ClientTimeout(total=timeout_seconds)
    headers = build_ask_headers(env)
    rows: list[dict[str, Any]] = []
    async with ClientSession(timeout=timeout, headers=headers) as session:
        for question in questions:
            sections = select_grounding_sections(await retriever.retrieve_sections(question.query))
            context = build_context(sections, max_context_chars=max_context_chars)
            response = await ask_endpoint(
                session=session,
                endpoint=endpoint,
                question=question.query,
            )
            rows.append(
                {
                    "id": question.id,
                    "query": question.query,
                    "context": context,
                    "ground_truth": context,
                    "response": response,
                    "sources": [source_from_section(section) for section in sections],
                }
            )
    return rows


async def ask_endpoint(*, session: ClientSession, endpoint: str, question: str) -> str:
    async with session.post(endpoint, json={"question": question}) as response:
        payload = await response.json(content_type=None)
        if response.status != 200:
            raise RuntimeError(f"/ask failed with HTTP {response.status}: {safe_json(payload)}")
        if not isinstance(payload, dict):
            raise RuntimeError("/ask response must be a JSON object")
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("/ask response must contain a non-empty answer string")
        return answer.strip()


def build_context(sections: Sequence[SectionDocument], *, max_context_chars: int) -> str:
    parts: list[str] = []
    for index, section in enumerate(sections, start=1):
        heading = section.section_heading or section.title
        breadcrumb = " > ".join(section.breadcrumb)
        content = section.content[:MAX_SOURCE_CONTENT_CHARS].strip()
        parts.append(
            f"[{index}] title: {section.title}\n"
            f"heading: {heading}\n"
            f"breadcrumb: {breadcrumb}\n"
            f"url: {section.page_url}\n"
            f"content: {content}"
        )
    return "\n\n".join(parts)[:max_context_chars]


def source_from_section(section: SectionDocument) -> dict[str, Any]:
    return {
        "chunk_id": section.chunk_id,
        "title": section.title,
        "section_heading": section.section_heading,
        "page_url": section.page_url,
        "confidence_score": section.confidence_score,
        "reviewer_approved": section.reviewer_approved,
    }


def run_evaluation(
    *,
    dataset_path: Path,
    results_path: Path,
    settings: AzureRagSettings,
    env: Mapping[str, str],
    evaluator_names: Sequence[str],
) -> dict[str, Any]:
    try:
        from azure.ai.evaluation import (
            AzureOpenAIModelConfiguration,
            CoherenceEvaluator,
            FluencyEvaluator,
            GroundednessEvaluator,
            RelevanceEvaluator,
            SimilarityEvaluator,
            evaluate,
        )
    except ImportError as error:
        raise RuntimeError("Install azure-ai-evaluation before running evaluation.") from error

    api_key = read_evaluation_api_key(env)
    sync_credential = None if api_key else build_sync_azure_credential(settings)
    foundry_upload_credential = None
    evaluator_deployment = read_evaluation_deployment(env, settings)
    model_config_values: dict[str, Any] = {
        "azure_endpoint": settings.azure_openai_endpoint,
        "azure_deployment": evaluator_deployment,
        "api_version": settings.azure_openai_api_version,
    }
    if api_key:
        model_config_values["api_key"] = api_key
    model_config = AzureOpenAIModelConfiguration(**model_config_values)

    evaluator_factories = {
        "groundedness": GroundednessEvaluator,
        "relevance": RelevanceEvaluator,
        "coherence": CoherenceEvaluator,
        "fluency": FluencyEvaluator,
        "similarity": SimilarityEvaluator,
    }
    evaluator_kwargs: dict[str, object] = {}
    if sync_credential is not None:
        evaluator_kwargs["credential"] = sync_credential
    if is_reasoning_evaluator_model(env, evaluator_deployment):
        evaluator_kwargs["is_reasoning_model"] = True
    evaluators = {
        name: evaluator_factories[name](model_config, **evaluator_kwargs) for name in evaluator_names
    }
    evaluator_config = {
        "default": {
            "column_mapping": {
                "query": "${data.query}",
                "context": "${data.context}",
                "response": "${data.response}",
                "ground_truth": "${data.ground_truth}",
            }
        }
    }
    evaluate_kwargs: dict[str, Any] = {
        "data": str(dataset_path),
        "evaluators": evaluators,
        "evaluation_name": EVALUATION_NAME,
        "evaluator_config": evaluator_config,
        "output_path": str(results_path),
    }
    azure_ai_project = read_azure_ai_project(env)
    if azure_ai_project is not None:
        apply_azure_identity_environment(env)
        evaluate_kwargs["azure_ai_project"] = azure_ai_project
        foundry_upload_credential = sync_credential or build_sync_azure_credential(settings)
        evaluate_kwargs["credential"] = foundry_upload_credential

    try:
        result = evaluate(**evaluate_kwargs)
        return dict(result)
    finally:
        close_if_present_sync(sync_credential)
        if foundry_upload_credential is not sync_credential:
            close_if_present_sync(foundry_upload_credential)


def emit_evaluation_telemetry(
    *,
    result: Mapping[str, Any],
    dataset_path: Path,
    results_path: Path,
    evaluator_names: Sequence[str],
    row_count: int,
    logger: StructuredLogger,
) -> None:
    raw_metrics = result.get("metrics", {})
    metrics = collect_numeric_metrics(raw_metrics if isinstance(raw_metrics, Mapping) else {})
    attributes: dict[str, object] = {
        "homestyle.eval.name": EVALUATION_NAME,
        "homestyle.eval.row_count": row_count,
        "homestyle.eval.evaluator_count": len(evaluator_names),
        "homestyle.eval.evaluators": ",".join(evaluator_names),
        "homestyle.eval.dataset_path": str(dataset_path),
        "homestyle.eval.results_path": str(results_path),
    }
    for name, value in metrics.items():
        attributes[f"homestyle.eval.metric.{sanitize_metric_name(name)}"] = value

    with start_request_span(
        EVALUATION_SPAN_NAME,
        tracer_name=EVALUATION_TRACER_NAME,
        attributes=attributes,
    ) as span:
        add_event = getattr(span, "add_event", None)
        if add_event is not None:
            for name, value in metrics.items():
                add_event(
                    "homestyle.eval.metric",
                    {
                        "homestyle.eval.metric.name": name,
                        "homestyle.eval.metric.value": value,
                    },
                )

    logger.info(
        "grounded_qa_evaluation_completed",
        evaluation_name=EVALUATION_NAME,
        row_count=row_count,
        evaluator_names=list(evaluator_names),
        metrics=metrics,
        dataset_path=str(dataset_path),
        results_path=str(results_path),
    )


def collect_numeric_metrics(metrics: Mapping[str, Any], prefix: str = "") -> dict[str, float]:
    collected: dict[str, float] = {}
    for name, value in metrics.items():
        metric_name = f"{prefix}.{name}" if prefix else str(name)
        if isinstance(value, Mapping):
            collected.update(collect_numeric_metrics(value, metric_name))
        elif isinstance(value, bool):
            continue
        elif isinstance(value, (int, float)) and math.isfinite(value):
            collected[metric_name] = float(value)
    return collected


def sanitize_metric_name(name: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in name)


def flush_observability() -> None:
    from opentelemetry import trace

    force_flush = getattr(trace.get_tracer_provider(), "force_flush", None)
    if force_flush is not None:
        force_flush()


def build_search_credential(
    settings: AzureRagSettings,
    token_credential: AsyncTokenCredential,
) -> AzureKeyCredential | AsyncTokenCredential:
    if settings.azure_search_admin_key:
        return AzureKeyCredential(settings.azure_search_admin_key)
    return token_credential


def read_evaluation_api_key(env: Mapping[str, str]) -> str | None:
    for name in EVALUATION_API_KEY_ENV_VARS:
        value = env.get(name, "").strip()
        if value:
            return value
    return None


def read_evaluation_deployment(env: Mapping[str, str], settings: AzureRagSettings) -> str:
    value = env.get(EVALUATION_DEPLOYMENT_ENV_VAR, "").strip()
    if value:
        return value
    return settings.azure_openai_chat_deployment


def read_azure_ai_project(env: Mapping[str, str]) -> str | None:
    for name in AZURE_AI_PROJECT_ENDPOINT_ENV_VARS:
        value = env.get(name, "").strip()
        if value:
            return value
    return None


def apply_azure_identity_environment(env: Mapping[str, str]) -> None:
    for name in AZURE_IDENTITY_ENV_VARS:
        value = env.get(name, "").strip()
        if value:
            os.environ[name] = value

    managed_identity_client_id = env.get("MANAGED_IDENTITY_CLIENT_ID", "").strip()
    if managed_identity_client_id and not os.environ.get("AZURE_CLIENT_ID", "").strip():
        os.environ["AZURE_CLIENT_ID"] = managed_identity_client_id


def is_reasoning_evaluator_model(env: Mapping[str, str], deployment: str) -> bool:
    value = env.get(EVALUATION_REASONING_MODEL_ENV_VAR, "").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False

    normalized = deployment.lower()
    return any(marker in normalized for marker in ("gpt-5", "o1", "o3", "o4"))


def build_sync_azure_credential(settings: AzureRagSettings) -> object:
    if settings.use_developer_credentials:
        if settings.azure_tenant_id:
            return SyncAzureCliCredential(tenant_id=settings.azure_tenant_id)
        return SyncDefaultAzureCredential()
    if settings.managed_identity_client_id:
        return SyncManagedIdentityCredential(client_id=settings.managed_identity_client_id)
    return SyncManagedIdentityCredential()


def build_ask_headers(env: Mapping[str, str]) -> dict[str, str]:
    token = env.get("HOMESTYLE_AGENT_BEARER_TOKEN", "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def make_eval_paths(output_dir: Path) -> EvalPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    return EvalPaths(
        dataset_path=output_dir / "ask_grounded_qa_dataset.jsonl",
        results_path=output_dir / "ask_grounded_qa_results.json",
    )


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_required_str(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def safe_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False)[:500]


async def close_if_present(resource: object) -> None:
    close = getattr(resource, "close", None)
    if close is not None:
        result = close()
        if asyncio.iscoroutine(result):
            await result


def close_if_present_sync(resource: object) -> None:
    close = getattr(resource, "close", None)
    if close is not None:
        close()


if __name__ == "__main__":
    asyncio.run(main())