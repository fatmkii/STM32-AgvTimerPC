import csv

from agv_timer.export import CSV_HEADER, write_csv
from agv_timer.measurement import MeasurementModel
from agv_timer.protocol import MessageKind, ProtocolMessage


def test_csv_contains_only_measurement_columns(tmp_path) -> None:
    model = MeasurementModel()
    model.connect_port("COM3")
    model.process(ProtocolMessage(MessageKind.EVENT, 0))
    model.process(ProtocolMessage(MessageKind.EVENT, 79800))

    destination = tmp_path / "measurements.csv"
    write_csv(destination, model)
    with destination.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))

    assert rows == [
        list(CSV_HEADER),
        ["01", "00:01:19.8", "79.8", "--"],
    ]
