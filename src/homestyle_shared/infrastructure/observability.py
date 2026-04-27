from typing import Protocol
from uuid import uuid4

import structlog


class StructuredLogger(Protocol):
    def bind(self, **new_values: object) -> "StructuredLogger": ...

    def info(self, event: str, **event_kw: object) -> object: ...


def build_logger(name: str) -> StructuredLogger:
    return structlog.get_logger(name)


def bind_correlation_id(
    logger: StructuredLogger,
    correlation_id: str | None = None,
) -> tuple[StructuredLogger, str]:
    resolved_correlation_id = correlation_id or str(uuid4())
    return logger.bind(correlation_id=resolved_correlation_id), resolved_correlation_id
