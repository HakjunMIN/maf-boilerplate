import logging
import sys
from typing import Protocol
from uuid import uuid4

import structlog

_AZURE_MONITOR_CONNECTION_STRING: str | None = None


class StructuredLogger(Protocol):
    def bind(self, **new_values: object) -> "StructuredLogger": ...

    def info(self, event: str, **event_kw: object) -> object: ...


def configure_observability(
    *,
    log_level: str = "INFO",
    application_insights_connection_string: str | None = None,
) -> None:
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
