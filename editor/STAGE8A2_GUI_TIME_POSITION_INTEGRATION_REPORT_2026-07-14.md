# Stage 8A.2 GUI 时间位置公共核心接入报告

## 1. 阶段结论

Stage 8A.2 已完成。现有 PyQt6 GUI 已从全局只读模式升级为离线时间位置编辑器，并且只通过
`OfflineGuiController` 调用已冻结的 Stage 7B-1 `set_time_position()` 公共核心。

GUI 没有读取、哈希或 patch BIN 字节，没有复制大小验证、差分、黄金匹配、独占写入或写后
复核算法。资源 Builder、主图/缩略图导入、RGB565、Uploader、BLE、adb、Frida 和上传仍未接入。

## 2. Git、标签与冻结审计

修改前执行 `git fetch origin` 后的结果：

| 项目 | 结果 |
|---|---|
| 分支 | `main` |
| 工作区 | 干净 |
| HEAD | `26f5499ad7d57b1e431af38d9f5378369de0e9dd` |
| origin/main | `26f5499ad7d57b1e431af38d9f5378369de0e9dd` |
| Stage 7B-1 标签 | `ultra3-editor-v0.3.1-stage7b1` |
| 标签目标 | `26f5499ad7d57b1e431af38d9f5378369de0e9dd` |
| 最新提交 | `feat(editor): add verified time position editing core` |
| Uploader 未提交修改 | `0` |

标签提交包含 `set_time_position()`、`set-time-position` CLI、双向黄金 BIN/JSON/Markdown 和
`STAGE7B1_TIME_POSITION_EDITOR_REPORT_2026-07-13.md`。

## 3. 修改前测试与架构

| 测试集 | 结果 | 计时 |
|---|---:|---:|
| Editor | `174 passed` | `2.771s` |
| Uploader | `126 passed` | `2.006s` |

修改前 GUI 调用链只有：

```text
MainWindow.load_file()
  → OfflineGuiController.load_file()
    → inspect_static_diy()
```

Top/Bottom、输出路径、JSON/Markdown 和 Primary 全部硬禁用；侧栏与状态栏显示 `READ ONLY`。
GUI 不直接读取或写入 BIN；Builder 公共接口不存在；GUI 未导入 Uploader。

## 4. 新增与修改文件

新增：

| 文件 | 职责 |
|---|---|
| `tests/gui/test_time_position_integration.py` | Controller、窗口状态、确认、错误、成功、黄金、隔离和 Builder 回归 |
| `scripts/generate_stage8a2_gui_artifacts.py` | 只通过 GUI Controller 独占生成双向黄金验证产物 |
| `scripts/capture_stage8a2_screenshots.py` | 每张独立 Qt 进程生成 12 个真实离线状态截图 |
| `artifacts/stage8a2_gui_edit/` | 双向 GUI Controller BIN、JSON 和 Markdown |
| `artifacts/stage8a2_gui/screenshots/` | Stage 8A.2 视觉验收截图 |
| `STAGE8A2_GUI_TIME_POSITION_INTEGRATION_REPORT_2026-07-14.md` | 本报告 |

修改：

| 文件 | 修改 |
|---|---|
| `src/ultra3_editor/gui/controllers.py` | 增加编辑计划、公共核心执行入口和中文错误映射 |
| `src/ultra3_editor/gui/main_window.py` | 编辑状态、输出选择、确认/成功/错误对话框及结果操作 |
| `tests/gui/test_offline_gui.py` | 将 Stage 8A 全局只读门升级为“时间位置可编辑、Builder 仍锁定” |
| `tests/test_time_position_editor.py` | 约束只有 GUI Controller 可导入/调用编辑核心 |
| `README.md` | 记录 Stage 8A.2 接入与资源 Builder 安全边界 |

Stage 7B-1 核心、`static_diy.py`、Uploader 源码和状态机均未修改。

## 5. GUI 调用链与算法隔离

