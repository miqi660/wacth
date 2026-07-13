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
