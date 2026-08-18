"""Background pyserial reader used by the Qt GUI."""

from __future__ import annotations

import serial
from PySide6.QtCore import QObject, QThread, Signal

from .protocol import LineParser


SERIAL_BAUDRATE = 115200


class SerialReader(QThread):
    opened = Signal()
    message_received = Signal(object)
    error = Signal(str)
    closed = Signal()

    def __init__(self, port: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.port = port

    def run(self) -> None:
        connection: serial.Serial | None = None
        parser = LineParser()
        try:
            connection = serial.Serial(
                port=self.port,
                baudrate=SERIAL_BAUDRATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.2,
            )
            if self.isInterruptionRequested():
                return
            self.opened.emit()

            while not self.isInterruptionRequested():
                data = connection.read(4096)
                for message in parser.feed(data):
                    self.message_received.emit(message)
        except (serial.SerialException, OSError) as exc:
            if not self.isInterruptionRequested():
                self.error.emit(str(exc))
        finally:
            if connection is not None and connection.is_open:
                connection.close()
            self.closed.emit()
