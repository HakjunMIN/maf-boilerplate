# Agent observability uses standard OpenTelemetry configuration

The Agent Request Path needs traces, logs, and metrics locally in Aspire Dashboard and later in Azure Application Insights. We will use standard OpenTelemetry environment variables as the primary configuration contract for OTLP backends, use Azure Monitor configuration only when `APPLICATION_INSIGHTS_CONNECTION_STRING` is set, and fail fast if both backend paths are configured in the same process. This keeps local Aspire setup portable, avoids an app-specific backend enum, and prevents accidental duplicate telemetry export.

## Consequences

- Aspire uses `ENABLE_INSTRUMENTATION=true` and `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`.
- OTLP support includes both gRPC and HTTP exporter packages because both local Aspire and a planned HTTP OTLP target must be configurable through standard OTEL environment variables.
- Application Insights uses `APPLICATION_INSIGHTS_CONNECTION_STRING` and Agent Framework instrumentation without OTLP exporter configuration.
- Sensitive Agent Content remains excluded by default and is only allowed through explicit local or test-only opt-in.
