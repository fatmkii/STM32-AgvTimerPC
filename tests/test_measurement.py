from decimal import Decimal

import pytest

from agv_timer.measurement import (
    MeasurementModel,
    format_seconds,
    format_timestamp,
    parse_target_seconds,
)
from agv_timer.protocol import MessageKind, ProtocolMessage


def message(kind: MessageKind, timestamp_ms: int) -> ProtocolMessage:
    return ProtocolMessage(kind, timestamp_ms)


def connected_model() -> MeasurementModel:
    model = MeasurementModel()
    model.connect_port("COM3")
    return model


def test_first_event_is_only_a_baseline_and_later_events_create_rows() -> None:
    model = connected_model()
    assert model.process(message(MessageKind.EVENT, 1000))
    assert model.records == ()
    assert model.process(message(MessageKind.EVENT, 1798))
    assert model.records[0].interval_ms == 798
    assert model.records[0].number == 1


def test_start_and_end_split_segments_without_clearing_history() -> None:
    model = connected_model()
    model.process(message(MessageKind.START, 0))
    model.process(message(MessageKind.EVENT, 1000))
    model.process(message(MessageKind.EVENT, 2000))
    model.process(message(MessageKind.END, 2500))
    model.process(message(MessageKind.START, 3000))
    model.process(message(MessageKind.EVENT, 4000))
    model.process(message(MessageKind.EVENT, 5500))

    assert [record.interval_ms for record in model.records] == [1000, 1500]
    assert model.recording is True


def test_event_without_start_is_accepted_but_does_not_change_status() -> None:
    model = connected_model()
    model.process(message(MessageKind.EVENT, 100))
    model.process(message(MessageKind.EVENT, 2100))
    assert model.recording is False
    assert model.records[0].interval_ms == 2000


def test_duplicate_key_is_ignored_but_same_timestamp_different_kind_is_not() -> None:
    model = connected_model()
    assert model.process(message(MessageKind.START, 100))
    assert not model.process(message(MessageKind.START, 100))
    assert model.process(message(MessageKind.EVENT, 100))
    assert model.recording is True


def test_timestamp_rollback_starts_new_mcu_context() -> None:
    model = connected_model()
    model.process(message(MessageKind.START, 1000))
    model.process(message(MessageKind.EVENT, 2000))
    model.process(message(MessageKind.EVENT, 50))
    assert model.recording is False
    assert len(model.records) == 0
    model.process(message(MessageKind.EVENT, 1050))
    assert [record.interval_ms for record in model.records] == [1000]


def test_target_recalculates_existing_rows_and_average_uses_raw_values() -> None:
    model = connected_model()
    model.process(message(MessageKind.EVENT, 0))
    model.process(message(MessageKind.EVENT, 79800))
    model.process(message(MessageKind.EVENT, 160900))
    model.set_target_seconds(Decimal("80.0"))

    assert format_seconds(model.deviation_seconds(model.records[0]), signed=True) == "-0.2"
    assert format_seconds(model.deviation_seconds(model.records[1]), signed=True) == "+1.1"
    assert format_seconds(model.average_interval_seconds) == "80.5"

    model.set_target_seconds(None)
    assert model.deviation_seconds(model.records[0]) is None


def test_clear_resets_rows_and_number_but_keeps_recording_state() -> None:
    model = connected_model()
    model.process(message(MessageKind.START, 0))
    model.process(message(MessageKind.EVENT, 100))
    model.process(message(MessageKind.EVENT, 200))
    model.clear_measurements()
    assert model.records == ()
    assert model.recording is True
    model.process(message(MessageKind.EVENT, 300))
    model.process(message(MessageKind.EVENT, 500))
    assert model.records[0].number == 1


def test_same_port_reconnect_keeps_dedupe_but_resets_baseline() -> None:
    model = connected_model()
    model.process(message(MessageKind.EVENT, 100))
    model.process(message(MessageKind.EVENT, 200))
    model.disconnect_port()
    model.connect_port("COM3")
    assert not model.process(message(MessageKind.EVENT, 200))
    model.process(message(MessageKind.EVENT, 300))
    assert len(model.records) == 1


def test_formatting_and_target_validation() -> None:
    assert format_timestamp(24 * 60 * 60 * 1000 + 5 * 60 * 1000 + 12300) == "24:05:12.3"
    assert format_seconds(Decimal("79.8") - Decimal("80.0"), signed=True) == "-0.2"
    assert format_seconds(Decimal("0.001"), signed=True) == "0.0"
    assert parse_target_seconds("") is None
    assert parse_target_seconds("80.0") == Decimal("80.0")
    with pytest.raises(ValueError):
        parse_target_seconds("0")
