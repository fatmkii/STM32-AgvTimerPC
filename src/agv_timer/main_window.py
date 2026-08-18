"""Main PySide6 window for the AGV interval measurement tool."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QRegularExpression, Qt, Signal
from PySide6.QtGui import QCloseEvent, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from serial.tools import list_ports

from .export import write_csv
from .measurement import (
    MeasurementModel,
    format_seconds,
    format_timestamp,
    parse_target_seconds,
)
from .protocol import ProtocolMessage
from .serial_worker import SerialReader


PortProvider = Callable[[], list[str]]
ReaderFactory = Callable[[str, QWidget], SerialReader]


def available_ports() -> list[str]:
    return sorted(info.device for info in list_ports.comports())


class PortComboBox(QComboBox):
    about_to_show = Signal()

    def showPopup(self) -> None:  # noqa: N802 - Qt method name
        self.about_to_show.emit()
        super().showPopup()


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        port_provider: PortProvider | None = None,
        reader_factory: ReaderFactory = SerialReader,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = MeasurementModel()
        self._port_provider = port_provider or available_ports
        self._reader_factory = reader_factory
        self._reader: SerialReader | None = None
        self._connected = False
        self._connecting = False
        self._closing = False
        self._target_valid = True

        self.setWindowTitle("AGV 节拍测量")
        self.setMinimumSize(760, 500)
        self.resize(960, 620)
        self._build_ui()
        self._refresh_ports()
        self._refresh_view()

    @property
    def model(self) -> MeasurementModel:
        return self._model

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("AGV 节拍测量")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch()

        header.addWidget(QLabel("COM"))
        self.port_combo = PortComboBox()
        self.port_combo.setObjectName("portCombo")
        self.port_combo.setMinimumWidth(120)
        self.port_combo.about_to_show.connect(self._refresh_ports)
        header.addWidget(self.port_combo)

        self.connection_status = QLabel("未连接")
        self.connection_status.setObjectName("connectionStatus")
        header.addWidget(self.connection_status)

        self.connect_button = QPushButton("连接")
        self.connect_button.setObjectName("connectButton")
        self.connect_button.clicked.connect(self._toggle_connection)
        header.addWidget(self.connect_button)
        root.addLayout(header)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("目标节拍："))
        self.target_input = QLineEdit()
        self.target_input.setObjectName("targetInput")
        self.target_input.setPlaceholderText("未设置")
        self.target_input.setMaximumWidth(110)
        self.target_input.setValidator(
            QRegularExpressionValidator(
                QRegularExpression(r"(?:\d+(?:\.\d*)?|\.\d+)?"), self.target_input
            )
        )
        self.target_input.textChanged.connect(self._target_changed)
        self.target_input.editingFinished.connect(self._target_editing_finished)
        controls.addWidget(self.target_input)
        controls.addWidget(QLabel("s"))
        controls.addSpacing(18)

        controls.addWidget(QLabel("状态："))
        self.recording_status = QLabel("停止中")
        self.recording_status.setObjectName("recordingStatus")
        controls.addWidget(self.recording_status)
        controls.addStretch()

        self.clear_button = QPushButton("清空")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.clicked.connect(self._clear_measurements)
        controls.addWidget(self.clear_button)
        root.addLayout(controls)

        self.table = QTableWidget(0, 4)
        self.table.setObjectName("measurementTable")
        self.table.setHorizontalHeaderLabels(("No.", "时间戳", "节拍(s)", "偏差(s)"))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 110)
        root.addWidget(self.table, stretch=1)

        footer = QHBoxLayout()
        self.summary_label = QLabel("测量次数 0       平均 --")
        self.summary_label.setObjectName("summaryLabel")
        footer.addWidget(self.summary_label)
        footer.addStretch()
        self.save_button = QPushButton("CSV 保存")
        self.save_button.setObjectName("saveButton")
        self.save_button.clicked.connect(self._save_csv)
        footer.addWidget(self.save_button)
        root.addLayout(footer)

    def _refresh_ports(self) -> None:
        if self._connected or self._connecting:
            return

        selected = self.port_combo.currentData()
        try:
            ports = self._port_provider()
        except Exception:
            ports = []

        self.port_combo.blockSignals(True)
        self.port_combo.clear()
        if ports:
            for port in ports:
                self.port_combo.addItem(port, port)
            index = self.port_combo.findData(selected)
            self.port_combo.setCurrentIndex(index if index >= 0 else 0)
        else:
            self.port_combo.addItem("无可用端口", None)
            self.port_combo.setCurrentIndex(0)
        self.port_combo.blockSignals(False)
        self.connect_button.setEnabled(bool(self.port_combo.currentData()))

    def _toggle_connection(self) -> None:
        if self._connected or self._connecting:
            self._disconnect_reader()
            return

        port = self.port_combo.currentData()
        if not port:
            QMessageBox.information(self, "提示", "请先选择 COM 端口。")
            return

        self._connecting = True
        self.connect_button.setText("连接中…")
        self.connect_button.setEnabled(False)
        self.port_combo.setEnabled(False)
        reader = self._reader_factory(str(port), self)
        self._reader = reader
        reader.opened.connect(self._reader_opened)
        reader.message_received.connect(self._message_received)
        reader.error.connect(self._reader_error)
        reader.closed.connect(self._reader_closed)
        reader.finished.connect(reader.deleteLater)
        reader.start()

    def _reader_opened(self) -> None:
        reader = self.sender()
        if reader is not self._reader:
            return
        port = getattr(reader, "port", None)
        if not port:
            return
        self._model.connect_port(str(port))
        self._connected = True
        self._connecting = False
        self.connection_status.setText("已连接")
        self.connection_status.setStyleSheet("color: #2e7d32; font-weight: 600;")
        self.connect_button.setText("断开")
        self.connect_button.setEnabled(True)
        self.port_combo.setEnabled(False)
        self._refresh_view()

    def _reader_error(self, message: str) -> None:
        if self._closing:
            return
        QMessageBox.warning(self, "串口错误", message or "串口连接失败。")

    def _reader_closed(self) -> None:
        reader = self.sender()
        if reader is not self._reader:
            return
        self._finish_reader_state()

    def _disconnect_reader(self) -> None:
        reader = self._reader
        if reader is not None:
            reader.requestInterruption()
            reader.wait(2000)
        self._finish_reader_state()

    def _finish_reader_state(self) -> None:
        self._reader = None
        self._connected = False
        self._connecting = False
        self._model.disconnect_port()
        self.connection_status.setText("未连接")
        self.connection_status.setStyleSheet("color: #757575; font-weight: 600;")
        self.connect_button.setText("连接")
        self.port_combo.setEnabled(True)
        self._refresh_ports()
        self._refresh_view()

    def _message_received(self, message: object) -> None:
        if not self._connected or not isinstance(message, ProtocolMessage):
            return
        accepted = self._model.process(message)
        if accepted:
            self._refresh_view()

    def _target_changed(self, text: str) -> None:
        try:
            target = parse_target_seconds(text)
        except ValueError:
            self._target_valid = False
            self._model.set_target_seconds(None)
            self.target_input.setStyleSheet("border: 1px solid #c62828;")
        else:
            self._target_valid = True
            self._model.set_target_seconds(target)
            self.target_input.setStyleSheet("")
        self._refresh_view()

    def _target_editing_finished(self) -> None:
        if not self._target_valid:
            self.target_input.clear()

    def _clear_measurements(self) -> None:
        self._model.clear_measurements()
        self._refresh_view()

    def _refresh_view(self) -> None:
        self.recording_status.setText("测量中" if self._model.recording else "停止中")
        self.recording_status.setStyleSheet(
            "color: #2e7d32; font-weight: 600;"
            if self._model.recording
            else "color: #757575; font-weight: 600;"
        )

        self.table.setRowCount(0)
        for record in self._model.records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = (
                f"{record.number:02d}",
                format_timestamp(record.timestamp_ms),
                format_seconds(Decimal(record.interval_ms) / Decimal(1000)),
                format_seconds(self._model.deviation_seconds(record), signed=True),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        if self.table.rowCount():
            self.table.scrollToBottom()

        average = format_seconds(self._model.average_interval_seconds)
        self.summary_label.setText(
            f"测量次数 {len(self._model.records)}       平均 {average} s"
        )
        self.save_button.setEnabled(bool(self._model.records))

    def _save_csv(self) -> None:
        if not self._model.records:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "保存 CSV",
            str(Path.cwd() / "agv_measurements.csv"),
            "CSV 文件 (*.csv);;所有文件 (*)",
        )
        if not path:
            return
        try:
            write_csv(path, self._model)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt method name
        self._closing = True
        self._disconnect_reader()
        event.accept()
