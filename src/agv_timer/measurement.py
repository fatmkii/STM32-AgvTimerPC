"""Pure measurement and session state for the AGV timer."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .protocol import MessageKind, ProtocolMessage


_MILLISECONDS_PER_SECOND = Decimal(1000)
_ONE_DECIMAL = Decimal("0.1")


@dataclass(frozen=True, slots=True)
class MeasurementRecord:
    number: int
    timestamp_ms: int
    interval_ms: int


def parse_target_seconds(value: str) -> Decimal | None:
    """Return a positive finite target, or ``None`` for an empty field."""

    text = value.strip()
    if not text:
        return None
    try:
        target = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("目标节拍必须是数字") from exc
    if not target.is_finite() or target <= 0:
        raise ValueError("目标节拍必须大于 0")
    return target


class MeasurementModel:
    """Apply protocol messages and expose the current in-memory measurements."""

    def __init__(self) -> None:
        self._records: list[MeasurementRecord] = []
        self._next_number = 1
        self._target_seconds: Decimal | None = None

        self._current_port: str | None = None
        self._last_connected_port: str | None = None
        self._seen_by_port: dict[str, set[tuple[MessageKind, int]]] = {}
        self._last_timestamp_by_port: dict[str, int] = {}
        self._previous_event_ms: int | None = None
        self.recording = False

    @property
    def records(self) -> tuple[MeasurementRecord, ...]:
        return tuple(self._records)

    @property
    def target_seconds(self) -> Decimal | None:
        return self._target_seconds

    @property
    def current_port(self) -> str | None:
        return self._current_port

    @property
    def average_interval_seconds(self) -> Decimal | None:
        if not self._records:
            return None
        total_ms = sum(record.interval_ms for record in self._records)
        return Decimal(total_ms) / (_MILLISECONDS_PER_SECOND * len(self._records))

    def connect_port(self, port: str) -> None:
        if not port:
            raise ValueError("端口不能为空")

        # A different selected port represents a different device context.
        # A same-port reconnect retains the dedupe history so queued retries
        # cannot create duplicate table rows.
        if self._last_connected_port != port:
            self._seen_by_port[port] = set()
            self._last_timestamp_by_port.pop(port, None)

        self._current_port = port
        self._last_connected_port = port
        self._previous_event_ms = None
        self.recording = False

    def disconnect_port(self) -> None:
        self._current_port = None
        self._previous_event_ms = None
        self.recording = False

    def set_target_seconds(self, target: Decimal | None) -> None:
        if target is not None and (not target.is_finite() or target <= 0):
            raise ValueError("目标节拍必须大于 0")
        self._target_seconds = target

    def clear_measurements(self) -> None:
        self._records.clear()
        self._next_number = 1
        self._previous_event_ms = None

    def process(self, message: ProtocolMessage) -> bool:
        """Apply a message; return ``False`` when it is a duplicate."""

        port = self._current_port
        if port is None:
            raise RuntimeError("尚未连接串口")

        seen = self._seen_by_port.setdefault(port, set())
        key = (message.kind, message.timestamp_ms)
        if key in seen:
            return False

        last_timestamp = self._last_timestamp_by_port.get(port)
        if last_timestamp is not None and message.timestamp_ms < last_timestamp:
            # A timestamp rollback is the only protocol-level indication of a
            # new MCU boot. Preserve visible records but start a fresh context.
            seen.clear()
            self._previous_event_ms = None
            self.recording = False

        seen.add(key)
        self._last_timestamp_by_port[port] = message.timestamp_ms

        if message.kind is MessageKind.START:
            self.recording = True
            self._previous_event_ms = None
        elif message.kind is MessageKind.END:
            self.recording = False
            self._previous_event_ms = None
        else:
            self._process_event(message.timestamp_ms)
        return True

    def _process_event(self, timestamp_ms: int) -> None:
        previous = self._previous_event_ms
        if previous is not None:
            interval_ms = timestamp_ms - previous
            if interval_ms > 0:
                self._records.append(
                    MeasurementRecord(
                        number=self._next_number,
                        timestamp_ms=timestamp_ms,
                        interval_ms=interval_ms,
                    )
                )
                self._next_number += 1
        self._previous_event_ms = timestamp_ms

    def deviation_seconds(self, record: MeasurementRecord) -> Decimal | None:
        if self._target_seconds is None:
            return None
        return Decimal(record.interval_ms) / _MILLISECONDS_PER_SECOND - self._target_seconds


def quantize_one_decimal(value: Decimal) -> Decimal:
    return value.quantize(_ONE_DECIMAL, rounding=ROUND_HALF_UP)


def format_seconds(value: Decimal | None, *, signed: bool = False) -> str:
    if value is None:
        return "--"
    rounded = quantize_one_decimal(value)
    if rounded == 0:
        rounded = Decimal("0.0")
    text = f"{rounded:.1f}"
    if signed and rounded > 0:
        return f"+{text}"
    return text


def format_timestamp(timestamp_ms: int) -> str:
    """Format MCU uptime as cumulative hours, minutes, seconds and tenths."""

    total_tenths = (timestamp_ms + 50) // 100
    total_seconds, tenths = divmod(total_tenths, 10)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{tenths}"
