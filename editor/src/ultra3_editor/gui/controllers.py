from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .. import (
    GreenLionStaticBuildInput,
    GreenLionStaticBuildResult,
    build_greenlion_static_diy,
)
from ..errors import (
    BuildError,
    BuildInputOutputSamePathError,
    BuildOutputExistsError,
    BuildRollbackError,
    EditOutputExistsError,
    EditVerificationError,
    EditorError,
    FileReadError,
    InputOutputSamePathError,
    InvalidExistingTimePositionError,
    NoChangeRequestedError,
    UnexpectedChangedBytesError,
    UnsupportedStaticDiySizeError,
    UnsupportedPillowVersionError,
    UnsupportedTemplateError,
)
from ..static_diy import (
    STATIC_DIY_SIZE,
    TIME_POSITION_OFFSET,
    StaticDiyInspection,
    TimePosition,
    inspect_static_diy,
)
from ..time_position import (
    TimePositionEditResult,
    set_time_position as execute_time_position_core,
)


@dataclass(frozen=True)
class UserFacingError:
    title: str
    message: str
    technical_details: str
    error_code: str | None = None
    path: object | None = None
    expected: object | None = None
    actual: object | None = None
    golden_status: object | None = None
    failed_cleanup_paths: tuple[object, ...] = ()
    original_error_type: str | None = None
    original_error_message: str | None = None


@dataclass(frozen=True)
class TimePositionEditPlan:
    input_path: Path
    output_path: Path
    target_position: TimePosition
    json_path: Path | None
    report_path: Path | None
    field_offset_hex: str
    before_hex: str
    after_hex: str
    changed_byte_count: int
    unchanged_byte_count: int


@dataclass(frozen=True)
class GreenLionGuiBuildPlan:
    image_path: Path
    template_path: Path
    output_path: Path
    json_path: Path | None
    report_path: Path | None
    profile: str


