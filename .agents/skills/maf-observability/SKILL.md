---
name: maf-observability
description: 'Implement, review, migrate, or troubleshoot Microsoft Agent Framework Python observability with OpenTelemetry, traces, logs, metrics, Azure Monitor Application Insights, Aspire Dashboard, console exporters, MCP trace propagation, configure_otel_providers, enable_instrumentation, and GenAI semantic conventions.'
argument-hint: 'Describe the MAF app, telemetry backend, and whether this is new setup, migration, review, or troubleshooting.'
---

# MAF Observability

Use this skill when adding or reviewing observability for Python applications built with Microsoft Agent Framework. It turns Agent Framework telemetry on deliberately, sends traces/logs/metrics to a chosen OpenTelemetry-compatible backend, and verifies that agent, model, workflow, and tool activity can be inspected without leaking sensitive data.

Default to Aspire Dashboard for local development unless the user names another backend. Keep the guidance reusable for Python MAF projects in general; do not assume this repository's runtime or settings structure unless the user asks for a repo-specific implementation.

Base implementation guidance on the current official sample: <https://github.com/microsoft/agent-framework/blob/main/python/samples/02-agents/observability/README.md>.

## When to Use

- Add OpenTelemetry observability to a Microsoft Agent Framework Python app.
- Configure traces, logs, or metrics for agents, workflows, model calls, tool calls, or MCP tools.
- Send telemetry to Azure Monitor Application Insights, Aspire Dashboard, console exporters, Langfuse, Opik, or another OTLP-compatible APM backend.
- Review whether existing observability uses the current Agent Framework API instead of deprecated `setup_observability` patterns.
- Troubleshoot missing spans, logs, metrics, operation IDs, token usage, tool call duration, or MCP trace propagation.

## Source Check

Before changing code, consult the official Agent Framework observability sample and prefer its current API names over memory. If the repository also uses the general `microsoft-agent-framework` skill, apply that skill first for Python package and framework guidance, then use this skill for observability-specific decisions.

## Workflow

1. Identify the telemetry goal.
   - Local debugging: prefer Aspire Dashboard, with console exporters as the fallback when no viewer is available.
   - Azure production monitoring: prefer Azure Monitor Application Insights.
   - Vendor APM: prefer standard OTLP environment variables or the vendor's supported OpenTelemetry setup.
   - Migration: look for deprecated `setup_observability`, `OTLP_ENDPOINT`, or implicit console fallback assumptions.

2. Inspect existing dependencies and settings.
   - Agent Framework includes OpenTelemetry API, SDK, and GenAI semantic conventions support.
   - Add exporter dependencies only when needed.
   - Use `azure-monitor-opentelemetry` for Application Insights.
   - Use `opentelemetry-exporter-otlp-proto-grpc` for Aspire Dashboard or gRPC OTLP backends.
   - Use `opentelemetry-exporter-otlp-proto-http` only when HTTP OTLP export is required.

3. Choose one setup pattern.
   - Standard environment variables: call `configure_otel_providers()` from `agent_framework.observability` and configure `OTEL_EXPORTER_OTLP_*` variables outside code.
   - Console/local startup: call `configure_otel_providers(enable_console_exporters=True)` or set `ENABLE_CONSOLE_EXPORTERS=true`.
   - Custom exporters: create OTLP trace, log, and metric exporters explicitly and pass them as `exporters=[...]` to `configure_otel_providers(...)`.
   - Third-party setup: configure the third-party OpenTelemetry provider first, then call `enable_instrumentation(...)` to activate Agent Framework telemetry code paths.
   - Foundry-backed Azure Monitor: prefer the Foundry client helper that configures Azure Monitor from the project connection details.
   - Full manual setup: use only when the app needs explicit provider, processor, reader, or exporter control.

