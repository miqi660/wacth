from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from pathlib import Path

from .bcsdial import BCSDIALPayload
from .errors import (
    ExpectedSha256RequiredError,
    GattValidationError,
    InvalidSha256Error,
    LogFileExistsError,
    MtuTooSmallError,
    PayloadSha256MismatchError,
    RealUploadError,
    RealUploadNotAuthorizedError,
    RealUploadPacketDelayError,
    WriteSizeTooSmallError,
)
from .logging_utils import Stage5Logger
from .stage5 import GattValidation

SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
STAGE6C_MINIMUM_MTU = 240
STAGE6C_MINIMUM_WRITE_WITHOUT_RESPONSE = 237
STAGE6C_PACKET_DELAY_MS = 45.0


@dataclass(frozen=True)
class RealUploadAuthorization:
    confirmed: bool
    expected_sha256: str | None
    log_file: Path | None = None
    minimum_mtu: int = STAGE6C_MINIMUM_MTU
    minimum_write_without_response: int = STAGE6C_MINIMUM_WRITE_WITHOUT_RESPONSE
    required_packet_delay_ms: float = STAGE6C_PACKET_DELAY_MS


def validate_local_authorization(
    payload: BCSDIALPayload,
    authorization: RealUploadAuthorization,
    *,
    packet_delay_ms: float,
) -> None:
    payload.validate()
    if not authorization.confirmed:
        raise RealUploadNotAuthorizedError(
            "Stage 6B build does not permit real BLE upload without explicit "
            "authorization；真实上传必须提供 --confirm-real-upload"
        )
    expected = authorization.expected_sha256
    if expected is None:
        raise ExpectedSha256RequiredError("真实上传必须提供 --expected-sha256")
    if SHA256_PATTERN.fullmatch(expected) is None:
        raise InvalidSha256Error("--expected-sha256 必须是 64 位十六进制")
    if not hmac.compare_digest(payload.sha256.lower(), expected.lower()):
        raise PayloadSha256MismatchError(
            f"文件 SHA-256 不匹配: actual={payload.sha256} expected={expected.upper()}"
        )
    if (
        authorization.required_packet_delay_ms != STAGE6C_PACKET_DELAY_MS
        or packet_delay_ms != STAGE6C_PACKET_DELAY_MS
    ):
        raise RealUploadPacketDelayError(
            "Stage 6C 首次真实上传的 --packet-delay-ms 必须严格等于 "
            f"{STAGE6C_PACKET_DELAY_MS:g}"
        )


def reserve_log_file(path: Path) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n"):
            pass
    except FileExistsError as exc:
        raise LogFileExistsError(f"真实上传日志已存在，拒绝覆盖: {path}") from exc
    except OSError as exc:
        raise RealUploadError(f"无法独占创建真实上传日志 {path}: {exc}") from exc


def validate_real_log_binding(
    authorization: RealUploadAuthorization,
    logger: Stage5Logger | None,
) -> None:
    if authorization.log_file is None:
        raise RealUploadError("真实上传必须提供 --log-file")
    if logger is None or logger.log_file is None:
        raise RealUploadError("真实上传必须使用已独占创建的日志")
    if logger.log_file.resolve() != authorization.log_file.resolve():
        raise RealUploadError("真实上传授权日志与实际日志路径不一致")
    if not authorization.log_file.is_file():
        raise RealUploadError("真实上传日志尚未独占创建")


def validate_runtime_capabilities(
    validation: GattValidation,
    authorization: RealUploadAuthorization,
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
    if validation.mtu_size is None:
        raise MtuTooSmallError("MTU 未知，拒绝真实上传")
    minimum_mtu = max(authorization.minimum_mtu, STAGE6C_MINIMUM_MTU)
    if validation.mtu_size < minimum_mtu:
        raise MtuTooSmallError(
            f"MTU {validation.mtu_size} 小于安全下限 {minimum_mtu}"
        )
    maximum = validation.maximum_write_without_response
    if maximum is None:
        raise WriteSizeTooSmallError("最大无响应写入长度未知，拒绝真实上传")
    minimum_write = max(
        authorization.minimum_write_without_response,
        STAGE6C_MINIMUM_WRITE_WITHOUT_RESPONSE,
    )
    if maximum < minimum_write:
        raise WriteSizeTooSmallError(
            "最大无响应写入长度 "
            f"{maximum} 小于安全下限 {minimum_write}"
        )