当前唯一编辑调用链：

```text
MainWindow
  → OfflineGuiController.prepare_time_position_edit()
    → TimePositionEditPlan
  → OfflineGuiController.execute_time_position_edit()
    → set_time_position()
      → Stage 7B-1 输入验证、单字节编辑、独占输出、写后复核和报告
```

`MainWindow` 只管理控件、用户选择、对话框、Controller 调用和结果展示。GUI 源码检查确认不含：

```text
data[0]
read_bytes
write_bytes
Path.open
hashlib
ultra3_uploader
BleakClient / BleakScanner
write_without_response
rgb565 / wire buffer
```

同步执行足以处理 351617 字节文件。执行期间 `_busy` 禁用重复操作并显示 `VALIDATING`；没有
为短任务引入 QThread、worker 或第二套编辑服务。

## 6. 文件加载与编辑状态

加载仍由 `inspect_static_diy()` 完成，显示文件名、脱敏路径、大小、完整 SHA-256、首字节、
当前位置、container/firmware 范围和资源规格。加载不创建任何输出。

加载 Top 默认选择上方，加载 Bottom 默认选择下方。当前值等于目标值时：

- 显示“没有变化”；
- Changed bytes = `0`；
- “生成新 BIN”禁用；
- 不调用 Controller 编辑入口。

选择相反位置时，摘要来自 `TimePositionEditPlan`：

| 方向 | Offset | Value | Changed | Unchanged |
|---|---|---|---:|---:|
| Top → Bottom | `0x00000000` | `00 → 01` | 1 | 351616 |
| Bottom → Top | `0x00000000` | `01 → 00` | 1 | 351616 |

预览继续标记 `SCHEMATIC TIME POSITION`，没有显示或推导真实 X/Y 坐标。

## 7. 按钮启用条件与状态栏

“生成新 BIN”只有在以下条件同时成立时启用：

- 已加载有效输入；
- 目标位置与当前位置不同；
- 输出路径非空；
- 派生的 BIN/JSON/Markdown 路径互不重复；
- 当前没有执行中的任务。

状态栏：

```text
No file loaded | BLE usage: 0
VERIFIED · No changes · READY
VERIFIED · READY TO EXPORT
VALIDATING · BLE usage: 0
COMPLETE · Changed bytes: 1
ERROR · No output created
```

全局 `READ ONLY` 已移除，改为 `OFFLINE EDIT`。禁用 Primary 仍使用非蓝色 disabled 样式。

## 8. 输出路径与 JSON/Markdown

“选择输出 BIN”使用 `QFileDialog.getSaveFileName()`。默认建议名为：

```text
<input_stem>_bottom.bin
<input_stem>_top.bin
```

JSON 和 Markdown 默认勾选，并从输出路径派生 `.json`、`.md`。关闭选项时 Controller 向核心
传入 `None`。GUI 不生成报告内容，也不提供覆盖确认或 `--force`；已有输出和输入输出同路径
最终均由公共核心拒绝。

## 9. 确认对话框

标题为“确认生成新 BIN”，按钮严格为“生成”和“取消”。内容包括输入/输出文件名、当前位置、
目标位置、offset、before/after、Changed bytes、JSON/Markdown 状态、输入不会被修改和不执行
BLE 上传。取消路径测试确认 Controller 调用为 0，且不创建任何输出。

## 10. 中文错误映射

| 核心异常 | GUI 标题/策略 |
|---|---|
| `NoChangeRequestedError` | 没有变化；未创建输出 |
| `InputOutputSamePathError` | 输出路径无效；不能与输入相同 |
| `EditOutputExistsError` | 输出文件已经存在；不提供覆盖 |
| `UnsupportedStaticDiySizeError` | 仅支持 351617 字节格式 |
| `InvalidExistingTimePositionError` | offset 0 必须为 00 或 01 |
| `UnexpectedChangedBytesError` | 检测到预期外变化；不保留输出 |
| `EditVerificationError` | 未完成文件已清理；输入不变 |
| `FileReadError` | 检查文件存在与读取权限 |

