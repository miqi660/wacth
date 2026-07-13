from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import datetime, timezone

from .ble_transport import (
    BleDevice,
    GattCharacteristic,
    GattSnapshot,
    NotificationCallback,
)
from .constants import FF02_UUID, FF03_UUID, TARGET_SERVICE_UUID
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
        disconnect_on_subscribe: bool = False,
        disconnect_on_write: bool = False,
    ) -> None:
        self.devices = list(devices) if devices is not None else [
            BleDevice("FAKE-ULTRA3-1", "ULTRA 3", -45, "fake")
        ]
        self.snapshot = snapshot if snapshot is not None else default_snapshot()
        self.scan_error = scan_error
        self.connect_error = connect_error
        self.notify_error = notify_error
        self.notifications_on_subscribe = list(notifications_on_subscribe)
        self.notifications_on_write = list(notifications_on_write)
        self.disconnect_on_subscribe = disconnect_on_subscribe
        self.disconnect_on_write = disconnect_on_write
        self.scan_calls: list[float] = []
        self.connect_calls: list[tuple[str, float]] = []
        self.disconnect_calls = 0
        self.discover_calls = 0
        self.notify_subscriptions: list[str] = []
        self.notify_unsubscriptions: list[str] = []
        self.writes: list[tuple[str, bytes]] = []
        self.write_order: list[int] = []
        self.write_timestamps: list[str] = []
        self._connected = False
        self._callbacks: dict[str, NotificationCallback] = {}
        self._disconnected_event = asyncio.Event()

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
        self.writes.append((uuid.lower(), bytes(data)))
        self.write_order.append(len(self.writes) - 1)
        self.write_timestamps.append(datetime.now(timezone.utc).isoformat())
        for notification in self.notifications_on_write:
            await self.emit_notification(FF03_UUID, notification)
        if self.disconnect_on_write:
            self.simulate_remote_disconnect()

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
