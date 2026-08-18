import time

import agv_timer.serial_worker as serial_worker
from agv_timer.protocol import MessageKind


class FakeSerial:
    instances: list["FakeSerial"] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.is_open = True
        self._sent = False
        self.instances.append(self)

    def read(self, _size: int) -> bytes:
        if not self._sent:
            self._sent = True
            return b"START,1\r\nEVENT,2\r\n"
        time.sleep(0.001)
        return b""

    def close(self) -> None:
        self.is_open = False


def test_serial_reader_uses_fixed_settings_and_emits_messages(qtbot, monkeypatch) -> None:
    FakeSerial.instances.clear()
    monkeypatch.setattr(serial_worker.serial, "Serial", FakeSerial)
    reader = serial_worker.SerialReader("COM3")
    messages = []
    reader.message_received.connect(messages.append)

    reader.start()
    qtbot.waitUntil(lambda: len(messages) == 2, timeout=1000)
    reader.requestInterruption()
    qtbot.waitSignal(reader.closed, timeout=1000)
    reader.wait(1000)

    assert [message.kind for message in messages] == [MessageKind.START, MessageKind.EVENT]
    assert FakeSerial.instances[0].kwargs == {
        "port": "COM3",
        "baudrate": 115200,
        "bytesize": serial_worker.serial.EIGHTBITS,
        "parity": serial_worker.serial.PARITY_NONE,
        "stopbits": serial_worker.serial.STOPBITS_ONE,
        "timeout": 0.2,
    }