错误主信息不显示 traceback，技术详情保留在折叠区域。失败后 `_busy` 清除，控件状态恢复。

## 11. 成功结果展示

成功对话框展示输入/输出位置、offset、before/after、Changed/Unchanged、输出大小、文件名、完整
SHA-256、输入 unchanged、输出 revalidated 和外部调用 0。提供：

- 打开输出文件夹；
- 复制 SHA-256；
- 打开 JSON；
- 打开 Markdown；
- 关闭。

未生成的报告按钮禁用。GUI 不自动打开文件夹/报告，不自动加载输出，也不替换当前输入。

黄金匹配完全使用核心返回值：

| 核心值 | GUI |
|---|---|
| `true` | `VERIFIED GOLDEN MATCH` |
| `false` | `GOLDEN MISMATCH` 错误状态 |
| `not_applicable` | `CUSTOM VALID BIN` |

普通合法非黄金 BIN 已通过 GUI Controller 测试，不会因 `not_applicable` 被拒绝。

## 12. 双向 GUI Controller 黄金验证

产物目录：`editor/artifacts/stage8a2_gui_edit/`

| 方向 | 输出 | 大小 | SHA-256 | 官方样本 exact |
|---|---|---:|---|---|
| Top → Bottom | `gui_top_to_bottom.bin` | 351617 | `3B8302F6746AB2B78FA48599328DB7907788FA322D18ADF297280C8A5D3370C0` | `true` |
| Bottom → Top | `gui_bottom_to_top.bin` | 351617 | `9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635` | `true` |

两个方向均满足：changed bytes `1`、changed offsets `[0]`、unchanged bytes `351616`、输入
unchanged、输出 revalidated、`exact_golden_match = true`。黄金输入复核仍为原 SHA。

## 13. Builder、资源规格与未支持组件

时间位置编辑标记为 `VERIFIED / EDITABLE`。资源区继续显示 `Builder: NOT AVAILABLE`，并且：

- 选择主图：禁用；
- 选择缩略图：禁用；
- 从主图生成缩略图：禁用；
- 图片适配模式：禁用；
- 生成完整表盘 BIN：禁用。

主图 `320 × 384`、缩略图 `210 × 252`、比例 `5:6` 测试继续通过。它们只表示资源尺寸；
`Physical display geometry = UNKNOWN`、`Visible display area = UNKNOWN`。GUI 中不存在 `320×505`。

时间颜色继续 `UNKNOWN`；日期、星期、步数、卡路里、心率继续 `UNSUPPORTED`。

## 14. 测试结果

最终命令：

```powershell
$env:PYTHONPATH = (Resolve-Path ".\src").Path
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q -p no:cacheprovider
```

| 测试集 | 结果 | 计时 |
|---|---:|---:|
| Editor 全量 | `206 passed` | `3.643s` |
| 原 Stage 8A.2 前基线 | `174/174` 保留，无删除/skip/xfail | — |
| 新增 GUI 集成测试 | `32 passed` | 包含在全量中 |
| Uploader 全量 | `126 passed` | `2.012s` |

与 Stage 8A.2 冲突的旧“全局只读”断言被原位升级为“时间位置编辑可用、Builder 仍锁定”，测试
槽位没有删除；所有不冲突的既有测试继续原样通过。

## 15. Uploader 与外部调用保护

```text
git diff -- uploader: EMPTY
Uploader tracked manifest SHA-256:
59A22F8D3D1707AABFBEF1A900A1AFB34AC16063A5D3D5C24C13E79AB3093265

Bleak initialization: 0
BLE scan: 0
BLE connect: 0
FF02 writes: 0
adb: 0
Frida: 0
Uploader calls: 0
真实上传: 0
```

## 16. Frozen 复核

```text
Ultra3_v0.2.4_Frozen_Baseline_2026-07-11.zip
size: 218518
SHA-256: 3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231
```

