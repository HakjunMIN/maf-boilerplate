---
name: azure-ai-evaluation-agent-eval
description: "Evaluate agent question/answer behavior with Azure AI Evaluation SDK for Python. Use when: azure-ai-evaluation, Azure AI Evaluation, agent eval, Q/A evaluation, RAG eval, grounded QA evaluation, relevance, groundedness, coherence, fluency, similarity, safety evaluators, simulator, 질문 답변 평가."
argument-hint: "Describe the agent, eval questions/data, available ground truth/context, and desired quality or safety metrics."
---

# Azure AI Evaluation Agent Eval

Use this skill to design, implement, or review evaluation workflows for Python agents and RAG systems using the Azure AI Evaluation SDK. The goal is to turn agent questions and answers into repeatable metrics, row-level evidence, and clear pass/fail checks without leaking secrets or sensitive content.

Base SDK guidance on the official Azure AI Evaluation README: <https://learn.microsoft.com/en-us/python/api/overview/azure/ai-evaluation-readme?view=azure-python>.

## When to Use

- Evaluate a Python agent's question/answer responses.
- Evaluate grounded QA, RAG, retrieval, or generated answers against test questions.
- Score existing answer datasets with `evaluate(...)`.
- Invoke an agent or HTTP endpoint as an evaluation target and score its outputs.
- Add quality metrics such as groundedness, relevance, coherence, fluency, similarity, retrieval, F1, ROUGE, GLEU, BLEU, or METEOR.
- Add safety metrics or adversarial simulations through Azure AI Foundry-backed evaluators.
- Create repeatable local, CI, or Azure AI Foundry-tracked evaluation runs.

## Source Check

Before implementing code, verify the current SDK API from the official README or API reference. Prefer documented imports from `azure.ai.evaluation` and `azure.ai.evaluation.simulator` over memory, because evaluator names and required configuration can change.

The SDK package is `azure-ai-evaluation`. Python 3.9 or later is required by the SDK, but follow the repository's stricter Python version when present.

## Workflow

1. Define the evaluation contract.
   - Identify the target: existing output dataset, Python callable, local HTTP endpoint, deployed endpoint, or simulator callback.
   - Identify the input columns: question/query, response, context, retrieved documents, ground truth, conversation history, metadata, and expected refusal or safety labels.
   - Decide whether evaluation is offline scoring of known outputs or live invocation of the agent.
   - Keep the contract explicit; do not infer `userId`, tenant, role, or ownership from client-provided data.

2. Choose the minimum evaluator set.
   - Grounded RAG answer: start with `GroundednessEvaluator`, `RelevanceEvaluator`, and, when retrieval output is available, `RetrievalEvaluator`.
   - General answer quality: use `CoherenceEvaluator`, `FluencyEvaluator`, and `SimilarityEvaluator` when ground truth exists.
   - Exact or lexical comparison: use NLP evaluators such as `F1ScoreEvaluator`, `RougeScoreEvaluator`, `GleuScoreEvaluator`, `BleuScoreEvaluator`, or `MeteorScoreEvaluator`.
   - Safety and harmful-content risk: use Azure AI Foundry-backed safety evaluators only when project configuration and responsible-use requirements are in place.
   - Custom business rules: add simple code-based evaluators for deterministic checks such as required citations, no empty answer, allowed language, blocked phrases, or schema validity.

3. Configure model-backed evaluators securely.
   - For AI-assisted quality evaluators, use model configuration from environment variables or the repository's settings layer.
   - For Azure AI Foundry safety evaluators or tracking, use `azure_ai_project` as documented, either project details or project URL.
   - Prefer managed identity or `DefaultAzureCredential` where supported. Do not hardcode API keys, connection strings, project identifiers containing secrets, or tokens.
   - Keep SDK `logging_enable` off by default. DEBUG logging can include request/response bodies or unredacted headers.

4. Prepare eval data.
   - Use JSONL for row-based evaluation when possible.
   - Each row should contain stable IDs, query/question text, and any expected ground truth or context needed by selected evaluators.
   - If evaluating a RAG target, preserve retrieved context in the target output so groundedness and retrieval metrics can map to `${outputs.context}`.
   - Exclude PII and secrets from eval fixtures. Mask or syntheticize sensitive examples.

5. Implement the target path.
   - For existing outputs, call `evaluate(data=..., evaluators=..., evaluator_config=...)` without a target.
   - For live app evaluation, pass `target=<callable>` to `evaluate(...)`. The target should accept row data and return a dictionary containing at least `response`; include `context` when needed.
   - For HTTP agents, wrap the endpoint in a small Python callable that sets timeouts, validates status codes, and returns only evaluator-safe fields.
   - For async agent APIs, use the SDK-supported target shape if available; otherwise create a synchronous wrapper that manages the event loop safely for the local test runner.

