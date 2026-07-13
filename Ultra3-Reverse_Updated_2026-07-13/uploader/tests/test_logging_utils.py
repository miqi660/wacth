import json
from pathlib import Path

from ultra3_uploader.constants import FF03_UUID
from ultra3_uploader.logging_utils import Stage5Logger, redact_device_id
from ultra3_uploader.notification_parser import parse_notification
from ultra3_uploader.upload_state import UploadState


def test_jsonl_notification_keeps_full_device_id(tmp_path: Path) -> None:
    path = tmp_path / "notifications.jsonl"
    logger = Stage5Logger(path, human_output=False)
    logger.notification(
        parse_notification(bytes.fromhex("BC7203021E001E")),
        state=UploadState.LISTENING,
        device_id="26:05:09:12:00:08",
        uuid=FF03_UUID,
    )

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["event"] == "notification"
    assert record["direction"] == "RX"
    assert record["state"] == "LISTENING"
    assert record["device_id"] == "26:05:09:12:00:08"
    assert record["uuid"] == FF03_UUID
    assert record["length"] == 7
    assert record["hex"] == "BC7203021E001E"
    assert record["command"] == "72"


def test_terminal_device_id_redaction() -> None:
    assert redact_device_id("26:05:09:12:00:08").endswith("0:08")
    assert redact_device_id("26:05:09:12:00:08") != "26:05:09:12:00:08"