Frozen changes = `0`。

## 17. 截图与视觉复审

目录：`editor/artifacts/stage8a2_gui/screenshots/`

1. `top_loaded_ready.png`
2. `bottom_selected_ready.png`
3. `output_path_selected.png`
4. `export_confirmation_active.png`
5. `export_success_golden.png`
6. `export_success_custom.png`
7. `output_exists_error.png`
8. `same_path_error.png`
9. `no_change_disabled.png`
10. `builder_still_unavailable.png`
11. `unsupported_features.png`
12. `about_stage8a2.png`

截图全部非空，黄金成功和自定义成功截图均来自真实公共核心执行结果。`image-analysis` 通过
fallback 最终由 `sf-35b-2` 完成 12 图逐张复审，结论全部为“无问题”：中文无方框/乱码，
无重叠或裁切，无用户名、邮箱、MAC 或完整私人绝对路径；没有错误的全局 `READ ONLY`；
Builder/UNKNOWN/UNSUPPORTED 状态明确；BLE usage 为 0；确认、成功和错误信息完整。

## 18. 当前适用范围与停止边界

```text
App: GreenLion
Container: greenlion-static
Firmware: NJ-LEJ-2.1.7
Input: 351617-byte reconstructed Static DIY BIN
Time position: offset 0x00000000, 00=top, 01=bottom
Mode: Offline GUI editing through Stage 7B-1 public core
```

尚未支持 Builder、图片导入/裁剪/适配、RGB565、缩略图生成、时间颜色、日期/健康组件、自由
坐标、预设表盘、BLE 或 GUI 上传。本阶段未执行真实上传，未进入 Stage 8B，未提交、未打标签、
未推送；等待人工验收。

## 19. 冻结前可靠性修正

冻结前审查发现：Controller 若抛出非 `EditorError` 的普通意外异常，旧执行路径可能跳过
`self._busy = False`，使窗口永久停留在 `VALIDATING` 且控件禁用。

修正仅涉及 `MainWindow._generate_new_bin()` 的执行收尾：

- `self._busy = True` 后，统一在 `finally` 中恢复为 `False` 并调用 `_update_edit_state()`；
- `EditorError` 继续使用既有中文明确映射；
- 普通 `Exception` 映射为标题“离线编辑失败”、主信息“发生未预期错误，操作未完成。”；
- 技术详情只记录异常类型和文本，例如 `RuntimeError: 模拟意外异常`；
- 不捕获 `BaseException`，因此 `KeyboardInterrupt` 和 `SystemExit` 不会被吞掉，但仍会经过
  `finally` 恢复 GUI 状态；
- 统一恢复控件后才设置最终 `ERROR` 或 `COMPLETE`，避免收尾状态覆盖最终状态栏；
- 仍由 Stage 7B-1 核心负责事务回滚，GUI 不声称或尝试删除调用前已经存在的文件。

新增 `test_unexpected_exception_restores_gui_state`，注入单次
`RuntimeError("模拟意外异常")` 并确认：`_busy = False`、`last_result = None`、生成按钮重新可用、
状态为 `ERROR · No output created`、没有输出 BIN、通用主信息和折叠技术详情正确、核心调用次数
严格为 1。既有 `EditorError` 和成功路径测试继续通过。

修正后的最终回归为 Editor `206 passed`、Uploader `126 passed`。两份 Stage 8A.2 黄金 BIN
SHA-256 仍分别为：

```text
gui_top_to_bottom.bin
3B8302F6746AB2B78FA48599328DB7907788FA322D18ADF297280C8A5D3370C0

gui_bottom_to_top.bin
9305529D6C644C757F6B193671B84153F0ADEBE385E7B3B30552E9BC23513635
```

`git diff -- uploader` 仍为空；Frozen ZIP SHA-256 仍为
`3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231`；
BLE、ADB、Frida 和 Uploader calls 均为 0。
