# Ultra3 Stage 8A Offline GUI MVP 报告

## 阶段结论

已完成 `Ultra3 Lab — Fluent Engineering Dark` 的纯离线、只读 GUI MVP。

Stage 8A 需求规定：只有 Stage 7B-1 `set_time_position()` 完成后才能接入编辑。当前 `src/ultra3_editor` 中不存在该公共函数或 `set-time-position` 命令，因此本阶段严格执行只读降级：允许打开、验证和示意预览 GreenLion Static DIY BIN；目标位置、输出路径、JSON/Markdown 选项与“生成新 BIN”全部硬禁用。

未实现、未复制、未猜测任何 BIN patch 逻辑。`top→bottom`、`bottom→top` 和写后复核在 GUI 中均标记为 `NOT EXECUTED`，不伪造成功结果。

## GUI 技术栈

- Python `3.10+`
- PyQt6 `6.11.0` / Qt `6.11.0`
- Qt `offscreen` 平台执行自动化测试与截图
- Windows 系统字体 `Microsoft YaHei UI`，仅运行时加载系统现有字体，不打包或分发字体文件

环境已存在 PyQt6，未下载 PySide6，也未修改系统 Python。`pyproject.toml` 通过 `gui` optional dependency 声明 PyQt6。

启动命令：

```powershell
python -m ultra3_editor gui
```

实际命令入口已在 `offscreen` 模式启动并保持运行 2 秒后由 smoke test 主动结束：`GUI_COMMAND_STARTED=True`。

## 新增文件

| 文件 | 职责 |
|---|---|
| `src/ultra3_editor/static_diy.py` | 只读验证 351617 字节、offset 0 值、时间位置和 SHA-256。 |
| `src/ultra3_editor/gui/app.py` | 延迟创建 QApplication、应用主题并启动主窗口。 |
| `src/ultra3_editor/gui/main_window.py` | 三栏主窗口、文件信息、只读时间面板、状态栏、导航和错误/范围对话框。 |
| `src/ultra3_editor/gui/controllers.py` | GUI 与公共核心之间的只读调用层及用户错误映射。 |
| `src/ultra3_editor/resource_geometry.py` | 定义独立的主图 320×384 与缩略图 210×252 资源画布规格。 |
| `src/ultra3_editor/gui/widgets.py` | 可复用 `StatusBadge` 与 5:6 `ResourcePreview`。 |
| `src/ultra3_editor/gui/theme.py` | 语义设计 Token、QPalette、集中 QSS 和系统中文字体回退。 |
| `src/ultra3_editor/gui/__init__.py`、`__main__.py` | GUI 包入口。 |
| `tests/test_static_diy_inspector.py` | 只读核心验证测试。 |
| `tests/gui/` | Qt 离屏启动、安全、加载、状态、错误、导航和布局测试。 |
| `scripts/capture_stage8a_screenshots.py` | 独占生成脱敏 GUI 截图。 |

## 修改文件

| 文件 | 修改 |
|---|---|
| `src/ultra3_editor/errors.py` | 增加静态 DIY 大小和时间位置明确异常。 |
| `src/ultra3_editor/cli.py` | 增加 `gui` 子命令，Qt 仅在选择该命令后延迟导入。 |
| `pyproject.toml` | 增加 `gui = ["PyQt6>=6.5"]` optional dependency。 |
| `README.md` | 记录只读 GUI 启动方式与 Stage 7B-1 安全门。 |

Uploader 源码和协议状态机没有修改。

## 设计 Token

`theme.py` 集中定义：

- `background_primary`、`background_sidebar`、`background_panel`、`background_elevated`
- `border_default`、`divider`
- `text_primary`、`text_secondary`、`text_disabled`
- `accent`、`accent_hover`、`accent_pressed`
- `state_verified`、`state_experimental`、`state_unknown`
- `state_unsupported`、`state_error`

业务代码不使用颜色判断状态。按钮、Card、导航、输入、Radio、Badge、focus 和 disabled 状态由集中主题统一管理。

