from decimal import Decimal

from agv_timer.main_window import MainWindow
from agv_timer.protocol import MessageKind, ProtocolMessage


def test_main_window_initializes_with_available_ports(qtbot) -> None:
    window = MainWindow(port_provider=lambda: ["COM3", "COM4"])
    qtbot.addWidget(window)

    assert window.port_combo.currentData() == "COM3"
    assert window.connection_status.text() == "未连接"
    assert window.recording_status.text() == "停止中"
    assert window.table.rowCount() == 0


def test_gui_updates_rows_and_recalculates_deviation(qtbot) -> None:
    window = MainWindow(port_provider=lambda: ["COM3"])
    qtbot.addWidget(window)
    window._connected = True
    window.model.connect_port("COM3")

    window._message_received(ProtocolMessage(MessageKind.EVENT, 0))
    window._message_received(ProtocolMessage(MessageKind.EVENT, 79800))
    assert window.table.rowCount() == 1
    assert window.table.item(0, 2).text() == "79.8"
    assert window.table.item(0, 3).text() == "--"

    window.target_input.setText("80.0")
    assert window.table.item(0, 3).text() == "-0.2"
    assert window.model.target_seconds == Decimal("80.0")
