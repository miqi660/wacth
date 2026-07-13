from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
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
from .controllers import OfflineGuiController, TimePositionEditPlan
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
        self._busy = False
        self.setWindowTitle("Ultra3 Lab — Offline Time-position Editor")
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
            "时间位置编辑可用\nBuilder / 资源制作仍安全锁定",
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
        scroll.setFixedWidth(332)
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
        card, layout = self._new_card("资源准备")
        self.main_resource_status = self._field(layout, "Main resource", "NOT LOADED")
        choose_main = QPushButton("选择主图")
        choose_main.setEnabled(False)
        layout.addWidget(choose_main)
        self.thumbnail_resource_status = self._field(
            layout,
            "Thumbnail resource",
            "NOT LOADED",
        )
        choose_thumbnail = QPushButton("选择缩略图")
        choose_thumbnail.setEnabled(False)
        layout.addWidget(choose_thumbnail)
        generate_thumbnail = QPushButton("从主图生成缩略图")
        generate_thumbnail.setEnabled(False)
        layout.addWidget(generate_thumbnail)
        layout.addWidget(QLabel("图片适配模式", objectName="fieldLabel"))
        self.fit_mode = QComboBox()
        self.fit_mode.addItems(("裁剪填充（cover）", "完整适应（contain）", "居中裁剪"))
        self.fit_mode.setEnabled(False)
        layout.addWidget(self.fit_mode)
        self.builder_generate_button = QPushButton("生成完整表盘 BIN")
        self.builder_generate_button.setEnabled(False)
        layout.addWidget(self.builder_generate_button)
        gate = QLabel(
            "当前源码没有 Builder v0.2.4-greenlion-exact 公共接口，"
            "资源导入、适配与缩略图生成均未执行。",
            objectName="muted",
        )
        gate.setWordWrap(True)
        layout.addWidget(gate)
        self.resource_controls = (
            choose_main,
            choose_thumbnail,
            generate_thumbnail,
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
            ("Builder", "NOT AVAILABLE", BadgeState.UNSUPPORTED),
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
            self.placeholder_message.setText("当前页面尚未接入；时间位置编辑请使用 BIN 编辑。")
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

    def show_stage_gate_dialog(self, title: str = "资源 Builder 已锁定") -> QDialog:
        dialog = QMessageBox(self)
        dialog.setWindowTitle(title)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setText("NOT EXECUTED")
        dialog.setInformativeText(
            "Builder v0.2.4-greenlion-exact 公共接口尚未进入当前源码；"
            "时间位置编辑可用，但资源导入、缩略图和完整表盘构建仍不执行。"
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
        layout.addWidget(StatusBadge("OFFLINE TIME-POSITION EDITOR", BadgeState.VERIFIED))
        verified = QLabel(
            "已验证\n"
            "• GreenLion Static DIY\n"
            "• NJ-LEJ-2.1.7\n"
            "• 351617-byte container\n"
            "• Main resource：320 × 384（5:6）\n"
            "• Thumbnail resource：210 × 252（5:6）\n"
            "• Physical display geometry：UNKNOWN\n"
            "• offset 0x00000000：00 = top，01 = bottom\n"
            "• 时间位置编辑：AVAILABLE"
        )
        unsupported = QLabel(
            "未接入 / 未验证\n"
            "• Builder、资源导入与 GUI 上传\n"
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
