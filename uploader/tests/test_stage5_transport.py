from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from ultra3_uploader.ble_transport import BleDevice, GattCharacteristic, GattSnapshot
from ultra3_uploader.constants import FF02_UUID, FF03_UUID, TARGET_SERVICE_UUID
from ultra3_uploader.errors import (
    BleDisconnectedError,
    BleTransportError,
    DeviceNotFoundError,
    GattValidationError,
    MultipleDevicesError,
)
from ultra3_uploader.fake_transport import FakeBleTransport, default_snapshot
from ultra3_uploader.logging_utils import Stage5Logger
from ultra3_uploader.stage5 import (
    run_info,
    run_listen,
    run_scan,
    select_device,
    validate_gatt,
)


def run(coroutine):
    return asyncio.run(coroutine)


def logger() -> Stage5Logger:
    return Stage5Logger(human_output=False)


def test_scan_single_device() -> None:
    transport = FakeBleTransport()
    result = run(run_scan(transport, timeout=2, target_name="ULTRA 3", logger=logger()))
    assert result.matching_count == 1
    assert result.devices[0].device_id == "FAKE-ULTRA3-1"


def test_multiple_same_name_requires_device_id() -> None:
    devices = [
        BleDevice("ID-1", "ULTRA 3"),
        BleDevice("ID-2", "ULTRA 3"),
    ]
    result = run(run_scan(
        FakeBleTransport(devices=devices), timeout=0, target_name="ULTRA 3", logger=logger()
    ))
    assert result.matching_count == 2
    with pytest.raises(MultipleDevicesError, match="指定设备 ID"):
        select_device(list(result.devices), target_name="ULTRA 3")
    assert select_device(list(result.devices), target_name="ULTRA 3", device_id="ID-2").device_id == "ID-2"


def test_scan_without_target_device() -> None:
    result = run(run_scan(
        FakeBleTransport(devices=[]), timeout=0, target_name="ULTRA 3", logger=logger()
    ))
    assert result.matching_count == 0
    with pytest.raises(DeviceNotFoundError):
        select_device([], target_name="ULTRA 3")


def test_scan_backend_timeout() -> None:
    transport = FakeBleTransport(scan_error="模拟扫描超时")
    with pytest.raises(BleTransportError, match="模拟扫描超时"):
        run(run_scan(transport, timeout=0.01, target_name="ULTRA 3", logger=logger()))


def test_connection_failure_does_not_write() -> None:
    transport = FakeBleTransport(connect_error="模拟连接失败")
    with pytest.raises(BleTransportError, match="模拟连接失败"):
        run(run_info(transport, device_id="ID", timeout=1, logger=logger()))
    assert transport.writes == []
    assert not transport.is_connected


def test_missing_service_is_reported_and_connection_is_released() -> None:
    snapshot = GattSnapshot(TARGET_SERVICE_UUID, False, None, None, platform="fake")
    transport = FakeBleTransport(snapshot=snapshot)
    result = run(run_info(transport, device_id="ID", timeout=1, logger=logger()))
    assert not result.validation.service_found
    assert result.disconnected
    assert transport.disconnect_calls == 1
    assert transport.writes == []


@pytest.mark.parametrize(("missing", "attribute"), [("ff02", "ff02_found"), ("ff03", "ff03_found")])
def test_missing_characteristic_is_reported(missing: str, attribute: str) -> None:
    snapshot = default_snapshot()
    snapshot = replace(snapshot, **{missing: None})
    transport = FakeBleTransport(snapshot=snapshot)
    result = run(run_info(transport, device_id="ID", timeout=1, logger=logger()))
    assert not getattr(result.validation, attribute)
    assert result.disconnected
    assert transport.writes == []


def test_ff02_property_error() -> None:
    snapshot = replace(
        default_snapshot(),
        ff02=GattCharacteristic(FF02_UUID, frozenset({"write"}), 244),
    )
    validation = validate_gatt(snapshot)
    assert validation.ff02_found
    assert not validation.ff02_write_without_response


def test_ff03_property_error() -> None:
    snapshot = replace(
        default_snapshot(),
        ff03=GattCharacteristic(FF03_UUID, frozenset({"read"})),
    )
    validation = validate_gatt(snapshot)
    assert validation.ff03_found
    assert not validation.ff03_notify


