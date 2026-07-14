class Ultra3UploaderError(Exception):
    """Uploader 可预期错误基类。"""


class BCSDIALValidationError(Ultra3UploaderError):
    """输入文件不是可发送的动态 BCSDIAL。"""


class FrameError(Ultra3UploaderError):
    """协议帧格式或校验错误。"""


class CaptureParseError(Ultra3UploaderError):
    """Frida 抓包记录无法解析。"""


class OutputExistsError(Ultra3UploaderError):
    """输出路径已存在且未允许覆盖。"""


class StaticTransferPlanError(Ultra3UploaderError):
    """静态 Handoff 离线传输计划无效或无法生成。"""


class FixedStaticProfileError(StaticTransferPlanError):
    """固定静态传输 Profile 不受支持或参数不匹配。"""


class FixedStaticControlFrameError(StaticTransferPlanError):
    """固定静态 C8/CA 控制帧不符合冻结证据。"""


class FixedStaticVerificationError(StaticTransferPlanError):
    """固定静态离线传输计划复核失败。"""


class FixedStaticOutputError(StaticTransferPlanError):
    """固定静态离线计划无法安全写入。"""


class BleTransportError(Ultra3UploaderError):
    """BLE 后端操作失败。"""


class DeviceNotFoundError(BleTransportError):
    """扫描结果中不存在目标设备。"""


class MultipleDevicesError(BleTransportError):
    """存在多个同名设备，无法安全自动选择。"""


class GattValidationError(BleTransportError):
    """目标 GATT 服务或特征不符合已验证要求。"""


class BleDisconnectedError(BleTransportError):
    """BLE 连接意外断开。"""


class LogWriteError(Ultra3UploaderError):
    """结构化日志无法写入。"""


class PrepareError(Ultra3UploaderError):
    """动态 BCSDIAL 准备握手失败。"""


class PrepareTimeoutError(PrepareError):
    """准备握手等待已确认通知超时。"""


class CountdownError(PrepareError):
    """BC72 倒计时缺失、无效或乱序。"""


class C8ResponseMismatchError(PrepareError):
    """C8 response 与当前输入文件不匹配。"""


class UploadError(Ultra3UploaderError):
    """动态 BCSDIAL 完整上传模拟失败。"""


class UploadSafetyError(UploadError):
    """Stage 6B 真实 BLE 上传安全锁被触发。"""


class RealUploadError(UploadSafetyError):
    """真实上传授权或安全检查失败。"""


class RealUploadNotAuthorizedError(RealUploadError):
    """缺少真实上传显式确认。"""


class ExpectedSha256RequiredError(RealUploadError):
    """真实上传缺少期望 SHA-256。"""


class InvalidSha256Error(RealUploadError):
    """期望 SHA-256 格式无效。"""


class PayloadSha256MismatchError(RealUploadError):
    """输入文件 SHA-256 与授权值不匹配。"""


class RealUploadPacketDelayError(RealUploadError):
    """真实上传包间隔不符合当前安全要求。"""


class MtuTooSmallError(RealUploadError):
    """MTU 未知或小于真实上传安全下限。"""


class WriteSizeTooSmallError(RealUploadError):
    """最大无响应写入长度未知或小于安全下限。"""


class LogFileExistsError(RealUploadError):
    """真实上传日志已存在，禁止覆盖。"""


class UnsupportedTransportError(RealUploadError):
    """上传 Transport 类型未知或不受支持。"""


class UploadCancelledError(UploadError):
    """上传被显式取消。"""


class CAProtocolError(UploadError):
    """CA success 到达时机或内容不符合已验证顺序。"""
