from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

NotificationCallback = Callable[[bytes], None | Awaitable[None]]


@dataclass(frozen=True)
class BleDevice:
    device_id: str
    name: str | None
    rssi: int | None = None
    platform: str = "unknown"


@dataclass(frozen=True)
class GattCharacteristic:
    uuid: str
    properties: frozenset[str]
    max_write_without_response_size: int | None = None
    handle: int | None = None


@dataclass(frozen=True)
class GattSnapshot:
    service_uuid: str
    service_found: bool
    ff02: GattCharacteristic | None
    ff03: GattCharacteristic | None
    mtu_size: int | None = None
    platform: str = "unknown"


class BleTransport(Protocol):
    async def scan(self, timeout: float) -> list[BleDevice]: ...

    async def connect(self, device_id: str, timeout: float) -> None: ...

    async def disconnect(self) -> None: ...

    async def discover(self) -> GattSnapshot: ...

    async def start_notify(self, uuid: str, callback: NotificationCallback) -> None: ...

    async def stop_notify(self, uuid: str) -> None: ...

    async def write_without_response(self, uuid: str, data: bytes) -> None: ...

    async def wait_disconnected(self) -> None: ...

    @property
    def is_connected(self) -> bool: ...

