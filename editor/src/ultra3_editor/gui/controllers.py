from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..errors import (
    EditOutputExistsError,
    EditVerificationError,
    EditorError,
    FileReadError,
    InputOutputSamePathError,
    InvalidExistingTimePositionError,
    NoChangeRequestedError,
    UnexpectedChangedBytesError,
    UnsupportedStaticDiySizeError,
)
from ..static_diy import (
    STATIC_DIY_SIZE,
    TIME_POSITION_OFFSET,
    StaticDiyInspection,
    TimePosition,
    inspect_static_diy,
)
from ..time_position import TimePositionEditResult, set_time_position


@dataclass(frozen=True)
class UserFacingError:
    title: str
    message: str
    technical_details: str


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


class OfflineGuiController:
    editing_available = True

    def load_file(self, path: str | Path) -> StaticDiyInspection:
        return inspect_static_diy(path)

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
        return set_time_position(
            input_path=plan.input_path,
            output_path=plan.output_path,
            position=plan.target_position,
            json_path=plan.json_path,
            report_path=plan.report_path,
        )

    @staticmethod
    def user_error(error: EditorError) -> UserFacingError:
        if isinstance(error, NoChangeRequestedError):
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
        return UserFacingError(title, message, str(error))
