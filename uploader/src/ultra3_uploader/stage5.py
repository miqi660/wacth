from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .ble_transport import BleDevice, BleTransport, GattSnapshot
from .constants import (
    FF02_UUID,
    FF03_UUID,
    REQUIRED_WRITE_WITHOUT_RESPONSE_SIZE,
    TARGET_SERVICE_UUID,
)
from .errors import (
    BleDisconnectedError,
    DeviceNotFoundError,
    GattValidationError,
    MultipleDevicesError,
)
from .logging_utils import Stage5Logger
from .notification_parser import parse_notification
from .upload_state import UploadState


@dataclass(frozen=True)
class ScanResult:
    devices: tuple[BleDevice, ...]
    target_name: str
    matching_count: int


@dataclass(frozen=True)
class GattValidation:
    service_found: bool
    ff02_found: bool
    ff02_write_without_response: bool
    ff03_found: bool
    ff03_notify: bool
    maximum_write_without_response: int | None
    mtu_size: int | None
    platform: str

    @property
    def required_gatt_ok(self) -> bool:
        return all((
            self.service_found,
            self.ff02_found,
            self.ff02_write_without_response,
            self.ff03_found,
            self.ff03_notify,
        ))

    @property
    def capacity_below_required(self) -> bool:
        return (
            self.maximum_write_without_response is not None
            and self.maximum_write_without_response < REQUIRED_WRITE_WITHOUT_RESPONSE_SIZE
        )


@dataclass(frozen=True)
class InfoResult:
    validation: GattValidation
    disconnected: bool


@dataclass(frozen=True)
class ListenResult:
    validation: GattValidation
    notifications: int
    disconnected: bool


def select_device(
    devices: list[BleDevice],
    *,
    target_name: str,
    device_id: str | None = None,
) -> BleDevice:
    if device_id is not None:
        matches = [device for device in devices if device.device_id == device_id]
        if len(matches) == 1:
            return matches[0]
        raise DeviceNotFoundError(f"未找到设备 ID: {device_id}")
    matches = [device for device in devices if device.name == target_name]
    if not matches:
        raise DeviceNotFoundError(f"未发现名称为 {target_name!r} 的设备")
    if len(matches) > 1:
        ids = ", ".join(device.device_id for device in matches)
        raise MultipleDevicesError(f"发现 {len(matches)} 个同名设备，请指定设备 ID: {ids}")
    return matches[0]


def validate_gatt(snapshot: GattSnapshot) -> GattValidation:
    service_found = (
        snapshot.service_found
        and snapshot.service_uuid.lower() == TARGET_SERVICE_UUID
    )
    ff02_found = snapshot.ff02 is not None and snapshot.ff02.uuid.lower() == FF02_UUID
    ff03_found = snapshot.ff03 is not None and snapshot.ff03.uuid.lower() == FF03_UUID
    return GattValidation(
        service_found=service_found,
        ff02_found=ff02_found,
        ff02_write_without_response=(
            ff02_found
            and snapshot.ff02 is not None
            and "write-without-response" in snapshot.ff02.properties
        ),
        ff03_found=ff03_found,
        ff03_notify=(
            ff03_found and snapshot.ff03 is not None and "notify" in snapshot.ff03.properties
        ),
        maximum_write_without_response=(
            snapshot.ff02.max_write_without_response_size if snapshot.ff02 else None
        ),
        mtu_size=snapshot.mtu_size,
        platform=snapshot.platform,
    )


def require_valid_gatt(
    validation: GattValidation,
    *,
    require_capacity: bool = True,
) -> None:
    if not validation.service_found:
        raise GattValidationError("找不到目标 Service")
    if not validation.ff02_found:
        raise GattValidationError("找不到 FF02")
    if not validation.ff02_write_without_response:
        raise GattValidationError("FF02 不支持 Write Without Response")
    if not validation.ff03_found:
        raise GattValidationError("找不到 FF03")
    if not validation.ff03_notify:
        raise GattValidationError("FF03 不支持 Notify")
    if require_capacity and validation.capacity_below_required:
        raise GattValidationError(
            "maximum write without response is below 237 bytes"
        )


