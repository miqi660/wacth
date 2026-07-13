from __future__ import annotations

import asyncio
from collections.abc import Callable

from .bc_frames import parse_c9
from .bcsdial import BCSDIALPayload
from .ble_transport import BleTransport
from .constants import CA_APPLY_FRAME, FF02_UUID
from .errors import (
    BleDisconnectedError,
    CAProtocolError,
    UploadCancelledError,
    UploadError,
    UploadSafetyError,
)
from .fake_transport import FakeBleTransport
from .logging_utils import Stage5Logger
from .prepare_bcsdial import (
    PreparedSession,
    cleanup_session,
    next_notification,
    prepare_bcsdial_session,
)
from .timing import Clock, FakeSleeper, RealClock, RealSleeper, Sleeper
from .upload_progress import UploadProgress, make_progress
from .upload_result import UploadResult
from .upload_state import UploadState

ProgressCallback = Callable[[UploadProgress], None]


def _write_counts(frames: list[bytes]) -> tuple[int, int, int]:
    c8 = sum(frame.startswith(b"\xBC\xC8") for frame in frames)
    c9 = sum(frame.startswith(b"\xBC\xC9") for frame in frames)
    ca = sum(frame.startswith(b"\xBC\xCA") for frame in frames)
    return c8, c9, ca


def _result(
    *,
    success: bool,
    final_state: UploadState,
    frames: list[bytes],
    packets_sent: int,
    bytes_sent: int,
    last_sequence: int | None,
    ca_success_received: bool,
    ca_apply_sent: bool,
    elapsed_seconds: float,
    cancellation_requested: bool,
    disconnected: bool,
    error: BaseException | None,
) -> UploadResult:
    c8, c9, ca = _write_counts(frames)
    return UploadResult(
        success=success,
        final_state=final_state,
        c8_writes=c8,
        c9_writes=c9,
        ca_writes=ca,
        total_writes=len(frames),
        packets_sent=packets_sent,
        bytes_sent=bytes_sent,
        last_sequence=last_sequence,
        ca_success_received=ca_success_received,
        ca_apply_sent=ca_apply_sent,
        elapsed_seconds=elapsed_seconds,
        cancellation_requested=cancellation_requested,
        disconnect_observed=disconnected,
        error_type=type(error).__name__ if error else None,
        error_message=str(error) if error else None,
    )