## 页面结构

- 标题栏：`Ultra3 Lab`、当前文件名、`Verified scope: GreenLion Static DIY / NJ-LEJ-2.1.7`。
- 左侧导航：概览、表盘编辑、抓包重组、文件对比、验证报告、设置。
- 中央预览：主图 320×384 与缩略图 210×252 两个独立标签页，均保持 5:6，明确显示 `RESOURCE PREVIEW · NOT PHYSICAL DISPLAY GEOMETRY`。
- 右侧属性：文件信息、时间组件、导出安全门、功能证据等级。
- 底部状态栏：验证状态、Changed bytes、`BLE usage: 0`、`READ ONLY`。
- 未接入页面显示“当前版本仅支持命令行”，没有假功能按钮。

## 资源画布修订

| 项目 | 状态 |
|---|---|
| Main resource canvas | `320 × 384 — VERIFIED` |
| Thumbnail resource canvas | `210 × 252 — VERIFIED` |
| Resource aspect ratio | `5:6` |
| Physical display geometry | `UNKNOWN` |
| Physical visible area | `UNKNOWN` |
| Preset watchface geometry | `UNVERIFIED` |

- 主图和缩略图使用两个独立 `ResourceCanvasSpec`，不会互相作为数据别名。
- 标签页切换只改变当前预览规格；缩放只改变绘制倍率，不改变资源像素尺寸或输入 BIN。
- 时间位置仅在主图资源画布中显示 `SCHEMATIC TIME POSITION · TOP/BOTTOM`，不推导真实 Y 坐标。
- 画布使用普通 5:6 矩形，不使用手表外壳，也不暗示资源尺寸等于物理屏幕。
- 文件信息固定显示 `Physical display geometry: UNKNOWN` 与 `Visible display area: UNKNOWN`。
- 旧静态 DIY 制作尺寸已经从 GUI 源码、测试、README 和本报告移除。

当前项目根目录没有 `Builder v0.2.4-greenlion-exact` 公共接口或资源准备服务。因此“选择主图”“选择缩略图”“从主图生成缩略图”、适配模式和“生成表盘 BIN”均可见但硬禁用；GUI 没有实现图片转换、裁剪、静默拉伸、RGB565、wire buffer、缩略图覆盖或 BIN 拼装。待真实 Builder 进入当前源码后，只允许通过其公共接口启用这些控件。

## 核心调用链

```text
MainWindow.load_file()
  → OfflineGuiController.load_file()
    → inspect_static_diy()
      → 普通文件检查
      → size == 351617
      → offset 0 为 00 或 01
      → SHA-256
```

- GUI 不直接读取或写入 BIN 字节。
- GUI 中不存在 `data[0] = value`。
- 当前没有可复用的 `set_time_position()`，因此 GUI 未调用也未自行实现替代逻辑。
- 输出事务：当前不存在输出入口；所有相关控件禁用，所以成功和失败路径均不会产生半成品。

## 文件打开验证

- 只接受普通文件。
- 大小必须严格为 `351617`。
- offset `0x00000000` 必须是 `00` 或 `01`。
- `00 = top`，`01 = bottom`。
- SHA-256 完整显示并可复制。
- 可复制完整路径；界面默认使用中间省略，截图不暴露绝对用户目录。
- 加载和检测不修改输入文件、不创建输出、不自动弹出保存窗口。

## 错误映射

| 核心异常 | 用户提示 |
|---|---|
| `UnsupportedStaticDiySizeError` | 不支持的文件大小；当前仅检查 351617 字节文件。 |
| `InvalidExistingTimePositionError` | offset 0 的值不是 00 或 01。 |
| `FileReadError` | 请选择存在且可读取的普通 BIN 文件。 |

主提示不显示 traceback；技术详情保留在折叠区域。

## 测试结果

```text
Editor:   134 passed in 1.79s
Uploader: 126 passed in 1.48s
```

