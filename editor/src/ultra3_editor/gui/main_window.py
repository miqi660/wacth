from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from ..errors import EditorError
from ..resource_geometry import MAIN_RESOURCE, THUMBNAIL_RESOURCE
from ..static_diy import StaticDiyInspection, TimePosition
from .controllers import GreenLionGuiBuildPlan, OfflineGuiController, TimePositionEditPlan
from .widgets import BadgeState, ResourcePreview, StatusBadge


class MainWindow(QMainWindow):
    def __init__(self, controller: OfflineGuiController | None = None) -> None:
        super().__init__()
        self.controller = controller or OfflineGuiController()
        self.current_info: StaticDiyInspection | None = None
        self.last_error: str | None = None
        self.last_dialog: QDialog | None = None
        self.last_result = None
        self.last_plan: TimePositionEditPlan | None = None
        self.builder_image_path: Path | None = None
        self.builder_template_path: Path | None = None
        self.builder_last_result = None
        self.builder_last_plan: GreenLionGuiBuildPlan | None = None
        self.builder_last_error: str | None = None
        self._busy = False
        self.setWindowTitle("Ultra3 Lab — Offline GreenLion Workbench")
        self.resize(1280, 800)
        self.setMinimumSize(1050, 680)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget(objectName="root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_title_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        self.workspace = QStackedWidget()
        self.edit_page = self._build_edit_page()
        self.placeholder_page = self._build_placeholder_page()
        self.workspace.addWidget(self.edit_page)
        self.workspace.addWidget(self.placeholder_page)
        body.addWidget(self.workspace, 1)
        body_widget = QWidget()
        body_widget.setLayout(body)
        layout.addWidget(body_widget, 1)
        layout.addWidget(self._build_status_bar())
        self.setCentralWidget(root)

    def _build_title_bar(self) -> QWidget:
        bar = QFrame(objectName="titleBar")
        bar.setFixedHeight(64)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(22, 0, 22, 0)
        title = QLabel("Ultra3 Lab", objectName="appTitle")
        subtitle = QLabel("OFFLINE ENGINEERING WORKBENCH", objectName="muted")
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch()
        self.current_file_label = QLabel("未加载文件", objectName="mono")
        self.current_file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.current_file_label, 1)
        layout.addStretch()
        scope_box = QVBoxLayout()
        scope_box.setSpacing(1)
        scope_box.addWidget(QLabel("VERIFIED SCOPE", objectName="muted"))
        scope_box.addWidget(QLabel("GreenLion Static DIY · NJ-LEJ-2.1.7"))
        layout.addLayout(scope_box)
        return bar

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame(objectName="sidebar")
        sidebar.setFixedWidth(212)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 20, 12, 16)
        layout.setSpacing(5)
        group = QButtonGroup(self)
        group.setExclusive(True)
        labels = ("概览", "表盘制作", "BIN 编辑", "文件对比", "验证报告", "设置")
        self.nav_buttons: dict[str, QPushButton] = {}
        for label in labels:
            button = QPushButton(label, objectName="navButton")
            button.setCheckable(True)
            button.setAccessibleName(f"导航：{label}")
            button.clicked.connect(lambda checked, name=label: self._navigate(name))
            group.addButton(button)
            layout.addWidget(button)
            self.nav_buttons[label] = button
        self.nav_buttons["BIN 编辑"].setChecked(True)
        layout.addStretch()
        gate = QFrame(objectName="card")
        gate_layout = QVBoxLayout(gate)
        gate_layout.setContentsMargins(12, 12, 12, 12)
        gate_layout.addWidget(StatusBadge("BIN EDIT AVAILABLE", BadgeState.VERIFIED))
        gate_text = QLabel(
            "时间位置编辑可用\nVerified Builder 可用 · 全程离线",
            objectName="muted",
        )
        gate_text.setWordWrap(True)
        gate_layout.addWidget(gate_text)
        layout.addWidget(gate)
        about = QPushButton("关于已验证范围")
        about.clicked.connect(self.show_about_dialog)
        layout.addWidget(about)
        return sidebar

    def _build_edit_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(22, 20, 18, 18)
        layout.setSpacing(18)
        layout.addWidget(self._build_preview_panel(), 1)
        layout.addWidget(self._build_properties_panel())
        return page

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        heading = QHBoxLayout()
        heading.addWidget(QLabel("资源画布", objectName="pageTitle"))
        heading.addStretch()
        for text, callback in (
            ("−", lambda: self.preview.set_scale(self.preview.scale - 0.08)),
            ("适应", lambda: self.preview.set_scale(0.88)),
            ("100%", lambda: self.preview.set_scale(1.0)),
            ("+", lambda: self.preview.set_scale(self.preview.scale + 0.08)),
        ):
            button = QPushButton(text)
            button.setAccessibleName(f"预览缩放：{text}")
            button.clicked.connect(callback)
            heading.addWidget(button)
        layout.addLayout(heading)
        self.resource_tabs = QTabBar()
        self.resource_tabs.setAccessibleName("资源画布选择")
        self.resource_tabs.addTab("主图 320×384")
        self.resource_tabs.addTab("缩略图 210×252")
        self.resource_tabs.currentChanged.connect(self._select_resource_tab)
        layout.addWidget(self.resource_tabs)
        self.preview = ResourcePreview()
        layout.addWidget(self.preview, 1)
        note = QLabel(
            "Resource preview · Not physical display geometry · 不代表完整可见区域",
            objectName="muted",
        )
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(note)
        return panel

    def _build_properties_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(382)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(12)
        layout.addWidget(self._build_file_card())
        layout.addWidget(self._build_time_card())
        layout.addWidget(self._build_resource_card())
        layout.addWidget(self._build_export_card())
        layout.addWidget(self._build_scope_card())
        layout.addStretch()
        scroll.setWidget(content)
        self.properties_scroll = scroll
        return scroll

    def _new_card(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame(objectName="card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 14, 15, 15)
        layout.setSpacing(8)
        layout.addWidget(QLabel(title, objectName="sectionTitle"))
        return card, layout

    def _build_file_card(self) -> QWidget:
        card, layout = self._new_card("文件信息")
        top = QHBoxLayout()
        top.addWidget(QLabel("GreenLion Static DIY"))
        top.addStretch()
        self.file_badge = StatusBadge("NO FILE", BadgeState.UNKNOWN)
        top.addWidget(self.file_badge)
        layout.addLayout(top)
        self.size_value = self._field(layout, "文件大小", "—")
        self.main_size_value = self._field(layout, "Main resource size", "320 × 384")
        self.thumbnail_size_value = self._field(
            layout,
            "Thumbnail resource size",
            "210 × 252",
        )
        self.aspect_ratio_value = self._field(layout, "Resource aspect ratio", "5:6")
        self.physical_geometry_value = self._field(
            layout,
            "Physical display geometry",
            "UNKNOWN",
        )
        self.visible_area_value = self._field(layout, "Visible display area", "UNKNOWN")
        self.firmware_scope_value = self._field(
            layout,
            "Firmware scope",
            "NJ-LEJ-2.1.7",
        )
        self.first_byte_value = self._field(layout, "首字节", "—")
        self.position_value = self._field(layout, "检测时间位置", "—")
        layout.addWidget(QLabel("输入 SHA-256", objectName="fieldLabel"))
        self.sha_value = QPlainTextEdit(objectName="mono")
        self.sha_value.setReadOnly(True)
        self.sha_value.setMaximumHeight(66)
        self.sha_value.setPlainText("—")
        layout.addWidget(self.sha_value)
        copy_sha = QPushButton("复制完整 SHA-256")
        copy_sha.clicked.connect(self._copy_sha)
        layout.addWidget(copy_sha)
        layout.addWidget(QLabel("文件路径", objectName="fieldLabel"))
        path_row = QHBoxLayout()
        self.path_value = QLineEdit("—", objectName="mono")
        self.path_value.setReadOnly(True)
        path_row.addWidget(self.path_value, 1)
        copy_path = QPushButton("复制")
        copy_path.clicked.connect(self._copy_path)
        path_row.addWidget(copy_path)
        layout.addLayout(path_row)
        open_button = QPushButton("打开 BIN")
        open_button.setObjectName("openFileButton")
        open_button.clicked.connect(self._choose_file)
        layout.addWidget(open_button)
        return card

    def _build_time_card(self) -> QWidget:
        card, layout = self._new_card("时间位置示意")
        row = QHBoxLayout()
        row.addWidget(StatusBadge("VERIFIED / EDITABLE", BadgeState.VERIFIED))
        row.addStretch()
        row.addWidget(QLabel("offset 0x00000000", objectName="mono"))
        layout.addLayout(row)
        self.current_position = self._field(layout, "当前位置", "—")
        layout.addWidget(QLabel("目标位置", objectName="fieldLabel"))
        radio_row = QHBoxLayout()
        self.top_radio = QRadioButton("上方")
        self.bottom_radio = QRadioButton("下方")
        for radio in (self.top_radio, self.bottom_radio):
            radio.setEnabled(False)
            radio.setToolTip("加载有效 BIN 后可选择目标位置")
            radio.toggled.connect(self._update_edit_state)
            radio_row.addWidget(radio)
        layout.addLayout(radio_row)
        self.change_summary = QLabel(
            "尚未加载文件\nOffset: 0x00000000\nValue: —\nChanged: 0 bytes\nUnchanged: —",
            objectName="mono",
        )
        self.change_summary.setWordWrap(True)
        layout.addWidget(self.change_summary)
        gate = QLabel(
            "仅调用已验证的 Stage 7B-1 公共核心；预览位置为 SCHEMATIC。",
            objectName="muted",
        )
        gate.setWordWrap(True)
        layout.addWidget(gate)
        return card

    def _build_resource_card(self) -> QWidget:
        card, layout = self._new_card("GreenLion Static Builder")
        self.builder_state_badge = StatusBadge("NOT READY", BadgeState.UNKNOWN)
        layout.addWidget(self.builder_state_badge)

        self.main_resource_status = self._field(layout, "输入图片", "NOT SELECTED")
        self.builder_image_meta = QLabel("PNG / JPEG · 未选择", objectName="mono")
        self.builder_image_meta.setWordWrap(True)
        layout.addWidget(self.builder_image_meta)
        self.builder_source_preview = QLabel("输入图片预览", objectName="mono")
        self.builder_source_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.builder_source_preview.setMinimumHeight(150)
        self.builder_source_preview.setFrameShape(QFrame.Shape.StyledPanel)
        layout.addWidget(self.builder_source_preview)
        self.choose_main_button = QPushButton("选择图片")
        self.choose_main_button.clicked.connect(self._choose_builder_image)
        layout.addWidget(self.choose_main_button)
        preview_notice = QLabel(
            "输入图片预览，仅用于选择确认，不代表最终 RGB565、裁剪或设备显示效果。",
            objectName="muted",
        )
        preview_notice.setWordWrap(True)
        self.builder_preview_notice = preview_notice
        layout.addWidget(preview_notice)

        self.template_status_badge = StatusBadge("NONE", BadgeState.UNKNOWN)
        layout.addWidget(self.template_status_badge)
        self.builder_template_status = self._field(layout, "模板 BIN", "NOT SELECTED")
        self.choose_template_button = QPushButton("选择模板")
        self.choose_template_button.clicked.connect(self._choose_builder_template)
        layout.addWidget(self.choose_template_button)
        template_note = QLabel(
            "构建时由公共核心验证大小、17 字节头和 SHA-256。",
            objectName="muted",
        )
        template_note.setWordWrap(True)
        layout.addWidget(template_note)

        self.thumbnail_resource_status = self._field(
            layout,
            "Thumbnail resource",
            "AUTO FROM MAIN IMAGE · 210 × 252",
        )
        self.choose_thumbnail_button = QPushButton("选择缩略图（不支持）")
        self.choose_thumbnail_button.setEnabled(False)
        layout.addWidget(self.choose_thumbnail_button)
        thumbnail_note = QLabel(
            "由公共核心从原始输入独立生成，不从主资源二次缩放。",
            objectName="muted",
        )
        thumbnail_note.setWordWrap(True)
        layout.addWidget(thumbnail_note)

        layout.addWidget(QLabel("Exact profile（只读）", objectName="fieldLabel"))
        self.fit_mode = QComboBox()
        self.fit_mode.addItems(("cover（固定）",))
        self.fit_mode.setEnabled(False)
        layout.addWidget(self.fit_mode)
        self.builder_profile = QLabel(
            "GreenLion Static DIY · NJ-LEJ-2.1.7\n"
            "Main 320×384 · Thumbnail 210×252\n"
            "cover · bilinear · truncate RGB565\n"
            "greenlion-" "next-high · Pillow 10.4.0\n"
            "output 351617 bytes · template offset 0 preserved",
            objectName="mono",
        )
        self.builder_profile.setWordWrap(True)
        self.builder_profile.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.builder_profile)

        layout.addWidget(QLabel("BIN 输出", objectName="fieldLabel"))
        self.builder_output_path = QLineEdit(objectName="mono")
        self.builder_output_path.setPlaceholderText("选择新的完整 BIN 输出路径")
        self.builder_output_path.textChanged.connect(self._builder_output_changed)
        layout.addWidget(self.builder_output_path)
        self.select_builder_output_button = QPushButton("选择 BIN 输出")
        self.select_builder_output_button.clicked.connect(self._choose_builder_output)
        layout.addWidget(self.select_builder_output_button)

        self.builder_json_checkbox = QCheckBox("生成 JSON 构建记录")
        self.builder_report_checkbox = QCheckBox("生成 Markdown 构建报告")
        self.builder_json_checkbox.setChecked(True)
        self.builder_report_checkbox.setChecked(True)
        layout.addWidget(self.builder_json_checkbox)
        self.builder_json_path = QLineEdit(objectName="mono")
        self.builder_json_path.setPlaceholderText("JSON 输出路径")
        layout.addWidget(self.builder_json_path)
        layout.addWidget(self.builder_report_checkbox)
        self.builder_report_path = QLineEdit(objectName="mono")
        self.builder_report_path.setPlaceholderText("Markdown 输出路径")
        layout.addWidget(self.builder_report_path)
        for control in (
            self.builder_json_checkbox,
            self.builder_report_checkbox,
            self.builder_json_path,
            self.builder_report_path,
        ):
            if isinstance(control, QCheckBox):
                control.stateChanged.connect(self._update_builder_state)
            else:
                control.textChanged.connect(self._update_builder_state)

        self.builder_generate_button = QPushButton("生成完整表盘 BIN")
        self.builder_generate_button.setEnabled(False)
        self.builder_generate_button.clicked.connect(self._generate_builder_bin)
        layout.addWidget(self.builder_generate_button)
        gate = QLabel(
            "只调用 Stage 8B-1 公共 Builder 一次；不覆盖、不上传、不进入时间位置编辑。",
            objectName="muted",
        )
        gate.setWordWrap(True)
        layout.addWidget(gate)
        self.resource_controls = (
            self.choose_main_button,
            self.choose_template_button,
            self.choose_thumbnail_button,
            self.fit_mode,
            self.builder_generate_button,
        )
        return card

    def _build_export_card(self) -> QWidget:
        card, layout = self._new_card("BIN 编辑导出")
        self.output_path = QLineEdit(objectName="mono")
        self.output_path.setPlaceholderText("选择新的输出 BIN 路径")
        self.output_path.setEnabled(False)
        self.output_path.textChanged.connect(self._update_edit_state)
        layout.addWidget(self.output_path)
        self.select_output_button = QPushButton("选择输出 BIN")
        self.select_output_button.setEnabled(False)
        self.select_output_button.clicked.connect(self._choose_output)
        layout.addWidget(self.select_output_button)
        self.json_checkbox = QCheckBox("生成 JSON 编辑记录")
        self.markdown_checkbox = QCheckBox("生成 Markdown 编辑报告")
        for checkbox in (self.json_checkbox, self.markdown_checkbox):
            checkbox.setChecked(True)
            checkbox.setEnabled(False)
            checkbox.stateChanged.connect(self._update_edit_state)
            layout.addWidget(checkbox)
        self.generate_button = QPushButton("生成新 BIN", objectName="primaryButton")
        self.generate_button.setEnabled(False)
        self.generate_button.setToolTip("只生成新的离线 BIN，不修改输入，不执行上传")
        self.generate_button.clicked.connect(self._generate_new_bin)
        layout.addWidget(self.generate_button)
        return card

    def _build_scope_card(self) -> QWidget:
        card, layout = self._new_card("功能证据等级")
        self.scope_card = card
        states = (
            ("资源画布", "VERIFIED", BadgeState.VERIFIED),
            ("时间位置", "VERIFIED", BadgeState.VERIFIED),
            ("Builder", "AVAILABLE", BadgeState.VERIFIED),
            ("时间颜色", "UNKNOWN", BadgeState.UNKNOWN),
            ("日期 / 星期", "UNSUPPORTED", BadgeState.UNSUPPORTED),
            ("步数 / 卡路里 / 心率", "UNSUPPORTED", BadgeState.UNSUPPORTED),
            ("真机上传", "OFFLINE ONLY", BadgeState.UNSUPPORTED),
        )
        self.unsupported_controls: list[QPushButton] = []
        for label, status, state in states:
            row = QHBoxLayout()
            control = QPushButton(label)
            control.setEnabled(False)
            self.unsupported_controls.append(control)
            row.addWidget(control, 1)
            badge = StatusBadge(status, state)
            if label == "Builder":
                self.builder_status = badge
            row.addWidget(badge)
            layout.addLayout(row)
        return card

    def _field(self, layout: QVBoxLayout, label: str, value: str) -> QLabel:
        row = QHBoxLayout()
        row.addWidget(QLabel(label, objectName="fieldLabel"))
        row.addStretch()
        result = QLabel(value, objectName="mono")
        result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByKeyboard | Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(result)
        layout.addLayout(row)
        return result

    def _build_placeholder_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(80, 80, 80, 80)
        layout.addStretch()
        card = QFrame(objectName="placeholderCard")
        card.setMaximumWidth(620)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        self.placeholder_title = QLabel("尚未接入 GUI", objectName="pageTitle")
        self.placeholder_message = QLabel(
            "当前版本仅提供命令行能力，未添加未经验证的 GUI 操作。",
            objectName="muted",
        )
        self.placeholder_message.setWordWrap(True)
        card_layout.addWidget(StatusBadge("UNSUPPORTED", BadgeState.UNSUPPORTED))
        card_layout.addWidget(self.placeholder_title)
        card_layout.addWidget(self.placeholder_message)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        return page

    def _build_status_bar(self) -> QWidget:
        bar = QFrame(objectName="statusBar")
        bar.setFixedHeight(32)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 0, 18, 0)
        self.status_label = QLabel("No file loaded")
        layout.addWidget(self.status_label)
        layout.addStretch()
        self.changed_label = QLabel("Changed bytes: 0", objectName="mono")
        layout.addWidget(self.changed_label)
        layout.addSpacing(28)
        self.ble_label = QLabel("BLE usage: 0", objectName="mono")
        layout.addWidget(self.ble_label)
        layout.addSpacing(28)
        self.mode_label = QLabel("OFFLINE EDIT")
        layout.addWidget(self.mode_label)
        return bar

    def _select_resource_tab(self, index: int) -> None:
        resource = MAIN_RESOURCE if index == 0 else THUMBNAIL_RESOURCE
        self.preview.set_resource(resource)

    def _navigate(self, name: str) -> None:
        if name in ("表盘制作", "BIN 编辑"):
            self.workspace.setCurrentWidget(self.edit_page)
            return
        self.placeholder_title.setText(name)
        if name == "设置":
            self.placeholder_message.setText(
                "设置尚未持久化。当前固定为：深色主题、完整 SHA-256、零 BLE、无自动打开。"
            )
        else:
            self.placeholder_message.setText(
                "当前页面尚未接入；资源构建请使用表盘制作，时间位置编辑请使用 BIN 编辑。"
            )
        self.workspace.setCurrentWidget(self.placeholder_page)

    def _choose_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "打开 GreenLion Static DIY BIN",
            "",
            "BIN files (*.bin);;All files (*)",
        )
        if filename:
            self.load_file(filename)

    def _choose_output(self) -> None:
        if self.current_info is None:
            return
        target = self._selected_target()
        suffix = target.value if target is not None else "edited"
        suggestion = self.current_info.path.with_name(
            f"{self.current_info.path.stem}_{suffix}.bin"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "选择新的输出 BIN",
            str(suggestion),
            "BIN files (*.bin);;All files (*)",
        )
        if filename:
            self.output_path.setText(filename)

    def _choose_builder_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择 PNG/JPEG 输入图片",
            "",
            "Images (*.png *.jpg *.jpeg);;All files (*)",
        )
        if filename:
            self.select_builder_image(filename)

    def select_builder_image(self, path: str | Path, *, show_error: bool = True) -> bool:
        image_path = Path(path).resolve()
        reader = QImageReader(str(image_path))
        image_format = bytes(reader.format()).decode("ascii", errors="replace").upper()
        size = reader.size()
        if not reader.canRead() or image_format not in {"PNG", "JPEG", "JPG"}:
            self.builder_image_path = None
            self.main_resource_status.setText("INVALID")
            self.builder_image_meta.setText("仅支持可读取的 PNG / JPEG")
            self.builder_last_error = reader.errorString() or "不支持的图片"
            self._update_builder_state()
            if show_error:
                self._show_error(
                    "无法预览输入图片",
                    "请选择有效的 PNG 或 JPEG 图片。",
                    self.builder_last_error,
                )
            return False
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return False
        self.builder_image_path = image_path
        self.main_resource_status.setText(image_path.name)
        self.main_resource_status.setToolTip(str(image_path))
        self.builder_image_meta.setText(
            f"{image_format} · {size.width()} × {size.height()} · SOURCE PREVIEW"
        )
        self.builder_source_preview.setPixmap(
            pixmap.scaled(
                270,
                170,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.builder_source_preview.setToolTip(str(image_path))
        self.builder_last_error = None
        self._update_builder_state()
        return True

    def _choose_builder_template(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "选择 GreenLion Static DIY 模板",
            "",
            "BIN files (*.bin);;All files (*)",
        )
        if filename:
            self.select_builder_template(filename)

    def select_builder_template(self, path: str | Path) -> None:
        self.builder_template_path = Path(path).resolve()
        self.builder_template_status.setText(self.builder_template_path.name)
        self.builder_template_status.setToolTip(str(self.builder_template_path))
        self._set_badge(
            self.template_status_badge,
            "SELECTED · VALIDATION PENDING",
            BadgeState.EXPERIMENTAL,
        )
        self._update_builder_state()

    def _choose_builder_output(self) -> None:
        suggestion = "greenlion_static.bin"
        if self.builder_image_path is not None:
            suggestion = f"{self.builder_image_path.stem}_greenlion.bin"
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "选择新的完整 BIN 输出",
            suggestion,
            "BIN files (*.bin);;All files (*)",
        )
        if filename:
            self.builder_output_path.setText(filename)

    def _builder_output_changed(self, text: str) -> None:
        output = Path(text.strip()) if text.strip() else None
        self.builder_json_path.setText(str(output.with_suffix(".json")) if output else "")
        self.builder_report_path.setText(str(output.with_suffix(".md")) if output else "")
        self._update_builder_state()

    def _current_builder_plan(self) -> GreenLionGuiBuildPlan | None:
        output = self.builder_output_path.text().strip()
        if self.builder_image_path is None or self.builder_template_path is None or not output:
            return None
        json_text = self.builder_json_path.text().strip()
        report_text = self.builder_report_path.text().strip()
        if self.builder_json_checkbox.isChecked() and not json_text:
            return None
        if self.builder_report_checkbox.isChecked() and not report_text:
            return None
        try:
            return self.controller.prepare_greenlion_build(
                self.builder_image_path,
                self.builder_template_path,
                output,
                json_path=json_text if self.builder_json_checkbox.isChecked() else None,
                report_path=(
                    report_text if self.builder_report_checkbox.isChecked() else None
                ),
            )
        except EditorError:
            return None

    def _update_builder_state(self, *_args) -> None:
        controls_enabled = not self._busy
        for control in (
            self.choose_main_button,
            self.choose_template_button,
            self.builder_output_path,
            self.select_builder_output_button,
            self.builder_json_checkbox,
            self.builder_report_checkbox,
        ):
            control.setEnabled(controls_enabled)
        self.builder_json_path.setEnabled(
            controls_enabled and self.builder_json_checkbox.isChecked()
        )
        self.builder_report_path.setEnabled(
            controls_enabled and self.builder_report_checkbox.isChecked()
        )
        ready = self._current_builder_plan() is not None and not self._busy
        self.builder_generate_button.setEnabled(ready)
        if self._busy:
            self._set_badge(self.builder_state_badge, "BUILDING", BadgeState.EXPERIMENTAL)
            self.status_label.setText("BUILDING · Offline only · BLE usage: 0")
        elif ready:
            self._set_badge(self.builder_state_badge, "READY", BadgeState.VERIFIED)
            self.status_label.setText("BUILDER VERIFIED · READY TO BUILD")
        else:
            self._set_badge(self.builder_state_badge, "NOT READY", BadgeState.UNKNOWN)

    def _create_builder_confirmation(self, plan: GreenLionGuiBuildPlan) -> QMessageBox:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("确认生成完整表盘 BIN")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setText("确认使用已验证的 GreenLion exact profile 离线构建")
        dialog.setInformativeText(
            f"输入图片：{plan.image_path.name}\n"
            f"模板：{plan.template_path.name}\n"
            f"BIN 输出：{plan.output_path.name}\n"
            f"JSON 输出：{plan.json_path.name if plan.json_path else 'Disabled'}\n"
            f"Markdown 输出：{plan.report_path.name if plan.report_path else 'Disabled'}\n"
            f"Profile：{plan.profile}\n"
            "主资源：320×384\n"
            "缩略资源：210×252 · AUTO FROM MAIN IMAGE\n"
            "输出大小：351617 bytes\n"
            "offset 0 将保持模板值，不修改时间位置\n"
            "不执行上传，不覆盖已有文件"
        )
        generate = dialog.addButton("生成", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        dialog.generate_button = generate
        return dialog

    def show_builder_confirmation(self, plan: GreenLionGuiBuildPlan) -> QMessageBox:
        dialog = self._create_builder_confirmation(plan)
        self._set_badge(
            self.builder_state_badge,
            "CONFIRMATION",
            BadgeState.EXPERIMENTAL,
        )
        dialog.setModal(False)
        dialog.open()
        self.last_dialog = dialog
        return dialog

    def _confirm_builder(self, plan: GreenLionGuiBuildPlan) -> bool:
        dialog = self._create_builder_confirmation(plan)
        dialog.exec()
        self.last_dialog = dialog
        return dialog.clickedButton() is dialog.generate_button

    def _generate_builder_bin(self) -> None:
        if self._busy or not self.builder_generate_button.isEnabled():
            return
        plan = self._current_builder_plan()
        if plan is None:
            return
        if not self._confirm_builder(plan):
            self._update_builder_state()
            return

        self._busy = True
        self.builder_last_error = None
        self.builder_last_result = None
        self._update_edit_state()
        self._update_builder_state()
        result = None
        failure: tuple[str, str, str] | None = None
        try:
            result = self.controller.execute_greenlion_build(plan)
        except EditorError as error:
            mapped = self.controller.user_error(error)
            self.builder_last_error = mapped.message
            failure = (mapped.title, mapped.message, mapped.technical_details)
        except Exception as error:
            self.builder_last_error = "发生未预期错误，操作未完成。"
            failure = (
                "离线构建失败",
                self.builder_last_error,
                f"{type(error).__name__}: {error}",
            )
        finally:
            self._busy = False
            self._update_edit_state()
            self._update_builder_state()

        if failure is not None:
            self._set_badge(self.builder_state_badge, "ERROR", BadgeState.ERROR)
            self.status_label.setText("ERROR · No output created · BLE usage: 0")
            self._show_error(*failure)
            return

        self.builder_last_result = result
        self.builder_last_plan = plan
        self._set_badge(self.builder_state_badge, "COMPLETE", BadgeState.VERIFIED)
        self.status_label.setText("COMPLETE · 351617 bytes · BLE usage: 0")
        self._show_builder_success(result, plan)

    def _show_builder_success(self, result, plan: GreenLionGuiBuildPlan) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("Builder 构建成功")
        dialog.setMinimumWidth(680)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.addWidget(QLabel("完整表盘 BIN 构建成功", objectName="pageTitle"))

        golden_value = getattr(result.golden_status, "value", result.golden_status)
        if golden_value == "match":
            golden_text = "VERIFIED GOLDEN MATCH · DEVICE EVIDENCE LEVEL C"
            golden_state = BadgeState.VERIFIED
        else:
            golden_text = "CUSTOM VALID BUILD · GOLDEN NOT APPLICABLE"
            golden_state = BadgeState.EXPERIMENTAL
        layout.addWidget(StatusBadge(golden_text, golden_state))

        usage = result.external_usage
        usage_total = sum(
            (
                usage.hardware_initializations,
                usage.hardware_scans,
                usage.hardware_connections,
                usage.hardware_writes,
                usage.external_processes,
                usage.network_operations,
                usage.real_uploads,
            )
        )
        summary = QLabel(
            f"输出文件：{result.output_path.name}\n"
            f"输出大小：{result.output_size}\n"
            f"输出 SHA-256：{result.output_sha256}\n"
            f"Builder version：{result.builder_version}\n"
            "Pillow version：10.4.0\n"
            f"Template header preserved：{'是' if result.template_header_preserved else '否'}\n"
            f"Template offset 0：{result.template_offset_zero:02X}\n"
            f"Main：{result.main_resource_size[0]}×{result.main_resource_size[1]}\n"
            f"Thumbnail：{result.thumbnail_resource_size[0]}×{result.thumbnail_resource_size[1]}\n"
            f"Output revalidated：{'通过' if result.output_revalidated else '失败'}\n"
            f"Image unchanged：{'是' if result.image_unchanged else '否'}\n"
            f"Template unchanged：{'是' if result.template_unchanged else '否'}\n"
            f"Determinism：{getattr(result.determinism_status, 'value', result.determinism_status).upper()}\n"
            f"Repeated build SHA：{result.repeated_build_sha256 or 'None / Not evaluated'}\n"
            f"Golden status：{str(golden_value).upper()}\n"
            f"Exact golden match：{result.exact_golden_match}\n"
            f"External usage：{usage_total}",
            objectName="mono",
        )
        summary.setWordWrap(True)
        summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(summary)
        separation = QLabel(
            "此 Builder 输出保留模板 offset 0=02，尚未与已验证的 00/01 时间位置编辑流程合并。",
            objectName="muted",
        )
        separation.setWordWrap(True)
        layout.addWidget(separation)

        actions = QHBoxLayout()
        folder = QPushButton("打开输出目录")
        folder.setEnabled(result.output_path.exists())
        folder.clicked.connect(lambda: self._open_local_path(result.output_path.parent))
        actions.addWidget(folder)
        copy_sha = QPushButton("复制 SHA-256")
        copy_sha.clicked.connect(self._copy_builder_output_sha)
        actions.addWidget(copy_sha)
        open_json = QPushButton("打开 JSON")
        open_json.setEnabled(plan.json_path is not None and plan.json_path.exists())
        if plan.json_path is not None:
            open_json.clicked.connect(lambda: self._open_local_path(plan.json_path))
        actions.addWidget(open_json)
        open_report = QPushButton("打开 Markdown")
        open_report.setEnabled(plan.report_path is not None and plan.report_path.exists())
        if plan.report_path is not None:
            open_report.clicked.connect(lambda: self._open_local_path(plan.report_path))
        actions.addWidget(open_report)
        layout.addLayout(actions)

        close = QPushButton("关闭")
        close.clicked.connect(dialog.close)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.setModal(False)
        dialog.show()
        self.last_dialog = dialog
        return dialog

    def _copy_builder_output_sha(self) -> None:
        if self.builder_last_result is not None:
            QGuiApplication.clipboard().setText(self.builder_last_result.output_sha256)

    def load_file(self, path: str | Path, *, show_error: bool = True) -> bool:
        try:
            info = self.controller.load_file(path)
        except EditorError as error:
            mapped = self.controller.user_error(error)
            self.last_error = mapped.message
            self.status_label.setText("ERROR · No output created")
            self._set_badge(self.file_badge, "ERROR", BadgeState.ERROR)
            if show_error:
                self._show_error(mapped.title, mapped.message, mapped.technical_details)
            return False
        self.current_info = info
        self.last_error = None
        self.last_result = None
        self.last_plan = None
        self._render_file(info)
        return True

    def _render_file(self, info: StaticDiyInspection) -> None:
        self.current_file_label.setText(info.path.name)
        self.current_file_label.setToolTip(str(info.path))
        self._set_badge(self.file_badge, "VERIFIED", BadgeState.VERIFIED)
        self.size_value.setText(f"{info.size} bytes")
        self.first_byte_value.setText(f"{info.first_byte:02X}")
        self.position_value.setText(info.time_position.label)
        self.current_position.setText(info.time_position.label)
        self.sha_value.setPlainText(info.sha256)
        display_path = f"…\\{info.path.parent.name}\\{info.path.name}"
        self.path_value.setText(display_path)
        self.path_value.setToolTip(str(info.path))
        self.top_radio.setChecked(info.time_position is TimePosition.TOP)
        self.bottom_radio.setChecked(info.time_position is TimePosition.BOTTOM)
        self.preview.set_position(info.time_position)
        self.output_path.clear()
        self.json_checkbox.setChecked(True)
        self.markdown_checkbox.setChecked(True)
        self._update_edit_state()

    def _selected_target(self) -> TimePosition | None:
        if self.top_radio.isChecked():
            return TimePosition.TOP
        if self.bottom_radio.isChecked():
            return TimePosition.BOTTOM
        return None

    def _preview_plan(self) -> TimePositionEditPlan | None:
        if self.current_info is None:
            return None
        target = self._selected_target()
        if target is None or target is self.current_info.time_position:
            return None
        output_text = self.output_path.text().strip()
        output = (
            Path(output_text)
            if output_text
            else self.current_info.path.with_name(
                f"{self.current_info.path.stem}_{target.value}.bin"
            )
        )
        return self.controller.prepare_time_position_edit(
            self.current_info,
            output,
            target,
            include_json=self.json_checkbox.isChecked(),
            include_report=self.markdown_checkbox.isChecked(),
        )

    def _current_plan(self) -> TimePositionEditPlan | None:
        if not self.output_path.text().strip():
            return None
        return self._preview_plan()

    @staticmethod
    def _plan_paths_are_distinct(plan: TimePositionEditPlan) -> bool:
        paths = [
            str(path).casefold()
            for path in (plan.output_path, plan.json_path, plan.report_path)
            if path is not None
        ]
        return len(paths) == len(set(paths))

    def _update_edit_state(self, *_args) -> None:
        loaded = self.current_info is not None
        controls_enabled = loaded and not self._busy
        for control in (
            self.top_radio,
            self.bottom_radio,
            self.output_path,
            self.select_output_button,
            self.json_checkbox,
            self.markdown_checkbox,
        ):
            control.setEnabled(controls_enabled)

        plan = self._preview_plan() if loaded else None
        if not loaded:
            self.change_summary.setText(
                "尚未加载文件\nOffset: 0x00000000\nValue: —\n"
                "Changed: 0 bytes\nUnchanged: —"
            )
            self.changed_label.setText("Changed bytes: 0")
            self.generate_button.setEnabled(False)
            self.status_label.setText("No file loaded")
            return

        if plan is None:
            self.preview.set_position(self.current_info.time_position)
            self.change_summary.setText(
                "没有变化 · 当前值与目标值相同\n"
                "Offset: 0x00000000\n"
                f"Value: {self.current_info.first_byte:02X} → {self.current_info.first_byte:02X}\n"
                "Changed: 0 bytes\n"
                f"Unchanged: {self.current_info.size} bytes"
            )
            self.changed_label.setText("Changed bytes: 0")
            self.generate_button.setEnabled(False)
            self.status_label.setText(
                "VALIDATING · BLE usage: 0" if self._busy else "VERIFIED · No changes · READY"
            )
            return

        self.preview.set_position(plan.target_position)
        self.change_summary.setText(
            f"Offset: {plan.field_offset_hex}\n"
            f"Value: {plan.before_hex} → {plan.after_hex}\n"
            f"Changed: {plan.changed_byte_count} byte\n"
            f"Unchanged: {plan.unchanged_byte_count} bytes"
        )
        self.changed_label.setText(f"Changed bytes: {plan.changed_byte_count}")
        ready = (
            bool(self.output_path.text().strip())
            and self._plan_paths_are_distinct(plan)
            and not self._busy
        )
        self.generate_button.setEnabled(ready)
        if self._busy:
            self.status_label.setText("VALIDATING · BLE usage: 0")
        elif ready:
            self.status_label.setText("VERIFIED · READY TO EXPORT")
        else:
            self.status_label.setText("VERIFIED · Output path required")

    def _create_export_confirmation(self, plan: TimePositionEditPlan) -> QMessageBox:
        current = self.current_info.time_position.label if self.current_info else "—"
        dialog = QMessageBox(self)
        dialog.setWindowTitle("确认生成新 BIN")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setText("确认离线生成新的时间位置 BIN")
        dialog.setInformativeText(
            f"输入文件：{plan.input_path.name}\n"
            f"输出文件：{plan.output_path.name}\n"
            f"时间位置：{current} → {plan.target_position.label}\n"
            f"Offset：{plan.field_offset_hex}\n"
            f"Value：{plan.before_hex} → {plan.after_hex}\n"
            f"Changed bytes: {plan.changed_byte_count}\n"
            f"JSON：{'启用' if plan.json_path else '关闭'}\n"
            f"Markdown：{'启用' if plan.report_path else '关闭'}\n"
            "输入文件不会被修改\n"
            "不执行 BLE 上传"
        )
        generate = dialog.addButton("生成", QMessageBox.ButtonRole.AcceptRole)
        dialog.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        dialog.generate_button = generate
        return dialog

    def show_export_confirmation(self, plan: TimePositionEditPlan) -> QMessageBox:
        dialog = self._create_export_confirmation(plan)
        dialog.setModal(False)
        dialog.open()
        self.last_dialog = dialog
        return dialog

    def _confirm_export(self, plan: TimePositionEditPlan) -> bool:
        dialog = self._create_export_confirmation(plan)
        dialog.exec()
        self.last_dialog = dialog
        return dialog.clickedButton() is dialog.generate_button

    def _generate_new_bin(self) -> None:
        if self._busy or not self.generate_button.isEnabled():
            return
        plan = self._current_plan()
        if plan is None or not self._confirm_export(plan):
            return

        self._busy = True
        self.last_error = None
        self.last_result = None
        self._update_edit_state()
        failure: tuple[str, str, str] | None = None
        try:
            result = self.controller.execute_time_position_edit(plan)
        except EditorError as error:
            mapped = self.controller.user_error(error)
            self.last_error = mapped.message
            failure = (mapped.title, mapped.message, mapped.technical_details)
        except Exception as error:
            self.last_error = "发生未预期错误，操作未完成。"
            failure = (
                "离线编辑失败",
                self.last_error,
                f"{type(error).__name__}: {error}",
            )
        finally:
            self._busy = False
            self._update_edit_state()

        if failure is not None:
            self.status_label.setText("ERROR · No output created")
            self._show_error(*failure)
            return

        self.last_result = result
        self.last_plan = plan
        self.status_label.setText("COMPLETE · Changed bytes: 1")
        self._show_success(result, plan)

    def _show_success(self, result, plan: TimePositionEditPlan) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("生成成功")
        dialog.setMinimumWidth(620)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.addWidget(QLabel("生成成功", objectName="pageTitle"))
        golden_text, golden_state = self._golden_status(result.exact_golden_match)
        layout.addWidget(StatusBadge(golden_text, golden_state))
        summary = QLabel(
            f"输入位置：{result.detected_input_position.label}\n"
            f"输出位置：{result.output_position.label}\n"
            f"时间位置：{result.detected_input_position.label} → {result.output_position.label}\n"
            f"修改偏移：{result.field_offset_hex}\n"
            f"修改值：{result.before_hex} → {result.after_hex}\n"
            f"Changed bytes：{result.changed_byte_count}\n"
            f"Unchanged bytes：{result.unchanged_byte_count}\n"
            f"输出大小：{result.output_size}\n"
            f"输出文件：{result.output_path.name}\n"
            f"输出 SHA-256：{result.output_sha256}\n"
            f"输入文件未改变：{'是' if result.input_unchanged else '否'}\n"
            f"输出写后复核：{'通过' if result.output_revalidated else '失败'}\n"
            "BLE：0 · ADB：0 · Frida：0 · Uploader：0",
            objectName="mono",
        )
        summary.setWordWrap(True)
        summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(summary)

        actions = QHBoxLayout()
        folder = QPushButton("打开输出文件夹")
        folder.clicked.connect(lambda: self._open_local_path(result.output_path.parent))
        actions.addWidget(folder)
        copy_sha = QPushButton("复制 SHA-256")
        copy_sha.clicked.connect(self._copy_output_sha)
        actions.addWidget(copy_sha)
        open_json = QPushButton("打开 JSON")
        open_json.setEnabled(plan.json_path is not None)
        if plan.json_path is not None:
            open_json.clicked.connect(lambda: self._open_local_path(plan.json_path))
        actions.addWidget(open_json)
        open_report = QPushButton("打开 Markdown")
        open_report.setEnabled(plan.report_path is not None)
        if plan.report_path is not None:
            open_report.clicked.connect(lambda: self._open_local_path(plan.report_path))
        actions.addWidget(open_report)
        layout.addLayout(actions)

        close = QPushButton("关闭")
        close.clicked.connect(dialog.close)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.setModal(False)
        dialog.show()
        self.last_dialog = dialog
        return dialog

    @staticmethod
    def _golden_status(value: bool | str) -> tuple[str, BadgeState]:
        if value is True:
            return "VERIFIED GOLDEN MATCH", BadgeState.VERIFIED
        if value is False:
            return "GOLDEN MISMATCH", BadgeState.ERROR
        return "CUSTOM VALID BIN", BadgeState.EXPERIMENTAL

    def _copy_output_sha(self) -> None:
        if self.last_result is not None:
            QGuiApplication.clipboard().setText(self.last_result.output_sha256)

    @staticmethod
    def _open_local_path(path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _set_badge(self, badge: StatusBadge, text: str, state: BadgeState) -> None:
        badge.setText(text)
        badge.setProperty("state", state.value)
        badge.style().unpolish(badge)
        badge.style().polish(badge)

    def _copy_sha(self) -> None:
        if self.current_info:
            QGuiApplication.clipboard().setText(self.current_info.sha256)

    def _copy_path(self) -> None:
        if self.current_info:
            QGuiApplication.clipboard().setText(str(self.current_info.path))

    def _show_error(self, title: str, message: str, details: str) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setText(message)
        dialog.setDetailedText(details)
        dialog.setStandardButtons(QMessageBox.StandardButton.Close)
        dialog.setModal(False)
        self._localize_message_box(dialog)
        dialog.open()
        self.last_dialog = dialog

    def show_stage_gate_dialog(self, title: str = "Verified Builder 范围") -> QDialog:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText("OFFLINE BUILDER AVAILABLE")
        dialog.setInformativeText(
            "Builder v0.2.4-greenlion-exact 已通过 Controller 接入；"
            "只支持冻结 exact profile，时间位置编辑保持独立，GUI 上传不执行。"
        )
        dialog.setStandardButtons(QMessageBox.StandardButton.Close)
        dialog.setModal(False)
        self._localize_message_box(dialog)
        dialog.open()
        self.last_dialog = dialog
        return dialog

    @staticmethod
    def _localize_message_box(dialog: QMessageBox) -> None:
        close = dialog.button(QMessageBox.StandardButton.Close)
        if close is not None:
            close.setText("关闭")
        for button in dialog.findChildren(QPushButton):
            if "Details" in button.text():
                button.setText("查看技术详情")

    def show_about_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("关于 Ultra3 Lab")
        dialog.setMinimumWidth(520)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.addWidget(QLabel("Ultra3 Lab", objectName="pageTitle"))
        layout.addWidget(StatusBadge("OFFLINE VERIFIED BUILDER", BadgeState.VERIFIED))
        verified = QLabel(
            "已验证\n"
            "• GreenLion Static DIY\n"
            "• NJ-LEJ-2.1.7\n"
            "• 351617-byte container\n"
            "• Main resource：320 × 384（5:6）\n"
            "• Thumbnail resource：210 × 252（5:6）\n"
            "• Physical display geometry：UNKNOWN\n"
            "• offset 0x00000000：00 = top，01 = bottom\n"
            "• 时间位置编辑：AVAILABLE\n"
            "• Builder v0.2.4-greenlion-exact：AVAILABLE\n"
            "• Builder 输出：351617 bytes，模板 offset 0 保持 02"
        )
        unsupported = QLabel(
            "未接入 / 未验证\n"
            "• GUI 上传、独立缩略图和可调构建参数\n"
            "• Builder 输出与 00/01 时间位置编辑合并\n"
            "• 其他固件、预设表盘、时间颜色\n"
            "• 日期、星期、步数、卡路里、心率、组件拖拽"
        )
        unsupported.setObjectName("muted")
        layout.addWidget(verified)
        layout.addWidget(unsupported)
        close = QPushButton("关闭")
        close.clicked.connect(dialog.close)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.setModal(False)
        dialog.show()
        self.last_dialog = dialog
        return dialog