6. Map columns explicitly.
   - Use `evaluator_config` with `column_mapping` for each evaluator or `default` mapping when all evaluators share the same fields.
   - Map common fields deliberately: `query` from `${data.question}` or `${data.query}`, `response` from `${outputs.response}`, `context` from `${outputs.context}`, and `ground_truth` from `${data.ground_truth}`.
   - Do not rely on evaluator defaults when the dataset uses project-specific names.

7. Run and persist results.
   - Set `output_path` to a local JSON result file when the user needs reviewable artifacts.
   - Provide `azure_ai_project` only when the user wants Azure AI Foundry tracking.
   - Capture both summary metrics and row-level failures. Row-level output is the fastest path to improving prompts, retrieval, or tools.

8. Add pass/fail gates only after a baseline exists.
   - First run creates a baseline and exposes metric ranges.
   - Add conservative thresholds for CI after reviewing row-level results.
   - Prefer thresholds by metric and scenario, not one global score.
   - Keep safety gates stricter than quality gates when the agent is exposed to B2C or untrusted traffic.

9. Use simulators when test coverage is thin.
   - Use `Simulator` to generate context-relevant conversation data when seed questions are available.
   - Use `AdversarialSimulator` with `AdversarialScenario` for safety testing when Azure AI Foundry project configuration and credentials are available.
   - Review generated simulation data before committing it as a fixture.

10. Report findings clearly.
   - Summarize metric averages, threshold failures, and the worst rows.
   - Include question ID, query, response summary, metric scores, and a short failure reason.
   - Separate evaluation failure from application runtime failure.
   - Recommend targeted fixes: retrieval coverage, prompt grounding, response formatting, safety policy, or answer refusal behavior.

## Minimal Dataset Shape

Use a shape like this for grounded Q/A evaluation. Add fields only when an evaluator needs them.

```json
{"id":"qa-001","question":"What warranty applies?","ground_truth":"The product has a 1-year warranty.","context":"Warranty: 1 year from purchase date."}
```

For existing outputs, include the answer in the data row or map it from an outputs file according to the SDK pattern used in the implementation.

```json
{"id":"qa-001","question":"What warranty applies?","response":"The warranty is 1 year.","ground_truth":"The product has a 1-year warranty.","context":"Warranty: 1 year from purchase date."}
```

## Minimal Code Pattern

```python
import os

from azure.ai.evaluation import GroundednessEvaluator, RelevanceEvaluator, evaluate

model_config = {
    "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
    "api_key": os.environ["AZURE_OPENAI_API_KEY"],
    "azure_deployment": os.environ["AZURE_OPENAI_DEPLOYMENT"],
}

evaluators = {
    "groundedness": GroundednessEvaluator(model_config),
    "relevance": RelevanceEvaluator(model_config),
}

result = evaluate(
    data="eval_questions.jsonl",
    target=ask_agent,
    evaluators=evaluators,
    evaluator_config={
        "default": {
            "column_mapping": {
                "query": "${data.question}",
                "response": "${outputs.response}",
                "context": "${outputs.context}",
            }
        }
    },
    output_path="evaluation_results.json",
)
```

## HTTP Target Pattern

When evaluating a local or deployed `/ask` endpoint, keep the wrapper small and explicit.

```python
import json
from urllib import request


def ask_agent(question: str, **kwargs: object) -> dict[str, str]:
    body = json.dumps({"question": question}).encode("utf-8")
    http_request = request.Request(
       "http://127.0.0.1:8080/ask",
       data=body,
       headers={"Content-Type": "application/json"},
       method="POST",
    )

    with request.urlopen(http_request, timeout=30) as response:
       payload = json.loads(response.read().decode("utf-8"))

    return {
       "response": payload["answer"],
       "context": payload.get("context", ""),
    }
```

Adjust field names to the real API schema. Validate input and output at the boundary before sending rows to evaluators.

## Security and Privacy

- Treat prompts, responses, retrieved documents, tool arguments, user IDs, tenant IDs, and traces as sensitive.
- Do not commit real customer prompts, personal data, API keys, bearer tokens, Azure connection strings, or unredacted telemetry.
- Disable verbose SDK logging unless a local debug session explicitly needs it.
- Use environment variables, Azure Key Vault, managed identity, or workload identity for credentials.
- If evaluation results are uploaded to Azure AI Foundry, confirm the data is allowed to leave the local environment.
- For B2C-facing agents, include safety and abuse cases before treating quality scores as sufficient.

## Completion Criteria

- Evaluation goal, dataset schema, target shape, and evaluator set are explicit.
- SDK usage follows current Azure AI Evaluation documentation.
- Column mappings are declared for every evaluator input.
- Credentials and Azure project settings come from secure configuration, not source code.
- Results include summary metrics and row-level data.
- Failures are actionable and tied to question IDs or scenario IDs.
- CI thresholds, if added, are based on an observed baseline.
- Sensitive data exposure has been checked before committing fixtures or result artifacts.
