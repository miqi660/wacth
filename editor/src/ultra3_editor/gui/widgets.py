from __future__ import annotations

from enum import Enum

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QSizePolicy, QWidget

from ..resource_geometry import MAIN_RESOURCE, ResourceCanvasSpec
from ..static_diy import TimePosition
from .theme import TOKENS


class BadgeState(str, Enum):
    VERIFIED = "verified"
    EXPERIMENTAL = "experimental"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class StatusBadge(QLabel):
    def __init__(self, text: str, state: BadgeState, parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("badge")
        self.setProperty("state", state.value)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAccessibleName(f"状态：{text}")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class ResourcePreview(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._resource = MAIN_RESOURCE
        self._position: TimePosition | None = None
        self._scale = 0.88
        self.setMinimumSize(300, 420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._update_accessible_name()

    def sizeHint(self) -> QSize:
        return QSize(430, 560)

    def set_resource(self, resource: ResourceCanvasSpec) -> None:
        self._resource = resource
        self._update_accessible_name()
        self.update()

    def set_position(self, position: TimePosition | None) -> None:
        self._position = position
        self.update()

    def set_scale(self, scale: float) -> None:
        self._scale = min(1.2, max(0.65, scale))
        self.update()

    @property
    def scale(self) -> float:
        return self._scale

    @property
    def resource(self) -> ResourceCanvasSpec:
        return self._resource

    def _update_accessible_name(self) -> None:
        self.setAccessibleName(
            f"{self._resource.label}资源预览 {self._resource.width}×{self._resource.height}，"
            "非物理显示几何"
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        available_w = max(1, self.width() - 60)
        available_h = max(1, self.height() - 64)
        ratio = self._resource.width / self._resource.height
        height = min(available_h, available_w / ratio) * self._scale
        width = height * ratio
        x = (self.width() - width) / 2
        y = (self.height() - height) / 2 + 8
        face = QRectF(x, y, width, height)

        painter.setPen(QPen(QColor(TOKENS["border_default"]), 2))
        painter.setBrush(QColor("#0B0D0F"))
        painter.drawRect(face)

        painter.setPen(QColor(TOKENS["text_secondary"]))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            QRectF(x, y - 28, width, 22),
            Qt.AlignmentFlag.AlignCenter,
            "RESOURCE PREVIEW · NOT PHYSICAL DISPLAY GEOMETRY",
        )

        painter.setPen(QColor(TOKENS["text_primary"]))
        painter.setFont(QFont("Segoe UI", 17, 600))
        painter.drawText(
            QRectF(x, y + height / 2 - 42, width, 32),
            Qt.AlignmentFlag.AlignCenter,
            f"{self._resource.name.upper()} RESOURCE",
        )

        painter.setPen(QColor(TOKENS["text_secondary"]))
        painter.setFont(QFont("Cascadia Mono", 10))
        painter.drawText(
            QRectF(x, y + height / 2, width, 28),
            Qt.AlignmentFlag.AlignCenter,
            f"{self._resource.width} × {self._resource.height} · VERIFIED · 5:6",
        )

        if self._position is not None and self._resource is MAIN_RESOURCE:
            marker_y = y + height * (0.2 if self._position is TimePosition.TOP else 0.76)
            marker = QRectF(x + width * 0.08, marker_y, width * 0.84, 38)
            painter.setPen(QPen(QColor(TOKENS["accent"]), 1))
            painter.setBrush(QColor(TOKENS["background_elevated"]))
            painter.drawRoundedRect(marker, 8, 8)
            painter.setPen(QColor(TOKENS["accent_hover"]))
            painter.setFont(QFont("Cascadia Mono", 9, 600))
            painter.drawText(
                marker,
                Qt.AlignmentFlag.AlignCenter,
                f"SCHEMATIC TIME POSITION · {self._position.value.upper()}",
            )
