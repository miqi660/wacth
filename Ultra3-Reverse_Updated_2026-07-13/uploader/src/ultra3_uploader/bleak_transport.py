from __future__ import annotations

import asyncio
import inspect
import platform
import sys
from typing import Any

from bleak import BleakClient, BleakScanner

from .ble_transport import (
    BleDevice,
    GattCharacteristic,
    GattSnapshot,
    NotificationCallback,
)
from .constants import FF02_UUID, FF03_UUID, TARGET_SERVICE_UUID
from .errors import BleTransportError


def platform_description() -> str:
    system = platform.system() or "unknown"
    release = platform.release() or "unknown"
    if system == "Windows":
        try:
            build = sys.getwindowsversion().build
        except AttributeError:
            build = "unknown"
        return f"Windows release={release} build={build}"
    return f"{system} release={release}"


class BleakTransport:
    def __init__(self) -> None:
        self._client: BleakClient | None = None
        self._disconnected_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.platform = platform_description()

    @property
    def is_connected(self) -> bool:
        return bool(self._client and self._client.is_connected)

    async def scan(self, timeout: float) -> list[BleDevice]:
        try:
            discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
        except Exception as exc:
            raise BleTransportError(f"BLE 扫描失败（{self.platform}）: {exc}") from exc

        devices: list[BleDevice] = []
        if isinstance(discovered, dict):
            items = discovered.values()
            for device, advertisement in items:
                name = getattr(advertisement, "local_name", None) or device.name
                rssi = getattr(advertisement, "rssi", None)
                devices.append(BleDevice(device.address, name, rssi, self.platform))
        else:
            for device in discovered:
                devices.append(BleDevice(device.address, device.name, None, self.platform))
        return devices

    async def connect(self, device_id: str, timeout: float) -> None:
        self._loop = asyncio.get_running_loop()
        self._disconnected_event = asyncio.Event()
        self._client = BleakClient(
            device_id,
            disconnected_callback=self._on_disconnected,
            timeout=timeout,
        )
        try:
            await self._client.connect()
        except Exception as exc:
            self._client = None
            raise BleTransportError(f"BLE 连接失败（{self.platform}）: {exc}") from exc
        if not self._client.is_connected:
            self._client = None
            raise BleTransportError("Bleak connect 返回后设备仍未连接")

    def _on_disconnected(self, _client: BleakClient) -> None:
        if self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(self._disconnected_event.set)

    async def disconnect(self) -> None:
        client = self._client
        if client is None:
            return
        try:
            if client.is_connected:
                await client.disconnect()
        except Exception as exc:
            raise BleTransportError(f"BLE 断开失败: {exc}") from exc
        finally:
            self._disconnected_event.set()
            self._client = None

    def _require_client(self) -> BleakClient:
        if self._client is None or not self._client.is_connected:
            raise BleTransportError("BLE transport 未连接")
        return self._client

    @staticmethod
    def _characteristic(characteristic: Any) -> GattCharacteristic | None:
        if characteristic is None:
            return None
        try:
            maximum = getattr(characteristic, "max_write_without_response_size", None)
        except Exception:
            maximum = None
        if not isinstance(maximum, int) or maximum <= 0:
            maximum = None
        try:
            handle = getattr(characteristic, "handle", None)
        except Exception:
            handle = None
        if not isinstance(handle, int):
            handle = None
        try:
            properties = frozenset(
                str(value).lower() for value in characteristic.properties
            )
        except Exception:
            properties = frozenset()
        return GattCharacteristic(
            uuid=str(characteristic.uuid).lower(),
            properties=properties,
            max_write_without_response_size=maximum,
            handle=handle,
        )

    async def discover(self) -> GattSnapshot:
        client = self._require_client()
        try:
            services = client.services
            service = services.get_service(TARGET_SERVICE_UUID)
            ff02 = service.get_characteristic(FF02_UUID) if service else None
            ff03 = service.get_characteristic(FF03_UUID) if service else None
            try:
                mtu = getattr(client, "mtu_size", None)
            except Exception:
                mtu = None
            if not isinstance(mtu, int) or mtu <= 0:
                mtu = None
            return GattSnapshot(
                service_uuid=TARGET_SERVICE_UUID,
                service_found=service is not None,
                ff02=self._characteristic(ff02),
                ff03=self._characteristic(ff03),
                mtu_size=mtu,
                platform=self.platform,
            )
        except Exception as exc:
            raise BleTransportError(f"GATT 枚举失败（{self.platform}）: {exc}") from exc

    async def start_notify(self, uuid: str, callback: NotificationCallback) -> None:
        client = self._require_client()

        async def handler(_sender: Any, data: bytearray) -> None:
            result = callback(bytes(data))
            if inspect.isawaitable(result):
                await result

        try:
            await client.start_notify(uuid, handler)
        except Exception as exc:
            raise BleTransportError(f"订阅通知失败 {uuid}: {exc}") from exc

    async def stop_notify(self, uuid: str) -> None:
        client = self._require_client()
        try:
            await client.stop_notify(uuid)
        except Exception as exc:
            raise BleTransportError(f"取消通知失败 {uuid}: {exc}") from exc

    async def write_without_response(self, uuid: str, data: bytes) -> None:
        client = self._require_client()
        try:
            await client.write_gatt_char(uuid, data, response=False)
        except Exception as exc:
            raise BleTransportError(f"Write Without Response 失败 {uuid}: {exc}") from exc

    async def wait_disconnected(self) -> None:
        await self._disconnected_event.wait()
