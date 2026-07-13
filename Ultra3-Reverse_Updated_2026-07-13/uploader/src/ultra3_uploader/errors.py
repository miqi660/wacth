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