4. Configure environment variables explicitly.
   - `ENABLE_INSTRUMENTATION=true` turns on Agent Framework telemetry when not enabled in code.
   - `ENABLE_SENSITIVE_DATA=true` may include prompts, responses, and other sensitive content; do not enable it in production.
   - `ENABLE_CONSOLE_EXPORTERS=true` opts in to console telemetry output when using `configure_otel_providers()`.
   - `OTEL_SERVICE_NAME`, `OTEL_SERVICE_VERSION`, and `OTEL_RESOURCE_ATTRIBUTES` identify the service.
   - `OTEL_EXPORTER_OTLP_ENDPOINT`, signal-specific endpoints, protocol, and headers configure OTLP export.
   - `VS_CODE_EXTENSION_PORT` is only for AI Toolkit tracing integration.

5. Preserve security and privacy.
   - Treat prompts, responses, tool arguments, retrieved documents, user identifiers, and tenant identifiers as sensitive by default.
   - Do not hardcode instrumentation keys, connection strings, API keys, or OTLP headers.
   - Prefer environment variables, managed identity, or the cloud provider's configuration path for secrets.
   - Keep `enable_sensitive_data=False` unless the user explicitly requests local or test-only payload capture.
   - Mask or omit PII in app logs before those logs reach telemetry exporters.

6. Implement at the application boundary.
   - Initialize telemetry once during process startup before creating agents, workflows, clients, or MCP tools.
   - Keep observability setup in an infrastructure/runtime module, not domain logic.
   - Use standard Python logging configuration for log level and formatting.
   - Avoid hidden global side effects in tests; isolate telemetry setup behind explicit startup functions where possible.

7. Account for MCP trace propagation.
   - Agent Framework automatically propagates active OpenTelemetry span context through `params._meta` for client-opened MCP sessions such as `MCPStreamableHTTPTool`, `MCPStdioTool`, and `MCPWebsocketTool`.
   - This automatic injection does not apply when a hosted provider runtime issues the MCP `tools/call` request, such as provider-managed MCP tools from Foundry, OpenAI, Anthropic, Gemini, or toolbox-fetched tools.
   - If end-to-end tracing to the downstream MCP server is required, choose a client-opened MCP transport.

8. Validate telemetry.
   - Run a narrow app path that performs at least one agent or workflow invocation and, when relevant, one tool call.
   - Confirm traces, logs, and metrics arrive in the selected backend.
   - Confirm service name/version/resource attributes are useful.
   - Confirm operation or trace IDs are visible for filtering.
   - Confirm token usage, model call spans, tool call spans, and tool call durations appear when expected.
   - Confirm sensitive data is absent unless intentionally enabled for a local/test run.

## Local Aspire Dashboard

For a local OpenTelemetry viewer, run Aspire Dashboard with Docker and send OTLP data to `http://localhost:4317`. The dashboard UI is available at `http://localhost:18888`.

```bash
docker run --rm -it -d \
  -p 18888:18888 \
  -p 4317:18889 \
  --name aspire-dashboard \
  mcr.microsoft.com/dotnet/aspire-dashboard:latest
```

Configure the app with at least:

```bash
ENABLE_INSTRUMENTATION=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

Use console exporters when no backend is available:

```bash
ENABLE_INSTRUMENTATION=true
ENABLE_CONSOLE_EXPORTERS=true
```

## Current API Reminders

- Prefer `configure_otel_providers()` for Agent Framework-managed provider/exporter setup.
- Prefer `enable_instrumentation()` when another package already configured OpenTelemetry providers/exporters.
- Prefer `create_resource()` when manually configuring Azure Monitor or custom providers and you need Agent Framework-compatible resource attributes.
- Do not use deprecated `setup_observability(...)` examples as a model for new code.
- Console output is opt-in; do not assume it appears automatically when exporters are missing.

## Completion Criteria

- Observability setup is initialized once at application startup.
- Traces, logs, and metrics have a defined destination or an explicit local console mode.
- Exporter dependencies are minimal and match the selected backend.
- Configuration uses standard OpenTelemetry environment variables where possible.
- Sensitive data capture is disabled by default and documented when intentionally enabled.
- MCP trace propagation limitations are handled or called out.
- A verification command or manual check confirms telemetry reaches the backend.
