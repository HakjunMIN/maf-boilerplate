import os
import logging

import pytest

from homestyle_shared.infrastructure.observability import (
    build_logger,
    configure_process_observability,
    start_request_span,
)


@pytest.fixture(autouse=True)
def isolate_observability_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ENABLE_CONSOLE_EXPORTERS",
        "ENABLE_INSTRUMENTATION",
        "ENABLE_SENSITIVE_DATA",
        "AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING",
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
        "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
        "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AGENT_FRAMEWORK_OTEL_CONFIGURED",
        False,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AGENT_FRAMEWORK_INSTRUMENTATION_ENABLED",
        False,
    )


def test_configure_process_observability_emits_json_logs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_process_observability(log_level="DEBUG")

    logger = build_logger("test_logger").bind(correlation_id="corr-123")
    logger.info("test_event", value=1)

    output = capsys.readouterr().out
    assert '"event": "test_event"' in output
    assert '"value": 1' in output
    assert '"correlation_id": "corr-123"' in output
    assert '"logger": "test_logger"' in output


def test_configure_process_observability_quiets_azure_sdk_http_logs() -> None:
    azure_logger = logging.getLogger("azure")
    original_level = azure_logger.level
    try:
        azure_logger.setLevel(logging.NOTSET)

        configure_process_observability(log_level="INFO")

        assert azure_logger.level == logging.WARNING
    finally:
        azure_logger.setLevel(original_level)


def test_configure_process_observability_initializes_azure_monitor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_connection_strings: list[str] = []

    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AZURE_MONITOR_CONNECTION_STRING",
        None,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._configure_azure_monitor",
        captured_connection_strings.append,
    )

    configure_process_observability(
        log_level="INFO",
        application_insights_connection_string="InstrumentationKey=test",
    )

    assert captured_connection_strings == ["InstrumentationKey=test"]


def test_configure_process_observability_enables_agent_framework_instrumentation_for_app_insights(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AZURE_MONITOR_CONNECTION_STRING",
        None,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._configure_azure_monitor",
        lambda _: calls.append("azure_monitor"),
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._enable_agent_framework_instrumentation",
        calls.append,
    )

    configure_process_observability(
        application_insights_connection_string="InstrumentationKey=test",
    )
    configure_process_observability(
        application_insights_connection_string="InstrumentationKey=test",
    )

    assert calls == ["azure_monitor", False]


def test_configure_process_observability_passes_sensitive_data_env_to_agent_framework(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_sensitive_data_values: list[bool] = []

    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AZURE_MONITOR_CONNECTION_STRING",
        None,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._configure_azure_monitor",
        lambda _: None,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._enable_agent_framework_instrumentation",
        captured_sensitive_data_values.append,
    )

    configure_process_observability(
        application_insights_connection_string="InstrumentationKey=test",
        env={"ENABLE_SENSITIVE_DATA": "true"},
    )

    assert captured_sensitive_data_values == [True]


def test_configure_process_observability_rejects_app_insights_with_otlp_exporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    with pytest.raises(ValueError, match="APPLICATION_INSIGHTS_CONNECTION_STRING"):
        configure_process_observability(
            application_insights_connection_string="InstrumentationKey=test",
        )


def test_configure_process_observability_configures_agent_framework_otel_for_otlp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AGENT_FRAMEWORK_OTEL_CONFIGURED",
        False,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._configure_agent_framework_otel_providers",
        lambda: calls.append("configure_otel_providers"),
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._attach_application_otel_logging_handler",
        lambda _: calls.append("attach_application_logging"),
    )

    configure_process_observability()

    assert calls == ["configure_otel_providers", "attach_application_logging"]


def test_configure_process_observability_applies_otlp_values_from_dotenv_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    monkeypatch.delenv("ENABLE_INSTRUMENTATION", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AGENT_FRAMEWORK_OTEL_CONFIGURED",
        False,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._configure_agent_framework_otel_providers",
        lambda: calls.append("configure_otel_providers"),
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._attach_application_otel_logging_handler",
        lambda _: calls.append("attach_application_logging"),
    )

    configure_process_observability(
        env={
            "ENABLE_INSTRUMENTATION": "true",
            "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
        },
    )

    assert calls == ["configure_otel_providers", "attach_application_logging"]
    assert os.environ["ENABLE_INSTRUMENTATION"] == "true"
    assert os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://localhost:4317"