class OfflineGuiController:
    editing_available = True

    def load_file(self, path: str | Path) -> StaticDiyInspection:
        return inspect_static_diy(path)

    def prepare_greenlion_build(
        self,
        image_path: str | Path,
        template_path: str | Path,
        output_path: str | Path,
        *,
        json_path: str | Path | None,
        report_path: str | Path | None,
    ) -> GreenLionGuiBuildPlan:
        paths = {
            "image": Path(image_path).resolve(),
            "template": Path(template_path).resolve(),
            "output": Path(output_path).resolve(),
        }
        optional = {
            "json": Path(json_path).resolve() if json_path else None,
            "report": Path(report_path).resolve() if report_path else None,
        }
        keys = [
            str(path).casefold()
            for path in (*paths.values(), *optional.values())
            if path is not None
        ]
        if len(keys) != len(set(keys)):
            raise BuildInputOutputSamePathError(
                "输入图片、模板、BIN、JSON 和 Markdown 路径不能重复"
            )
        return GreenLionGuiBuildPlan(
            image_path=paths["image"],
            template_path=paths["template"],
            output_path=paths["output"],
            json_path=optional["json"],
            report_path=optional["report"],
            profile="GreenLion v0.2.4 exact · Pillow 10.4.0",
        )

    @staticmethod
    def execute_greenlion_build(
        plan: GreenLionGuiBuildPlan,
    ) -> GreenLionStaticBuildResult:
        return build_greenlion_static_diy(
            GreenLionStaticBuildInput(
                image_path=plan.image_path,
                template_path=plan.template_path,
                output_path=plan.output_path,
            ),
            json_path=plan.json_path,
            report_path=plan.report_path,
        )

    def prepare_time_position_edit(
        self,
        info: StaticDiyInspection,
        output_path: str | Path,
        target_position: TimePosition,
        *,
        include_json: bool,
        include_report: bool,
    ) -> TimePositionEditPlan:
        if info.time_position is target_position:
            raise NoChangeRequestedError(
                f"输入文件当前已是 {target_position.value}，无需修改"
            )
        output = Path(output_path).resolve()
        return TimePositionEditPlan(
            input_path=info.path,
            output_path=output,
            target_position=target_position,
            json_path=output.with_suffix(".json") if include_json else None,
            report_path=output.with_suffix(".md") if include_report else None,
            field_offset_hex=f"0x{TIME_POSITION_OFFSET:08X}",
            before_hex=f"{info.first_byte:02X}",
            after_hex=f"{target_position.byte_value:02X}",
            changed_byte_count=1,
            unchanged_byte_count=STATIC_DIY_SIZE - 1,
        )

    @staticmethod
    def execute_time_position_edit(
        plan: TimePositionEditPlan,
    ) -> TimePositionEditResult:
        return execute_time_position_core(
            input_path=plan.input_path,
            output_path=plan.output_path,
            position=plan.target_position,
            json_path=plan.json_path,
            report_path=plan.report_path,
        )

    @staticmethod
    def user_error(error: EditorError) -> UserFacingError:
        if isinstance(error, BuildRollbackError):
            title = "构建回滚未完成"
            message = "离线构建失败，可能存在未完成文件，请按技术详情人工检查。"
        elif isinstance(error, UnsupportedPillowVersionError):
            title = "Pillow 版本不受支持"
            message = "当前 exact profile 只支持 Pillow 10.4.0。"
        elif isinstance(error, UnsupportedTemplateError):
            title = "模板验证失败"
            message = "模板未通过公共核心的大小、17 字节头或 SHA-256 验证。"
        elif isinstance(error, BuildOutputExistsError):
            title = "输出文件已经存在"
            message = "为保护现有文件，Builder 不提供覆盖功能。"
        elif isinstance(error, BuildInputOutputSamePathError):
            title = "构建路径无效"
            message = "输入图片、模板和输出文件必须使用不同路径。"
        elif isinstance(error, BuildError):
            title = "离线构建失败"
            message = "公共 Builder 未完成构建，未生成可确认的成功结果。"
        elif isinstance(error, NoChangeRequestedError):
            title = "没有变化"
            message = "当前文件已经使用所选时间位置，未创建输出。"
        elif isinstance(error, InputOutputSamePathError):
            title = "输出路径无效"
            message = "输出路径不能与输入文件相同。"
        elif isinstance(error, EditOutputExistsError):
            title = "输出文件已经存在"
            message = "为保护现有文件，本工具不提供覆盖功能。"
        elif isinstance(error, UnsupportedStaticDiySizeError):
            title = "不支持的文件大小"
            message = "当前仅支持已验证的 351617 字节 GreenLion Static DIY BIN。"
        elif isinstance(error, InvalidExistingTimePositionError):
            title = "无法识别当前时间位置"
            message = "offset 0x00000000 的值必须是 00 或 01。"
        elif isinstance(error, UnexpectedChangedBytesError):
            title = "检测到预期之外的字节变化"
            message = "未保留本次输出。"
        elif isinstance(error, EditVerificationError):
            title = "输出验证失败"
            message = "本次创建的未完成文件已经清理，输入文件没有修改。"
        elif isinstance(error, FileReadError):
            title = "无法读取输入文件"
            message = "请确认文件仍存在且具有读取权限。"
        else:
            title = "离线编辑失败"
            message = "操作未完成，未创建或保留输出。"
        details = (
            [f"{type(error).__name__}: {error}"]
            if isinstance(error, BuildError)
            else [str(error)]
        )
        for name in ("error_code", "path", "expected", "actual", "golden_status"):
            value = getattr(error, name, None)
            if value is not None:
                details.append(f"{name}: {getattr(value, 'value', value)}")
        failed = tuple(getattr(error, "failed_cleanup_paths", ()))
        if failed:
            details.append("failed_cleanup_paths: " + ", ".join(map(str, failed)))
        original_type = getattr(error, "original_error_type", None)
        original_message = getattr(error, "original_error_message", None)
        if original_type is not None:
            details.append(f"original_error_type: {original_type}")
        if original_message is not None:
            details.append(f"original_error_message: {original_message}")
        return UserFacingError(
            title,
            message,
            "\n".join(details),
            error_code=getattr(error, "error_code", None),
            path=getattr(error, "path", None),
            expected=getattr(error, "expected", None),
            actual=getattr(error, "actual", None),
            golden_status=getattr(error, "golden_status", None),
            failed_cleanup_paths=failed,
            original_error_type=original_type,
            original_error_message=original_message,
        )
