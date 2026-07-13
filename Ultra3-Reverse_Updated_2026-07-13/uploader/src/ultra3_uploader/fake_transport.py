from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timezone

from .ble_transport import (
    BleDevice,
    GattCharacteristic,
    GattSnapshot,
    NotificationCallback,
    TransportKind,
)
from .constants import CA_APPLY_FRAME, CA_SUCCESS_FRAME, FF02_UUID, FF03_UUID, TARGET_SERVICE_UUID
from .errors import BleTransportError


def default_snapshot() -> GattSnapshot:
    return GattSnapshot(
        service_uuid=TARGET_SERVICE_UUID,
        service_found=True,
        ff02=GattCharacteristic(
            uuid=FF02_UUID,
            properties=frozenset({"write-without-response"}),
            max_write_without_response_size=244,
        ),
        ff03=GattCharacteristic(uuid=FF03_UUID, properties=frozenset({"notify"})),
        mtu_size=247,
        platform="fake",
    )


class FakeBleTransport:
    def __init__(
        self,
        *,
        devices: Iterable[BleDevice] | None = None,
        snapshot: GattSnapshot | None = None,
        scan_error: str | None = None,
        connect_error: str | None = None,
        notify_error: str | None = None,
        notifications_on_subscribe: Iterable[bytes] = (),
        notifications_on_write: Iterable[bytes] = (),
        prepare_notifications: Iterable[bytes] | None = None,
        auto_prepare: bool = False,
        disconnect_on_subscribe: bool = False,
        disconnect_on_write: bool = False,
        last_c9_sequence: int | None = None,
        ca_mode: str = "missing",
        ca_delay_seconds: float = 0.0,
        early_ca_sequence: int = 0,
        fail_at_sequence: int | None = None,
        disconnect_at_sequence: int | None = None,
        cancel_at_sequence: int | None = None,
        cancellation_event: asyncio.Event | None = None,
        notifications_at_sequence: dict[int, list[bytes]] | None = None,
        fail_ca_apply: bool = False,
        max_write_size: int | None = 244,
    ) -> None:
        self.devices = list(devices) if devices is not None else [
            BleDevice("FAKE-ULTRA3-1", "ULTRA 3", -45, "fake")
        ]
        base_snapshot = snapshot if snapshot is not None else default_snapshot()
        if snapshot is None and base_snapshot.ff02 is not None:
            base_snapshot = replace(
                base_snapshot,
                ff02=replace(
                    base_snapshot.ff02,
                    max_write_without_response_size=max_write_size,
                ),
            )
        self.snapshot = base_snapshot
        self.scan_error = scan_error
        self.connect_error = connect_error
        self.notify_error = notify_error
        self.notifications_on_subscribe = list(notifications_on_subscribe)
        self.notifications_on_write = list(notifications_on_write)
        self.prepare_notifications = (
            list(prepare_notifications) if prepare_notifications is not None else None
        )
        self.auto_prepare = auto_prepare
        self.disconnect_on_subscribe = disconnect_on_subscribe
        self.disconnect_on_write = disconnect_on_write
        self.last_c9_sequence = last_c9_sequence
        self.ca_mode = ca_mode
        self.ca_delay_seconds = ca_delay_seconds
        self.early_ca_sequence = early_ca_sequence
        self.fail_at_sequence = fail_at_sequence
        self.disconnect_at_sequence = disconnect_at_sequence
        self.cancel_at_sequence = cancel_at_sequence
        self.cancellation_event = cancellation_event
        self.notifications_at_sequence = notifications_at_sequence or {}
        self.fail_ca_apply = fail_ca_apply
        self.max_write_size = max_write_size
        self.scan_calls: list[float] = []
        self.connect_calls: list[tuple[str, float]] = []
        self.disconnect_calls = 0
        self.discover_calls = 0
        self.notify_subscriptions: list[str] = []
        self.notify_unsubscriptions: list[str] = []
        self.writes: list[tuple[str, bytes]] = []
        self.write_attempts: list[tuple[str, bytes]] = []
        self.write_order: list[int] = []
        self.write_timestamps: list[str] = []
        self._connected = False
        self._callbacks: dict[str, NotificationCallback] = {}
        self._disconnected_event = asyncio.Event()
        self._background_tasks: list[asyncio.Task[None]] = []

    @property
    def kind(self) -> TransportKind:
        return TransportKind.FAKE

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def scan(self, timeout: float) -> list[BleDevice]:
        self.scan_calls.append(timeout)
        await asyncio.sleep(0)
        if self.scan_error:
            raise BleTransportError(self.scan_error)
        return list(self.devices)

    async def connect(self, device_id: str, timeout: float) -> None:
        self.connect_calls.append((device_id, timeout))
        if self.connect_error:
            raise BleTransportError(self.connect_error)
        self._disconnected_event = asyncio.Event()
        self._connected = True

    async def disconnect(self) -> None:
        self.disconnect_calls += 1
        self._connected = False
        self._disconnected_event.set()
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()

    async def discover(self) -> GattSnapshot:
        self.discover_calls += 1
        if not self._connected:
            raise BleTransportError("fake transport 未连接")
        return self.snapshot

    async def start_notify(self, uuid: str, callback: NotificationCallback) -> None:
        if self.notify_error:
            raise BleTransportError(self.notify_error)
        self.notify_subscriptions.append(uuid.lower())
        self._callbacks[uuid.lower()] = callback
        for data in self.notifications_on_subscribe:
            await self.emit_notification(uuid, data)
        if self.disconnect_on_subscribe:
            self.simulate_remote_disconnect()

    async def stop_notify(self, uuid: str) -> None:
        self.notify_unsubscriptions.append(uuid.lower())
        self._callbacks.pop(uuid.lower(), None)

    async def write_without_response(self, uuid: str, data: bytes) -> None:
        if not self._connected:
            raise BleTransportError("fake transport 未连接")
        raw = bytes(data)
        normalized_uuid = uuid.lower()
        self.write_attempts.append((normalized_uuid, raw))
        if self.max_write_size is not None and len(raw) > self.max_write_size:
            raise BleTransportError(
                f"写入长度 {len(raw)} 超过 fake 上限 {self.max_write_size}"
            )
        is_c9 = raw.startswith(b"\xBC\xC9\x02")
        sequence = int.from_bytes(raw[4:6], "little") if is_c9 else None
        if is_c9 and sequence == self.fail_at_sequence:
            raise BleTransportError(f"模拟 C9 sequence {sequence} 写入失败")
        if raw == CA_APPLY_FRAME and self.fail_ca_apply:
            raise BleTransportError("模拟 CA apply 写入失败")
        self.writes.append((normalized_uuid, raw))
        self.write_order.append(len(self.writes) - 1)
        self.write_timestamps.append(datetime.now(timezone.utc).isoformat())
        if raw.startswith(b"\xBC\xC8") and self.auto_prepare:
            notifications = self._prepare_sequence(raw)
        elif raw.startswith(b"\xBC\xC8") and self.prepare_notifications is not None:
            notifications = self.prepare_notifications
        else:
            notifications = self.notifications_on_write
        for notification in notifications:
            await self.emit_notification(FF03_UUID, notification)
        if self.disconnect_on_write:
            self.simulate_remote_disconnect()
        if not is_c9 or sequence is None:
            return
        for notification in self.notifications_at_sequence.get(sequence, []):
            await self.emit_notification(FF03_UUID, notification)
        if self.ca_mode == "early" and sequence == self.early_ca_sequence:
            await self.emit_notification(FF03_UUID, CA_SUCCESS_FRAME)
        if sequence == self.disconnect_at_sequence:
            self.simulate_remote_disconnect()
        if sequence == self.cancel_at_sequence and self.cancellation_event is not None:
            self.cancellation_event.set()
        if sequence == self.last_c9_sequence and self.ca_mode in {
            "normal", "duplicate", "delayed"
        }:
            task = asyncio.create_task(self._emit_ca_success())
            self._background_tasks.append(task)

    @staticmethod
    def _prepare_sequence(c8_request: bytes) -> list[bytes]:
        countdown = [
            bytes.fromhex(f"BC720302{value:02X}00{value:02X}")
            for value in range(30, -1, -1)
        ]
        response = bytearray(c8_request)
        response[2] = 0x03
        return countdown + [bytes.fromhex("BCD103010202"), bytes(response)]

    async def _emit_ca_success(self) -> None:
        if self.ca_mode == "delayed" and self.ca_delay_seconds > 0:
            await asyncio.sleep(self.ca_delay_seconds)
        else:
            await asyncio.sleep(0)
        if not self._connected:
            return
        await self.emit_notification(FF03_UUID, CA_SUCCESS_FRAME)
        if self.ca_mode == "duplicate":
            await self.emit_notification(FF03_UUID, CA_SUCCESS_FRAME)

    async def wait_disconnected(self) -> None:
        await self._disconnected_event.wait()

    async def emit_notification(self, uuid: str, data: bytes) -> None:
        callback = self._callbacks.get(uuid.lower())
        if callback is None:
            raise BleTransportError(f"未订阅通知: {uuid}")
        result = callback(bytes(data))
        if result is not None:
            await result

    def simulate_remote_disconnect(self) -> None:
        self._connected = False
        self._disconnected_event.set()