def test_configure_process_observability_applies_azure_monitor_genai_trace_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", raising=False)
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AZURE_MONITOR_CONNECTION_STRING",
        None,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._configure_azure_monitor",
        lambda _: None,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._enable_agent_framework_instrumentation",
        lambda _: None,
    )

    configure_process_observability(
        application_insights_connection_string="InstrumentationKey=test",
        env={"AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING": "true"},
    )

    assert os.environ["AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING"] == "true"


def test_attach_application_otel_logging_handler_adds_one_root_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from homestyle_shared.infrastructure.observability import (
        _ApplicationTelemetryLogFilter,
        _APPLICATION_OTEL_LOGGING_HANDLER_MARKER,
        _attach_application_otel_logging_handler,
    )

    captured_providers: list[object] = []
    fake_provider = object()

    class FakeLoggingHandler(logging.Handler):
        def __init__(self, *, level: int, logger_provider: object) -> None:
            super().__init__(level)
            captured_providers.append(logger_provider)

    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    root_logger.handlers = []
    monkeypatch.setattr("opentelemetry._logs.get_logger_provider", lambda: fake_provider)
    monkeypatch.setattr("opentelemetry.sdk._logs.LoggingHandler", FakeLoggingHandler)
    try:
        _attach_application_otel_logging_handler(logging.INFO)
        _attach_application_otel_logging_handler(logging.DEBUG)

        marked_handlers = [
            handler
            for handler in root_logger.handlers
            if getattr(handler, _APPLICATION_OTEL_LOGGING_HANDLER_MARKER, False)
        ]
        assert len(marked_handlers) == 1
        assert marked_handlers[0].level == logging.DEBUG
        assert captured_providers == [fake_provider]
        log_filter = next(
            filter_item
            for filter_item in marked_handlers[0].filters
            if isinstance(filter_item, _ApplicationTelemetryLogFilter)
        )
        assert log_filter.filter(logging.LogRecord("app", logging.INFO, "", 1, "", (), None))
        assert not log_filter.filter(
            logging.LogRecord("opentelemetry.exporter", logging.INFO, "", 1, "", (), None)
        )
    finally:
        root_logger.handlers = original_handlers


def test_start_request_span_sets_attributes_and_skips_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    captured_span_names: list[str] = []
    captured_tracer_names: list[str] = []
    set_calls: list[tuple[str, object]] = []

    class FakeSpan:
        def set_attribute(self, key: str, value: object) -> None:
            set_calls.append((key, value))

    class FakeTracer:
        @contextmanager
        def start_as_current_span(self, name: str):
            captured_span_names.append(name)
            yield FakeSpan()

    def fake_get_tracer(name: str) -> FakeTracer:
        captured_tracer_names.append(name)
        return FakeTracer()

    monkeypatch.setattr("opentelemetry.trace.get_tracer", fake_get_tracer)

    with start_request_span(
        "homestyle.agent.answer",
        tracer_name="homestyle_agent.runtime",
        attributes={
            "homestyle.correlation_id": "corr-1",
            "homestyle.session_id": "sess-1",
            "homestyle.skipped": None,
            "homestyle.empty": "",
        },
    ) as span:
        span.set_attribute("homestyle.outcome", "answered")

    assert captured_span_names == ["homestyle.agent.answer"]
    assert captured_tracer_names == ["homestyle_agent.runtime"]
    assert ("homestyle.correlation_id", "corr-1") in set_calls
    assert ("homestyle.session_id", "sess-1") in set_calls
    assert ("homestyle.empty", "") in set_calls
    assert ("homestyle.outcome", "answered") in set_calls
    assert all(key != "homestyle.skipped" for key, _ in set_calls)