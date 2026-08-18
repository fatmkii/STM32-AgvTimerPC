"""Parser for the line-oriented STM32 USB CDC protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


MAX_TIMESTAMP = (1 << 64) - 1
MAX_BUFFER_BYTES = 64 * 1024


class MessageKind(StrEnum):
    START = "START"
    END = "END"
    EVENT = "EVENT"


@dataclass(frozen=True, slots=True)
class ProtocolMessage:
    kind: MessageKind
    timestamp_ms: int


def parse_frame(frame: bytes) -> ProtocolMessage | None:
    """Parse one complete CRLF-terminated frame.

    Invalid frames are deliberately ignored. USB CDC can contain partial or
    unrelated bytes, and a bad line must not prevent subsequent valid lines
    from being processed.
    """

    if not frame.endswith(b"\r\n"):
        return None

    payload = frame[:-2]
    fields = payload.split(b",")
    if len(fields) != 2:
        return None

    try:
        kind_text = fields[0].decode("ascii")
        timestamp_text = fields[1].decode("ascii")
    except UnicodeDecodeError:
        return None

    try:
        kind = MessageKind(kind_text)
    except ValueError:
        return None

    if not timestamp_text or not timestamp_text.isascii() or not timestamp_text.isdecimal():
        return None

    timestamp_ms = int(timestamp_text, 10)
    if timestamp_ms > MAX_TIMESTAMP:
        return None
    return ProtocolMessage(kind=kind, timestamp_ms=timestamp_ms)


class LineParser:
    """Incrementally parse arbitrary chunks of USB CDC data."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[ProtocolMessage]:
        if data:
            self._buffer.extend(data)

        messages: list[ProtocolMessage] = []
        while True:
            line_end = self._buffer.find(b"\n")
            if line_end < 0:
                break

            frame = bytes(self._buffer[: line_end + 1])
            del self._buffer[: line_end + 1]
            message = parse_frame(frame)
            if message is not None:
                messages.append(message)

        if len(self._buffer) > MAX_BUFFER_BYTES:
            del self._buffer[:-MAX_BUFFER_BYTES]
        return messages
