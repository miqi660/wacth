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


class BuildError(EditorError):
    """GreenLion Static DIY 构建失败。"""

    error_code = "build_error"

    def __init__(
        self,
        message: str,
        *,
        path: object | None = None,
        expected: object | None = None,
        actual: object | None = None,
        golden_status: object | None = None,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.expected = expected
        self.actual = actual
        self.golden_status = golden_status


class BuilderInputError(BuildError):
    """构建输入不存在、类型错误或无法读取。"""

    error_code = "builder_input_error"


class UnsupportedImageFormatError(BuilderInputError):
    """图片容器不在已验证范围。"""

    error_code = "unsupported_image_format"


class InvalidImageError(BuilderInputError):
    """图片内容无法由固定版本 Pillow 解码。"""

    error_code = "invalid_image"


class UnsupportedTemplateError(BuildError):
    """模板不等于已验证的 GreenLion Static DIY 模板。"""

    error_code = "unsupported_template"


class UnsupportedBuilderConfigError(BuildError):
    """构建配置超出 Stage 8B-1 exact 范围。"""

    error_code = "unsupported_builder_config"


class UnsupportedPillowVersionError(BuildError):
    """Pillow 版本不等于冻结验证版本。"""

    error_code = "unsupported_pillow_version"


class BuildOutputExistsError(BuildError):
    """构建输出目标已存在，拒绝覆盖。"""

    error_code = "build_output_exists"


class BuildInputOutputSamePathError(BuildError):
    """构建输入与任一输出目标指向同一路径。"""

    error_code = "build_input_output_same_path"


class BuildVerificationError(BuildError):
    """构建结果未通过内存或写后复核。"""

    error_code = "build_verification_error"


class BuildRollbackError(BuildVerificationError):
    """本次构建创建的文件未能全部清理。"""

    error_code = "build_rollback_error"

    def __init__(
        self,
        original_error: Exception,
        failed_cleanup_paths: tuple[object, ...],
    ) -> None:
        if isinstance(original_error, BuildRollbackError):
            original_error_type = original_error.original_error_type
            original_error_message = original_error.original_error_message
            failed_cleanup_paths = tuple(
                dict.fromkeys((*original_error.failed_cleanup_paths, *failed_cleanup_paths))
            )
        else:
            original_error_type = type(original_error).__name__
            original_error_message = str(original_error)
        paths = ", ".join(str(path) for path in failed_cleanup_paths)
        super().__init__(
            f"构建失败且回滚未完成，可能存在未完成文件: {paths}",
            path=failed_cleanup_paths[0] if failed_cleanup_paths else None,
            expected="all_created_files_removed",
            actual=tuple(str(path) for path in failed_cleanup_paths),
        )
        self.original_error_type = original_error_type
        self.original_error_message = original_error_message
        self.failed_cleanup_paths = failed_cleanup_paths
