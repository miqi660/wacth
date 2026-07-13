class EditorError(Exception):
    """Editor 可预期错误基类。"""


class FileReadError(EditorError):
    """输入文件不存在、类型错误或无法读取。"""


class BCSDIALValidationError(EditorError):
    """输入不符合 BCSDIAL 基础格式。"""


class OffsetError(EditorError):
    """偏移格式错误或超出文件边界。"""


class ReportExistsError(EditorError):
    """输出报告已存在，拒绝覆盖。"""


class KnownPatchVerificationError(EditorError):
    """样本对不符合已确认的单字节补丁。"""
