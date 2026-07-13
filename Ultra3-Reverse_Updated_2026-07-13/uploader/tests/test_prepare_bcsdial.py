from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from ultra3_uploader.bcsdial import BCSDIALPayload
from ultra3_uploader.checksum import c8_checksum
from ultra3_uploader.cli import main
from ultra3_uploader.constants import FF02_UUID, FF03_UUID
from ultra3_uploader.errors import (
    BleDisconnectedError,
    C8ResponseMismatchError,
    CountdownError,
    PrepareTimeoutError,
)
from ultra3_uploader.fake_transport import FakeBleTransport
from ultra3_uploader.logging_utils import Stage5Logger
from ultra3_uploader.prepare_bcsdial import EXPECTED_COUNTDOWN, run_prepare_bcsdial
from ultra3_uploader.upload_state import UploadState


def payload(size: int = 500) -> BCSDIALPayload:
    return BCSDIALPayload(b"BCSDIAL" + b"\x00" * (size - 11) + b"BCBC")


def bc72(value: int) -> bytes:
    return bytes.fromhex(f"BC720302{value:02X}00{value:02X}")


def c8_response(
    value: BCSDIALPayload,
    *,
    file_size: int | None = None,
    packet_count: int | None = None,
) -> bytes:
    frame = bytearray(value.build_prepare_frame())
    frame[2] = 0x03
    if file_size is not None:
        frame[5:9] = file_size.to_bytes(4, "little")
    if packet_count is not None:
        frame[9:11] = packet_count.to_bytes(2, "little")
    frame[-1] = c8_checksum(frame[4], bytes(frame[5:9]), bytes(frame[9:11]))
    return bytes(frame)


def normal_notifications(value: BCSDIALPayload) -> list[bytes]:
    return (
        [bc72(count) for count in EXPECTED_COUNTDOWN]
        + [bytes.fromhex("BCD103010202")]
        + [c8_response(value)]
    )


def run_prepare(
    transport: FakeBleTransport,
    value: BCSDIALPayload,
    *,
    timeout: float = 0.05,
    logger: Stage5Logger | None = None,
):
    return asyncio.run(run_prepare_bcsdial(
        transport,
        value,
        device_id="FAKE-ULTRA3-1",
        ready_timeout=timeout,
        connect_timeout=1,
        logger=logger or Stage5Logger(human_output=False),
    ))


def test_normal_prepare_sends_only_one_c8() -> None:
    value = payload()
    transport = FakeBleTransport(notifications_on_write=normal_notifications(value))
    result = run_prepare(transport, value)

    expected_c8 = value.build_prepare_frame()
    assert result.countdown == EXPECTED_COUNTDOWN
    assert result.d1_received
    assert result.c8_response_matched
    assert result.ff02_write_count == 1
    assert result.c9_write_count == 0
    assert result.ca_write_count == 0
    assert result.final_state is UploadState.COMPLETE
    assert transport.writes == [(FF02_UUID, expected_c8)]
    assert transport.notify_subscriptions == [FF03_UUID]
    assert transport.notify_unsubscriptions == [FF03_UUID]
    assert transport.disconnect_calls == 1
    assert not transport.is_connected


def test_golden_size_generates_confirmed_c8() -> None:
    value = payload(891180)
    assert value.build_prepare_frame().hex().upper() == "BCC80207012C990D00230F05"


def test_unknown_notification_is_logged_and_ignored() -> None:
    value = payload()
    notifications = normal_notifications(value)
    notifications.insert(10, bytes.fromhex("BC4803054B140F00006E"))
    logger = Stage5Logger(human_output=False)
    result = run_prepare(
        FakeBleTransport(notifications_on_write=notifications),
        value,
        logger=logger,
    )
    assert result.c8_response_matched
    unknown = [record for record in logger.records if record.get("command") == "UNKNOWN"]
    assert unknown[0]["hex"] == "BC4803054B140F00006E"


def test_missing_bc72_fails() -> None:
    value = payload()
    transport = FakeBleTransport(
        notifications_on_write=[bytes.fromhex("BCD103010202")]
    )
    with pytest.raises(CountdownError, match="BC72 countdown 缺失"):
        run_prepare(transport, value)
    assert transport.writes == [(FF02_UUID, value.build_prepare_frame())]


def test_countdown_out_of_order_fails() -> None:
    value = payload()
    transport = FakeBleTransport(notifications_on_write=[bc72(30), bc72(28)])
    with pytest.raises(CountdownError, match="乱序"):
        run_prepare(transport, value)


def test_d1_timeout_after_full_countdown() -> None:
    value = payload()
    transport = FakeBleTransport(
        notifications_on_write=[bc72(count) for count in EXPECTED_COUNTDOWN]
    )
    with pytest.raises(PrepareTimeoutError, match="D1 ready 超时"):
        run_prepare(transport, value, timeout=0.01)


def test_c8_response_timeout() -> None:
    value = payload()
    transport = FakeBleTransport(
        notifications_on_write=(
            [bc72(count) for count in EXPECTED_COUNTDOWN]
            + [bytes.fromhex("BCD103010202")]
        )
    )
    with pytest.raises(PrepareTimeoutError, match="C8 response 超时"):
        run_prepare(transport, value, timeout=0.01)


def test_c8_response_file_size_mismatch() -> None:
    value = payload()
    notifications = normal_notifications(value)
    notifications[-1] = c8_response(value, file_size=value.size + 1)
    with pytest.raises(C8ResponseMismatchError, match="文件大小不匹配"):
        run_prepare(FakeBleTransport(notifications_on_write=notifications), value)


def test_c8_response_packet_count_mismatch() -> None:
    value = payload()
    notifications = normal_notifications(value)
    notifications[-1] = c8_response(value, packet_count=value.packet_count + 1)
    with pytest.raises(C8ResponseMismatchError, match="包数不匹配"):
        run_prepare(FakeBleTransport(notifications_on_write=notifications), value)


def test_mid_prepare_disconnect() -> None:
    value = payload()
    transport = FakeBleTransport(disconnect_on_write=True)
    with pytest.raises(BleDisconnectedError, match="连接断开"):
        run_prepare(transport, value)
    assert not transport.is_connected
    assert len(transport.writes) == 1


def test_user_cancellation_stops_notify_and_disconnects() -> None:
    value = payload()
    transport = FakeBleTransport()
    logger = Stage5Logger(human_output=False)

    async def scenario() -> None:
        task = asyncio.create_task(run_prepare_bcsdial(
            transport,
            value,
            device_id="FAKE-ULTRA3-1",
            ready_timeout=60,
            connect_timeout=1,
            logger=logger,
        ))
        while not transport.writes:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert transport.notify_unsubscriptions == [FF03_UUID]
    assert transport.disconnect_calls == 1
    assert not transport.is_connected
    assert len(transport.writes) == 1
    assert any(record["state"] == "CANCELLED" for record in logger.records)


def test_dry_run_does_not_require_device_or_start_ble(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "watchface.bin"
    value = payload()
    path.write_bytes(value.data)
    assert main(["prepare-bcsdial", "--file", str(path), "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert f"文件大小: {value.size}" in output
    assert f"包数: {value.packet_count}" in output
    assert f"C8 HEX: {value.build_prepare_frame().hex().upper()}" in output
    assert "FF02 writes: 0" in output

