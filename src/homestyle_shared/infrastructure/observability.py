import importlib.metadata
import logging
import os
import sys
from collections.abc import Mapping
from typing import Protocol
from uuid import uuid4

import structlog

_AZURE_MONITOR_CONNECTION_STRING: str | None = None
_AGENT_FRAMEWORK_OTEL_CONFIGURED = False
_APPLICATION_OTEL_LOGGING_HANDLER_MARKER = "_homestyle_application_otel_logging_handler"
_OTEL_INTERNAL_LOGGER_PREFIXES = ("opentelemetry.", "grpc")
_OTLP_EXPORTER_ENV_VARS = (
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
)


class StructuredLogger(Protocol):
    def bind(self, **new_values: object) -> "StructuredLogger": ...

    def info(self, event: str, **event_kw: object) -> object: ...


class _ApplicationTelemetryLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(_OTEL_INTERNAL_LOGGER_PREFIXES)


def configure_observability(
    *,
    log_level: str = "INFO",
    application_insights_connection_string: str | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    values = os.environ if env is None else env
    _apply_agent_framework_observability_env(values)
    if application_insights_connection_string:
        _reject_conflicting_otlp_exporter_configuration(values)

    resolved_level = _resolve_log_level(log_level)
    logging.basicConfig(
        level=resolved_level,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_logger_name,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(resolved_level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    if application_insights_connection_string:
        _configure_azure_monitor(application_insights_connection_string)
        _enable_agent_framework_instrumentation()
    elif _has_otlp_exporter_configuration(values):
        _configure_agent_framework_otel_once()
        _attach_application_otel_logging_handler(resolved_level)


def build_logger(name: str) -> StructuredLogger:
    return structlog.get_logger(name)


def bind_correlation_id(
    logger: StructuredLogger,
    correlation_id: str | None = None,
) -> tuple[StructuredLogger, str]:
    resolved_correlation_id = correlation_id or str(uuid4())
    return logger.bind(correlation_id=resolved_correlation_id), resolved_correlation_id


def _resolve_log_level(log_level: str) -> int:
    normalized_level = log_level.strip().upper() if log_level.strip() else "INFO"
    return getattr(logging, normalized_level, logging.INFO)


def _configure_azure_monitor(connection_string: str) -> None:
    global _AZURE_MONITOR_CONNECTION_STRING
    if _AZURE_MONITOR_CONNECTION_STRING == connection_string:
        return

    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=connection_string)
    _AZURE_MONITOR_CONNECTION_STRING = connection_string


def _reject_conflicting_otlp_exporter_configuration(env: Mapping[str, str]) -> None:
    configured_names = _configured_otlp_exporter_env_vars(env)
    if not configured_names:
        return

    joined_names = ", ".join(configured_names)
    raise ValueError(
        "APPLICATION_INSIGHTS_CONNECTION_STRING cannot be used with OTLP exporter "
        f"configuration: {joined_names}",
    )


def _configure_agent_framework_otel_once() -> None:
    global _AGENT_FRAMEWORK_OTEL_CONFIGURED
    if _AGENT_FRAMEWORK_OTEL_CONFIGURED:
        return

    _configure_agent_framework_otel_providers()
    _AGENT_FRAMEWORK_OTEL_CONFIGURED = True


def _configure_agent_framework_otel_providers() -> None:
    _patch_agent_framework_version()
    from agent_framework.observability import configure_otel_providers

    configure_otel_providers()


def _attach_application_otel_logging_handler(level: int) -> None:
    from opentelemetry._logs import get_logger_provider
    from opentelemetry.sdk._logs import LoggingHandler

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if getattr(handler, _APPLICATION_OTEL_LOGGING_HANDLER_MARKER, False):
            handler.setLevel(level)
            return

    handler = LoggingHandler(level=level, logger_provider=get_logger_provider())
    handler.addFilter(_ApplicationTelemetryLogFilter())
    setattr(handler, _APPLICATION_OTEL_LOGGING_HANDLER_MARKER, True)
    root_logger.addHandler(handler)


def _enable_agent_framework_instrumentation() -> None:
    _patch_agent_framework_version()
    from agent_framework.observability import enable_instrumentation

    enable_instrumentation(enable_sensitive_data=False)


def _patch_agent_framework_version() -> None:
    import agent_framework

    if getattr(agent_framework, "__version__", None):
        return
    setattr(agent_framework, "__version__", importlib.metadata.version("agent-framework"))


def _has_otlp_exporter_configuration(env: Mapping[str, str]) -> bool:
    return bool(_configured_otlp_exporter_env_vars(env))


def _configured_otlp_exporter_env_vars(env: Mapping[str, str]) -> list[str]:
    return [name for name in _OTLP_EXPORTER_ENV_VARS if env.get(name, "").strip()]


def _apply_agent_framework_observability_env(env: Mapping[str, str]) -> None:
    for name, value in env.items():
        if not _is_agent_framework_observability_env_var(name):
            continue
        stripped = value.strip()
        if stripped:
            os.environ[name] = stripped


def _is_agent_framework_observability_env_var(name: str) -> bool:
    return name.startswith("OTEL_") or name in {
        "ENABLE_CONSOLE_EXPORTERS",
        "ENABLE_INSTRUMENTATION",
        "ENABLE_SENSITIVE_DATA",
    }
