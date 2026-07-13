from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .bcsdial import BCSDIALPayload
from .ble_transport import BleTransport
from .constants import FF02_UUID, FF03_UUID
from .errors import (
    BleDisconnectedError,
    C8ResponseMismatchError,
    CountdownError,
    PrepareError,
    PrepareTimeoutError,
)
from .logging_utils import Stage5Logger
from .notification_parser import NotificationRecord, parse_notification
from .stage5 import require_valid_gatt, validate_gatt
from .upload_state import UploadState

EXPECTED_COUNTDOWN = tuple(range(30, -1, -1))


@dataclass(frozen=True)
class PrepareResult:
    file_size: int
    packet_count: int
    c8_hex: str
    countdown: tuple[int, ...]
    d1_received: bool
    c8_response_matched: bool
    ff02_write_count: int
    c9_write_count: int
    ca_write_count: int
    disconnected: bool
    final_state: UploadState


async def _next_notification(
    queue: asyncio.Queue[NotificationRecord],
    transport: BleTransport,
    timeout: float,
) -> NotificationRecord:
    notification_task = asyncio.create_task(queue.get())
    disconnected_task = asyncio.create_task(transport.wait_disconnected())
    tasks = (notification_task, disconnected_task)
    try:
        done, _pending = await asyncio.wait(
            tasks,
            timeout=timeout,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if not done:
            raise asyncio.TimeoutError
        if disconnected_task in done:
            raise BleDisconnectedError("准备期间 BLE 连接断开")
        return notification_task.result()
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _remaining(deadline: float) -> float:
    remaining = deadline - asyncio.get_running_loop().time()
    if remaining <= 0:
        raise asyncio.TimeoutError
    return remaining


def _expected_c8_response(c8_request: bytes) -> bytes:
    response = bytearray(c8_request)
    response[2] = 0x03
    return bytes(response)


def _validate_c8_response(
    record: NotificationRecord,
    payload: BCSDIALPayload,
    expected_response: bytes,
) -> None:
    if not record.valid:
        raise C8ResponseMismatchError(record.parse_error or "C8 response 无效")
    fields = record.parsed_fields
    if fields.get("file_size") != payload.size:
        raise C8ResponseMismatchError(
            f"C8 response 文件大小不匹配: {fields.get('file_size')} != {payload.size}"
        )
    if fields.get("packet_count") != payload.packet_count:
        raise C8ResponseMismatchError(
            "C8 response 包数不匹配: "
            f"{fields.get('packet_count')} != {payload.packet_count}"
        )
    if record.raw != expected_response:
        raise C8ResponseMismatchError("C8 response 内容与当前 C8 request 不匹配")


async def run_prepare_bcsdial(
    transport: BleTransport,
    payload: BCSDIALPayload,
    *,
    device_id: str,
    ready_timeout: float,
    connect_timeout: float,
    logger: Stage5Logger,
) -> PrepareResult:
    payload.validate()
    queue: asyncio.Queue[NotificationRecord] = asyncio.Queue()
    state = UploadState.DISCONNECTED
    subscribed = False
    countdown: list[int] = []
    d1_received = False
    c8_confirmed = False
    sent_frames: list[bytes] = []
    c8_request = payload.build_prepare_frame()
    expected_response = _expected_c8_response(c8_request)
    cleanup_errors: list[str] = []

    def on_notification(data: bytes) -> None:
        record = parse_notification(data)
        logger.notification(record, state=state, device_id=device_id, uuid=FF03_UUID)
        queue.put_nowait(record)

    try:
        state = UploadState.CONNECTING
        logger.emit("connecting", state=state, device_id=device_id)
        await transport.connect(device_id, connect_timeout)
        state = UploadState.CONNECTED
        logger.emit("connected", state=state, device_id=device_id)

        validation = validate_gatt(await transport.discover())
        require_valid_gatt(validation)
        state = UploadState.GATT_VALIDATED
        logger.emit(
            "gatt_validated",
            state=state,
            device_id=device_id,
            maximum_write_without_response=validation.maximum_write_without_response,
            mtu_size=validation.mtu_size,
        )

        await transport.start_notify(FF03_UUID, on_notification)
        subscribed = True
        state = UploadState.NOTIFY_ENABLED
        logger.emit("notify_enabled", state=state, device_id=device_id, uuid=FF03_UUID)

        await transport.write_without_response(FF02_UUID, c8_request)
        sent_frames.append(c8_request)
        state = UploadState.C8_SENT
        logger.emit(
            "frame_sent",
            direction="TX",
            state=state,
            device_id=device_id,
            uuid=FF02_UUID,
            length=len(c8_request),
            hex_data=c8_request.hex().upper(),
            command="C8",
        )

        d1_deadline = asyncio.get_running_loop().time() + ready_timeout
        while not d1_received:
            try:
                record = await _next_notification(
                    queue, transport, _remaining(d1_deadline)
                )
            except asyncio.TimeoutError as exc:
                if not countdown:
                    raise PrepareTimeoutError("BC72 countdown 缺失") from exc
                if tuple(countdown) == EXPECTED_COUNTDOWN:
                    raise PrepareTimeoutError("D1 ready 超时") from exc
                raise PrepareTimeoutError("BC72 countdown 未完成") from exc

            if record.command == "UNKNOWN" or record.command == "CA":
                continue
            if record.command == "72":
                if not record.valid:
                    raise CountdownError(record.parse_error or "BC72 无效")
                value = int(record.parsed_fields["countdown"])
                expected = 30 - len(countdown)
                if value != expected:
                    raise CountdownError(
                        f"BC72 倒计时乱序: 收到 {value}，预期 {expected}"
                    )
                countdown.append(value)
                state = UploadState.COUNTDOWN
                continue
            if record.command == "D1":
                if not record.valid:
                    raise PrepareError(record.parse_error or "D1 ready 无效")
                if not countdown:
                    raise CountdownError("收到 D1，但 BC72 countdown 缺失")
                if tuple(countdown) != EXPECTED_COUNTDOWN:
                    raise CountdownError(
                        f"收到 D1，但 BC72 countdown 不完整: {len(countdown)}/31"
                    )
                d1_received = True
                state = UploadState.D1_READY
                logger.emit("d1_ready", direction="RX", state=state, device_id=device_id)
                continue
            if record.command == "C8":
                raise PrepareError("在 D1 ready 之前收到 C8 response")

        c8_deadline = asyncio.get_running_loop().time() + ready_timeout
        while not c8_confirmed:
            try:
                record = await _next_notification(
                    queue, transport, _remaining(c8_deadline)
                )
            except asyncio.TimeoutError as exc:
                raise PrepareTimeoutError("C8 response 超时") from exc
            if record.command == "UNKNOWN" or record.command == "CA":
                continue
            if record.command != "C8":
                raise PrepareError(f"D1 ready 后收到非预期 {record.command} 通知")
            _validate_c8_response(record, payload, expected_response)
            c8_confirmed = True
            state = UploadState.C8_CONFIRMED
            logger.emit("c8_confirmed", direction="RX", state=state, device_id=device_id)

        state = UploadState.PREPARE_VERIFIED
        logger.emit("prepare_verified", state=state, device_id=device_id)
    except asyncio.CancelledError:
        state = UploadState.CANCELLED
        logger.emit("cancelled", state=state, device_id=device_id)
        raise
    except Exception as exc:
        state = UploadState.FAILED
        logger.emit("prepare_failed", state=state, device_id=device_id, error=str(exc))
        raise
    finally:
        if subscribed and transport.is_connected:
            try:
                await transport.stop_notify(FF03_UUID)
            except Exception as exc:
                cleanup_errors.append(f"停止 FF03 通知失败: {exc}")
                logger.emit(
                    "stop_notify_failed",
                    state=UploadState.FAILED,
                    device_id=device_id,
                    uuid=FF03_UUID,
                    error=str(exc),
                )
        if transport.is_connected:
            state = UploadState.DISCONNECTING
            logger.emit("disconnecting", state=state, device_id=device_id)
            try:
                await transport.disconnect()
            except Exception as exc:
                cleanup_errors.append(f"断开失败: {exc}")
                logger.emit(
                    "disconnect_failed",
                    state=UploadState.FAILED,
                    device_id=device_id,
                    error=str(exc),
                )

    if cleanup_errors:
        raise PrepareError("；".join(cleanup_errors))

    state = UploadState.COMPLETE
    logger.emit("complete", state=state, device_id=device_id)
    c9_writes = sum(frame.startswith(b"\xBC\xC9") for frame in sent_frames)
    ca_writes = sum(frame.startswith(b"\xBC\xCA") for frame in sent_frames)
    return PrepareResult(
        file_size=payload.size,
        packet_count=payload.packet_count,
        c8_hex=c8_request.hex().upper(),
        countdown=tuple(countdown),
        d1_received=d1_received,
        c8_response_matched=c8_confirmed,
        ff02_write_count=len(sent_frames),
        c9_write_count=c9_writes,
        ca_write_count=ca_writes,
        disconnected=not transport.is_connected,
        final_state=state,
    )