async def upload_bcsdial(
    transport: BleTransport,
    payload: BCSDIALPayload,
    *,
    device_id: str = "FAKE-ULTRA3-1",
    packet_delay_ms: float = 45.0,
    ready_timeout: float = 60.0,
    ca_timeout: float = 30.0,
    connect_timeout: float = 20.0,
    cancellation_event: asyncio.Event | None = None,
    progress_callback: ProgressCallback | None = None,
    logger: Stage5Logger | None = None,
    sleeper: Sleeper | None = None,
    clock: Clock | None = None,
) -> UploadResult:
    if not isinstance(transport, FakeBleTransport):
        raise UploadSafetyError("Stage 6B build does not permit real BLE upload.")
    if packet_delay_ms < 0 or ready_timeout <= 0 or ca_timeout <= 0:
        raise UploadError("packet delay 必须非负，timeout 必须大于 0")

    event_logger = logger or Stage5Logger(human_output=False)
    delay = sleeper or RealSleeper()
    if clock is None and isinstance(delay, FakeSleeper) and delay.clock is not None:
        active_clock: Clock = delay.clock
    else:
        active_clock = clock or RealClock()

    started_at = active_clock.monotonic()
    frames: list[bytes] = []
    session: PreparedSession | None = None
    packets_sent = 0
    bytes_sent = 0
    last_sequence: int | None = None
    ca_success_received = False
    ca_apply_sent = False
    cancellation_requested = False
    business_state = UploadState.FAILED
    failure: BaseException | None = None
    last_progress_percent = -1

    def cancelled() -> bool:
        return cancellation_event is not None and cancellation_event.is_set()

    try:
        session = await prepare_bcsdial_session(
            transport,
            payload,
            device_id=device_id,
            ready_timeout=ready_timeout,
            connect_timeout=connect_timeout,
            logger=event_logger,
            sent_frames=frames,
        )
        maximum = session.maximum_write_without_response
        if maximum is None:
            raise UploadError("无法确认最大 Write Without Response 长度，拒绝发送 C9")

        session.context.state = UploadState.SENDING_C9
        event_logger.emit(
            "upload_started",
            state=session.context.state,
            device_id=device_id,
            total_packets=payload.packet_count,
            total_bytes=payload.size,
            packet_delay_ms=packet_delay_ms,
        )
        transfer_started = active_clock.monotonic()

        for expected_sequence, frame in enumerate(payload.iter_data_frames()):
            if cancelled():
                raise UploadCancelledError(
                    f"在 C9 sequence {expected_sequence} 前收到取消请求"
                )
            if session.context.early_ca_received:
                raise CAProtocolError("在最后一个 C9 之前收到 CA success")
            if not transport.is_connected:
                raise BleDisconnectedError(
                    f"发送 C9 sequence {expected_sequence} 前连接已断开"
                )
            if session.context.state is not UploadState.SENDING_C9:
                raise UploadError("C9 发送状态无效")
            packet = parse_c9(frame)
            if packet.sequence != expected_sequence:
                raise UploadError(
                    f"C9 sequence 不连续: {packet.sequence} != {expected_sequence}"
                )
            if not packet.checksum_valid:
                raise UploadError(f"C9 sequence {packet.sequence} checksum 无效")
            if len(frame) > maximum:
                raise UploadError(
                    f"C9 sequence {packet.sequence} 帧长 {len(frame)} 超过后端上限 {maximum}"
                )

            await transport.write_without_response(FF02_UUID, frame)
            frames.append(frame)
            packets_sent += 1
            bytes_sent += len(packet.data)
            last_sequence = packet.sequence
            event_logger.emit(
                "write",
                direction="TX",
                state=session.context.state,
                device_id=device_id,
                uuid=FF02_UUID,
                command="C9",
                sequence=packet.sequence,
                length=len(frame),
                data_length=len(packet.data),
                hex_data=frame.hex().upper(),
            )

            elapsed = active_clock.monotonic() - transfer_started
            progress = make_progress(
                packets_sent=packets_sent,
                total_packets=payload.packet_count,
                bytes_sent=bytes_sent,
                total_bytes=payload.size,
                elapsed_seconds=elapsed,
                current_sequence=packet.sequence,
                state=session.context.state,
            )
            if progress_callback is not None:
                progress_callback(progress)
            percent_bucket = int(progress.percent)
            if (
                packets_sent == 1
                or packets_sent == payload.packet_count
                or packets_sent % 50 == 0
                or percent_bucket > last_progress_percent
            ):
                event_logger.emit(
                    "progress",
                    state=session.context.state,
                    device_id=device_id,
                    current_packet=progress.current_packet,
                    total_packets=progress.total_packets,
                    packets_sent=progress.packets_sent,
                    bytes_sent=progress.bytes_sent,
                    total_bytes=progress.total_bytes,
                    percent=progress.percent,
                    elapsed_seconds=progress.elapsed_seconds,
                    effective_bytes_per_second=progress.effective_bytes_per_second,
                    estimated_remaining_seconds=progress.estimated_remaining_seconds,
                    current_sequence=progress.current_sequence,
                )
                last_progress_percent = max(last_progress_percent, percent_bucket)

            if session.context.early_ca_received:
                raise CAProtocolError("在最后一个 C9 之前收到 CA success")
            if not transport.is_connected:
                raise BleDisconnectedError(
                    f"发送 C9 sequence {packet.sequence} 后连接断开"
                )
            if cancelled():
                raise UploadCancelledError(
                    f"发送 C9 sequence {packet.sequence} 后收到取消请求"
                )
            if packets_sent < payload.packet_count:
                await delay.sleep(packet_delay_ms / 1000.0)

        session.context.state = UploadState.WAITING_CA_SUCCESS
        event_logger.emit(
            "waiting_ca_success",
            state=session.context.state,
            device_id=device_id,
        )
        ca_deadline = asyncio.get_running_loop().time() + ca_timeout
        while not ca_success_received:
            remaining = ca_deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise CAProtocolError("CA success 超时")
            try:
                notification = await next_notification(
                    session.context, transport, remaining
                )
            except asyncio.TimeoutError as exc:
                raise CAProtocolError("CA success 超时") from exc
            if notification.command == "UNKNOWN":
                continue
            if notification.command != "CA" or not notification.valid:
                raise CAProtocolError(
                    f"等待 CA success 时收到非预期 {notification.command} 通知"
                )
            ca_success_received = True
            session.context.state = UploadState.CA_SUCCESS_RECEIVED
            event_logger.emit(
                "ca_success",
                direction="RX",
                state=session.context.state,
                device_id=device_id,
                command="CA",
                hex_data=notification.hex,
            )

        await transport.write_without_response(FF02_UUID, CA_APPLY_FRAME)
        frames.append(CA_APPLY_FRAME)
        ca_apply_sent = True
        session.context.state = UploadState.CA_APPLY_SENT
        event_logger.emit(
            "write",
            direction="TX",
            state=session.context.state,
            device_id=device_id,
            uuid=FF02_UUID,
            command="CA",
            length=len(CA_APPLY_FRAME),
            hex_data=CA_APPLY_FRAME.hex().upper(),
        )
        business_state = UploadState.COMPLETE
        event_logger.emit(
            "upload_complete",
            state=business_state,
            device_id=device_id,
            packets_sent=packets_sent,
            bytes_sent=bytes_sent,
        )
    except UploadCancelledError as exc:
        cancellation_requested = True
        business_state = UploadState.CANCELLED
        failure = exc
        if session is not None:
            session.context.state = business_state
        event_logger.emit(
            "cancelled",
            state=business_state,
            device_id=device_id,
            error=str(exc),
        )
    except asyncio.CancelledError as exc:
        cancellation_requested = True
        business_state = UploadState.CANCELLED
        failure = exc
        if session is not None:
            session.context.state = business_state
        event_logger.emit(
            "cancelled",
            state=business_state,
            device_id=device_id,
            error="asyncio task cancelled",
        )
    except Exception as exc:
        business_state = UploadState.FAILED
        failure = exc
        if session is not None:
            session.context.state = business_state
        event_logger.emit(
            "failure",
            state=business_state,
            device_id=device_id,
            error=str(exc),
            error_type=type(exc).__name__,
        )
    finally:
        if session is not None:
            cleanup_errors = await cleanup_session(transport, session.context)
            if cleanup_errors and failure is None:
                failure = UploadError("；".join(cleanup_errors))
                business_state = UploadState.FAILED

    elapsed = active_clock.monotonic() - started_at
    return _result(
        success=business_state is UploadState.COMPLETE and failure is None,
        final_state=business_state,
        frames=frames,
        packets_sent=packets_sent,
        bytes_sent=bytes_sent,
        last_sequence=last_sequence,
        ca_success_received=ca_success_received,
        ca_apply_sent=ca_apply_sent,
        elapsed_seconds=elapsed,
        cancellation_requested=cancellation_requested,
        disconnected=not transport.is_connected,
        error=failure,
    )
