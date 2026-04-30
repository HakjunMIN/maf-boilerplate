import pytest

from homestyle_shared.infrastructure.observability import build_logger, configure_observability


def test_configure_observability_emits_json_logs(capsys: pytest.CaptureFixture[str]) -> None:
    configure_observability(log_level="DEBUG")

    logger = build_logger("test_logger").bind(correlation_id="corr-123")
    logger.info("test_event", value=1)

    output = capsys.readouterr().out
    assert '"event": "test_event"' in output
    assert '"value": 1' in output
    assert '"correlation_id": "corr-123"' in output
    assert '"logger": "test_logger"' in output


def test_configure_observability_initializes_azure_monitor(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_connection_strings: list[str] = []

    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._AZURE_MONITOR_CONNECTION_STRING",
        None,
    )
    monkeypatch.setattr(
        "homestyle_shared.infrastructure.observability._configure_azure_monitor",
        captured_connection_strings.append,
    )

    configure_observability(
        log_level="INFO",
        application_insights_connection_string="InstrumentationKey=test",
    )

    assert captured_connection_strings == ["InstrumentationKey=test"]