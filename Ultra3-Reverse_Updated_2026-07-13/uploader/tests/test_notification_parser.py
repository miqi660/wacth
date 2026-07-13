import pytest

from ultra3_uploader.notification_parser import parse_notification


@pytest.mark.parametrize(
    ("hex_data", "command", "field", "value"),
    [
        ("BC7203021E001E", "72", "countdown", 30),
        ("BCD103010202", "D1", "ready_code", 2),
        ("BCC80307012C990D00230F05", "C8", "file_size", 891180),
        ("BCCA030300000000", "CA", "status_hex", "000000"),
    ],
)
def test_parse_confirmed_notifications(
    hex_data: str, command: str, field: str, value: object
) -> None:
    record = parse_notification(bytes.fromhex(hex_data))
    assert record.command == command
    assert record.direction == "03"
    assert record.parsed_fields[field] == value
    assert record.valid
    assert record.parse_error is None


def test_unknown_notification_is_preserved() -> None:
    raw = bytes.fromhex("BC4803054B140F00006E")
    record = parse_notification(raw)
    assert record.raw == raw
    assert record.hex == raw.hex().upper()
    assert record.command == "UNKNOWN"
    assert record.parsed_fields == {"observed_command": "48"}
    assert not record.valid
    assert record.parse_error == "未确认的通知命令"


def test_invalid_known_frame_is_not_accepted() -> None:
    record = parse_notification(bytes.fromhex("BC7203021E0000"))
    assert record.command == "72"
    assert not record.valid
    assert "checksum" in (record.parse_error or "")