def test_gatt_identity_is_validated_by_uuid_not_handle() -> None:
    snapshot = replace(
        default_snapshot(),
        ff02=GattCharacteristic(
            "00000062-0000-1000-8000-00805f9b34fb",
            frozenset({"write-without-response"}),
            244,
            handle=0x0062,
        ),
    )
    validation = validate_gatt(snapshot)
    assert not validation.ff02_found


def test_below_237_capacity_blocks_listen_without_write() -> None:
    snapshot = replace(
        default_snapshot(),
        ff02=GattCharacteristic(FF02_UUID, frozenset({"write-without-response"}), 236),
    )
    transport = FakeBleTransport(snapshot=snapshot)
    with pytest.raises(GattValidationError, match="below 237"):
        run(run_listen(
            transport, device_id="ID", seconds=0, timeout=1, logger=logger()
        ))
    assert transport.disconnect_calls == 1
    assert transport.writes == []


def test_unknown_capacity_is_explicit_but_does_not_fake_a_value() -> None:
    snapshot = replace(
        default_snapshot(),
        ff02=GattCharacteristic(FF02_UUID, frozenset({"write-without-response"}), None),
    )
    result = run(run_info(
        FakeBleTransport(snapshot=snapshot), device_id="ID", timeout=1, logger=logger()
    ))
    assert result.validation.maximum_write_without_response is None
    assert result.validation.required_gatt_ok


def test_listen_subscribes_receives_and_unsubscribes_without_ff02_write() -> None:
    notifications = [
        bytes.fromhex("BC7203021E001E"),
        bytes.fromhex("BCD103010202"),
        bytes.fromhex("BCC80307012C990D00230F05"),
        bytes.fromhex("BCCA030300000000"),
    ]
    transport = FakeBleTransport(notifications_on_subscribe=notifications)
    result = run(run_listen(
        transport, device_id="ID", seconds=0, timeout=1, logger=logger()
    ))
    assert result.notifications == 4
    assert transport.notify_subscriptions == [FF03_UUID]
    assert transport.notify_unsubscriptions == [FF03_UUID]
    assert transport.disconnect_calls == 1
    assert transport.writes == []


def test_notify_subscription_failure_releases_connection() -> None:
    transport = FakeBleTransport(notify_error="模拟订阅失败")
    with pytest.raises(BleTransportError, match="模拟订阅失败"):
        run(run_listen(
            transport, device_id="ID", seconds=0, timeout=1, logger=logger()
        ))
    assert transport.disconnect_calls == 1
    assert not transport.is_connected
    assert transport.writes == []


def test_remote_disconnect_wakes_listener() -> None:
    transport = FakeBleTransport(disconnect_on_subscribe=True)
    with pytest.raises(BleDisconnectedError, match="连接断开"):
        run(run_listen(
            transport, device_id="ID", seconds=60, timeout=1, logger=logger()
        ))
    assert not transport.is_connected
    assert transport.writes == []


def test_cancelled_listener_unsubscribes_and_disconnects() -> None:
    transport = FakeBleTransport()

    async def scenario() -> None:
        task = asyncio.create_task(run_listen(
            transport, device_id="ID", seconds=60, timeout=1, logger=logger()
        ))
        while not transport.notify_subscriptions:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())
    assert transport.notify_unsubscriptions == [FF03_UUID]
    assert transport.disconnect_calls == 1
    assert not transport.is_connected
    assert transport.writes == []


def test_info_and_listen_never_call_write_interface() -> None:
    transport = FakeBleTransport()
    run(run_info(transport, device_id="ID", timeout=1, logger=logger()))
    run(run_listen(transport, device_id="ID", seconds=0, timeout=1, logger=logger()))
    assert transport.writes == []
    assert transport.write_order == []
    assert transport.write_timestamps == []


def test_fake_write_interface_records_order_and_timestamps() -> None:
    transport = FakeBleTransport()

    async def scenario() -> None:
        await transport.connect("ID", 1)
        await transport.write_without_response(FF02_UUID, b"one")
        await transport.write_without_response(FF02_UUID, b"two")
        await transport.disconnect()

    run(scenario())
    assert transport.writes == [(FF02_UUID, b"one"), (FF02_UUID, b"two")]
    assert transport.write_order == [0, 1]
    assert len(transport.write_timestamps) == 2