async def run_scan(
    transport: BleTransport,
    *,
    timeout: float,
    target_name: str,
    logger: Stage5Logger,
) -> ScanResult:
    logger.emit("scan_started", state=UploadState.SCANNING, timeout=timeout, target_name=target_name)
    devices = await transport.scan(timeout)
    matching = sum(device.name == target_name for device in devices)
    logger.emit(
        "scan_completed",
        state=UploadState.DISCONNECTED,
        device_count=len(devices),
        matching_count=matching,
    )
    return ScanResult(tuple(devices), target_name, matching)


async def run_info(
    transport: BleTransport,
    *,
    device_id: str,
    timeout: float,
    logger: Stage5Logger,
) -> InfoResult:
    validation: GattValidation | None = None
    disconnected = False
    try:
        logger.emit("connecting", state=UploadState.CONNECTING, device_id=device_id)
        await transport.connect(device_id, timeout)
        logger.emit("connected", state=UploadState.CONNECTED, device_id=device_id)
        validation = validate_gatt(await transport.discover())
        logger.emit(
            "gatt_validated" if validation.required_gatt_ok and not validation.capacity_below_required else "gatt_invalid",
            state=(
                UploadState.GATT_VALIDATED
                if validation.required_gatt_ok and not validation.capacity_below_required
                else UploadState.FAILED
            ),
            device_id=device_id,
            maximum_write_without_response=validation.maximum_write_without_response,
            mtu_size=validation.mtu_size,
            platform=validation.platform,
        )
    finally:
        if transport.is_connected:
            logger.emit("disconnecting", state=UploadState.DISCONNECTING, device_id=device_id)
            await transport.disconnect()
        disconnected = not transport.is_connected
        logger.emit("disconnected", state=UploadState.DISCONNECTED, device_id=device_id)
    if validation is None:
        raise GattValidationError("未取得 GATT 信息")
    return InfoResult(validation, disconnected)


async def run_listen(
    transport: BleTransport,
    *,
    device_id: str,
    seconds: float,
    timeout: float,
    logger: Stage5Logger,
) -> ListenResult:
    validation: GattValidation | None = None
    subscribed = False
    received = 0
    wait_tasks: list[asyncio.Task[object]] = []

    def on_notification(data: bytes) -> None:
        nonlocal received
        received += 1
        logger.notification(
            parse_notification(data),
            state=UploadState.LISTENING,
            device_id=device_id,
            uuid=FF03_UUID,
        )

    try:
        logger.emit("connecting", state=UploadState.CONNECTING, device_id=device_id)
        await transport.connect(device_id, timeout)
        logger.emit("connected", state=UploadState.CONNECTED, device_id=device_id)
        validation = validate_gatt(await transport.discover())
        require_valid_gatt(validation)
        logger.emit("gatt_validated", state=UploadState.GATT_VALIDATED, device_id=device_id)
        await transport.start_notify(FF03_UUID, on_notification)
        subscribed = True
        logger.emit("notify_enabled", state=UploadState.NOTIFY_ENABLED, device_id=device_id, uuid=FF03_UUID)
        logger.emit("listening", state=UploadState.LISTENING, device_id=device_id, seconds=seconds)

        timer = asyncio.create_task(asyncio.sleep(seconds))
        disconnected = asyncio.create_task(transport.wait_disconnected())
        wait_tasks = [timer, disconnected]
        done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        if disconnected in done:
            raise BleDisconnectedError("监听期间 BLE 连接断开")
    except asyncio.CancelledError:
        logger.emit("cancelled", state=UploadState.CANCELLED, device_id=device_id)
        raise
    finally:
        for task in wait_tasks:
            if not task.done():
                task.cancel()
        if wait_tasks:
            await asyncio.gather(*wait_tasks, return_exceptions=True)
        if subscribed and transport.is_connected:
            await transport.stop_notify(FF03_UUID)
        if transport.is_connected:
            logger.emit("disconnecting", state=UploadState.DISCONNECTING, device_id=device_id)
            await transport.disconnect()
        logger.emit("disconnected", state=UploadState.DISCONNECTED, device_id=device_id)
    if validation is None:
        raise GattValidationError("未取得 GATT 信息")
    return ListenResult(validation, received, not transport.is_connected)
