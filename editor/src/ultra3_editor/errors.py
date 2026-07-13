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


class CaptureReadError(EditorError):
    """抓包文件不存在、为空或无法读取。"""


class CaptureFormatError(EditorError):
    """抓包行或 HEX payload 无法安全识别。"""


class FrameValidationError(EditorError):
    """C8/C9 帧结构不符合已验证协议。"""


class SessionSelectionError(EditorError):
    """找不到唯一可重组的上传会话。"""


class ReconstructionError(EditorError):
    """上传会话未通过严格重组验证。"""


class UnsupportedStaticDiySizeError(EditorError):
    """静态 DIY 文件大小不在当前已验证范围。"""


class InvalidExistingTimePositionError(EditorError):
    """静态 DIY 首字节不是已验证的时间位置值。"""


class TimePositionEditError(EditorError):
    """GreenLion Static DIY 时间位置编辑失败。"""


class NoChangeRequestedError(TimePositionEditError):
    """请求的位置与输入文件当前位置相同。"""


class InputOutputSamePathError(TimePositionEditError):
    """输入文件与任一输出目标指向同一路径。"""


class EditOutputExistsError(TimePositionEditError):
    """编辑输出目标已存在，拒绝覆盖。"""


class EditVerificationError(TimePositionEditError):
    """编辑结果写入后未通过复验。"""


class UnexpectedChangedBytesError(EditVerificationError):
    """编辑结果改变了 offset 0 之外的字节。"""
