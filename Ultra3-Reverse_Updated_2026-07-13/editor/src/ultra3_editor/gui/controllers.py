from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..errors import (
    EditorError,
    FileReadError,
    InvalidExistingTimePositionError,
    UnsupportedStaticDiySizeError,
)
from ..static_diy import StaticDiyInspection, inspect_static_diy


@dataclass(frozen=True)
class UserFacingError:
    title: str
    message: str
    technical_details: str


class OfflineGuiController:
    editing_available = False

    def load_file(self, path: str | Path) -> StaticDiyInspection:
        return inspect_static_diy(path)

    @staticmethod
    def user_error(error: EditorError) -> UserFacingError:
        if isinstance(error, UnsupportedStaticDiySizeError):
            title = "不支持的文件大小"
            message = "当前 GUI 仅允许检查已验证的 351617 字节 GreenLion 静态 DIY 文件。"
        elif isinstance(error, InvalidExistingTimePositionError):
            title = "无法识别时间位置"
            message = "offset 0x00000000 的值不是 00 或 01。"
        elif isinstance(error, FileReadError):
            title = "无法打开文件"
            message = "请选择存在且可读取的普通 BIN 文件。"
        else:
            title = "文件检查失败"
            message = "输入文件未通过当前离线 GUI 的验证。"
        return UserFacingError(title, message, str(error))