- 原 Editor 96 项全部保留。
- 新增 38 条离线/离屏执行路径。
- Uploader 126 项全部通过。
- GUI 测试不依赖真实显示器、手表、手机、网络或 BLE。

新增覆盖：GUI 初始化、空状态、延迟 CLI 入口、top/bottom 黄金加载、大小/SHA/位置、空文件、错误大小、未知首字节、不存在文件、输入不变、编辑硬锁、UNKNOWN/UNSUPPORTED 禁用、BLE usage、导航占位、关于范围、公共核心调用、错误映射、唯一 Primary、最小窗口布局、完整哈希复制、集中 Token、focus 状态和 `NOT EXECUTED` 安全门。

## 黄金样本只读验证

| 样本 | 检测 | 大小 | SHA-256 |
|---|---|---:|---|
| A0_repeat_1 Top | `00 / 上方` | 351617 | `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635` |
| P1_time_bottom Bottom | `01 / 下方` | 351617 | `3B8302F6746AB2B78FA48599328DB7907788FA322D18ADF297280C8A5D3370C0` |

- top→bottom GUI 黄金输出：`NOT EXECUTED — Stage 7B-1 missing`。
- bottom→top GUI 黄金输出：`NOT EXECUTED — Stage 7B-1 missing`。
- Changed bytes：`0`，因为 GUI 本阶段没有执行编辑。
- 两个输入样本执行前后 SHA-256 保持不变。

## 截图与视觉验收

目录：`artifacts/stage8a_gui/screenshots/`

- `empty_state.png`
- `top_loaded.png`
- `bottom_selected.png`
- `thumbnail_resource.png`
- `export_confirmation.png`
- `export_success.png`
- `invalid_file_error.png`
- `unsupported_features.png`
- `about_scope.png`

由于编辑安全门未满足，`export_confirmation.png` 与 `export_success.png` 均明确显示 `NOT EXECUTED`，没有伪造导出成功。

初次审查发现 Qt offscreen 缺少中文字体，截图出现方框，随后改为运行时加载 Windows 系统 `Microsoft YaHei UI`。最终直接视觉复审又发现并修复了连续截图的增量重绘、第二个对话框空白、禁用 Primary 仍呈蓝色以及 Qt 按钮英文问题。

每张截图改为独立 Qt 进程生成，避免 offscreen backing store 的增量重绘污染。九张最终截图直接复审通过：中文清晰、主图/缩略图 5:6 资源画布完整、非物理显示几何标识明确、READ ONLY/UNKNOWN/UNSUPPORTED 清楚、禁用控件不会被误认为可操作、两个导出截图均明确为 `NOT EXECUTED`，且无用户名、邮箱、MAC 或完整绝对用户路径。最终复审未调用 `image-analysis` skill。

## 外部能力使用统计

```text
Bleak 初始化：0
BLE scan：0
BLE connect：0
FF02 writes：0
adb 调用：0
Frida 调用：0
Uploader 调用：0
真实上传：0
```

GUI 包源码不存在 Bleak、Uploader、subprocess、adb、Frida 或 `write_without_response` 调用。

## Frozen 保护

`Ultra3_v0.2.4_Frozen_Baseline_2026-07-11.zip` 复核 SHA-256：

```text
3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231
```

与既有基线一致，Frozen changes = 0。

## 未支持功能

- BIN 修改、输出、JSON/Markdown 编辑记录、写后复核和黄金输出匹配
- 时间颜色
- 日期、星期、步数、卡路里、心率
- 组件拖拽或自由坐标
- 背景解析、背景重建或 RGB565 编码
- 预设表盘编辑
- BLE、Uploader、GUI 上传或 Stage 8B 功能

## 当前已验证适用范围

```text
GreenLion Static DIY
NJ-LEJ-2.1.7
351617-byte container
Time position detection at offset 0x00000000
00 = top
01 = bottom
Offline read-only GUI
```

要启用编辑验收，下一步必须先独立完成并验收 Stage 7B-1 公共 `set_time_position()` 核心；届时 GUI 只能调用该核心，不得在事件回调中实现 patch。
