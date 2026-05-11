# Homestyle Agent

Homestyle Agent answers Korean questions about LG HomeStyle content using grounded evidence from the indexed corpus. This context captures domain language for the agent runtime and its operational boundaries.

## Language

**Agent Request Path**:
The user-facing path that starts with an Agent question and ends with a Grounded Answer or Decline.
_Avoid_: full pipeline, ingestion flow, crawler flow

**Agent Observability**:
Telemetry for the Agent Request Path that lets operators inspect request flow, retrieval, generation, and outcomes without exposing sensitive content.
_Avoid_: crawler observability, generic logging, debug dump

**Sensitive Agent Content**:
User questions, Grounding Context, Evidence, and Grounded Answer text that may reveal user intent or proprietary content.
_Avoid_: safe debug payload, harmless prompt text

**Session ID**:
The identifier for a multi-turn conversation across one or more Agent Request Paths.
_Avoid_: correlation ID, trace ID, request ID

**Correlation ID**:
The identifier for one Agent Request Path used to connect logs, spans, metrics, and error responses.
_Avoid_: session ID, conversation ID, trace ID

**Agent Request Outcome**:
The final category of an Agent Request Path: `answered`, `declined`, `invalid_request`, `unauthorized`, or `failed`.
_Avoid_: status, result, success flag

## Relationships

- An **Agent Request Path** belongs to exactly one **Agent** interaction.
- **Agent Observability** describes the **Agent Request Path**, not the **Ingestion Pipeline**.
- An **Agent Request Path** produces either one **Grounded Answer** or one **Decline**.
- **Agent Observability** excludes **Sensitive Agent Content** unless local or test-only capture is explicitly enabled.
- One **Session ID** can contain many **Agent Request Paths**.
- Each **Agent Request Path** has exactly one **Correlation ID**.
- Each **Agent Request Path** has exactly one **Agent Request Outcome**.

## Example dialogue

> **Dev:** "Should Agent Observability include crawling and indexing jobs?"
> **Domain expert:** "No — for this decision, Agent Observability covers only the Agent Request Path from question to answer. The Ingestion Pipeline is a separate concern."

## Flagged ambiguities

- "전체 옵서버빌리티" could mean the whole repository, including ingestion. Resolved: in this plan it means logs, metrics, and traces across the **Agent Request Path** only.
- "logs, metrics, traces" could imply capturing full prompt and answer payloads. Resolved: **Sensitive Agent Content** is excluded by default and may only be captured through an explicit local or test-only opt-in.
- The current API code uses `session_id` as a correlation value. Resolved language: **Session ID** and **Correlation ID** are distinct; implementation should carry both.
- `declined` is not a failure outcome; it is the expected result when the Agent lacks sufficient Evidence.
