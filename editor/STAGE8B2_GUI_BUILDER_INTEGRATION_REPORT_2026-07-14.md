# Stage 8B-2 — Verified GreenLion Static Builder GUI 集成报告

日期：2026-07-14  
状态：`COMPLETE — OFFLINE GUI ONLY`

## 1. Git 与冻结入口审计

- 分支：`main`
- 修改前工作区：干净
- HEAD / `origin/main`：`ec2a04a64003062685ccde601746843c245bf45d`
- `git fetch origin`：成功
- 冻结标签：`ultra3-editor-v0.3.4-stage8b1`，存在
- 最新提交包含 Stage 8B-1 公共 GreenLion Builder
- Uploader 修改：`0`
- 未执行 reset、clean、checkout、commit、tag 或 push

修改前基线：

- Editor：`266 passed in 4.92s`
- Uploader：`126 passed in 1.64s`

## 2. GUI 架构与调用链

唯一构建调用链：

```text
MainWindow
  -> OfflineGuiController.execute_greenlion_build()
  -> build_greenlion_static_diy()
```

`GreenLionGuiBuildPlan` 是 `frozen=True` 不可变模型，保存图片、模板、BIN、可选 JSON、
可选 Markdown 与固定 profile。Controller 的 `prepare_greenlion_build()` 只整理 GUI 参数并拒绝
明显重复路径；`execute_greenlion_build()` 每次用户确认后只调用一次公开 Builder。

GUI 与 Controller 没有导入 Builder 私有函数，没有图像编码、RGB565 位运算、GreenLion wire
算法、BIN 读取或 patch，也没有第二套 resize/crop 或模板哈希判断。

## 3. 输入、模板、缩略图与 exact profile

- 输入：PNG/JPEG，可显示文件名、格式、尺寸与 Qt 等比例源预览。
- 预览边界：明确显示“输入图片预览，仅用于选择确认，不代表最终 RGB565、裁剪或设备显示效果”。
- 模板：选择后显示 `SELECTED · VALIDATION PENDING`；大小、17 字节头和 SHA-256 仍由公共核心验证。
- 缩略图：无独立输入，固定显示 `AUTO FROM MAIN IMAGE · 210 × 252`。
- 缩略图说明：公共核心直接从原始输入独立生成，不从主资源二次缩放。
- profile：完全只读，固定 GreenLion Static DIY、NJ-LEJ-2.1.7、320×384、210×252、cover、
  bilinear、truncate RGB565、greenlion-next-high、Pillow 10.4.0、351617 bytes 和模板 offset 0 保留。

## 4. 输出、确认与按钮状态

- BIN 为必选新路径；JSON、Markdown 默认启用，可分别关闭或修改路径。
- 不提供覆盖或 force；最终独占创建与事务行为由公共 Builder 保证。
- 按钮状态：`NOT READY -> READY -> CONFIRMATION -> BUILDING -> COMPLETE/ERROR`。
- 就绪条件：图片、模板、BIN 输出齐全，当前不忙，输入与输出无明显重复。
- 确认摘要包含输入、模板、全部输出、exact profile、两种资源尺寸、351617 bytes、
  offset 0 保持模板值、不修改时间位置、不上传和不覆盖。
- 用户取消时公共核心调用为 `0`，不创建输出，状态恢复 `READY`。

## 5. 执行可靠性与错误映射

构建执行使用统一 `try / except / finally`：进入前 `_busy=True`，finally 中始终恢复
`_busy=False` 并刷新时间编辑与 Builder 控件。最终 `ERROR` / `COMPLETE` 在统一恢复后设置，
不会被通用状态刷新覆盖。没有捕获 `BaseException`，不会吞掉 `KeyboardInterrupt` 或
`SystemExit`。

已映射并测试：

- `UnsupportedPillowVersionError`：明确要求 Pillow 10.4.0。
- `UnsupportedTemplateError`：明确公共核心验证大小、17 字节头和 SHA-256。
- `BuildOutputExistsError`：拒绝覆盖。
- `BuildInputOutputSamePathError`：拒绝输入/输出路径重复。
- `BuildRollbackError`：醒目提示可能残留文件，并保留 `failed_cleanup_paths`、原异常类型与文本。
- 普通 `Exception`：显示“离线构建失败 / 发生未预期错误，操作未完成”，技术详情保留异常类型与文本。

意外异常测试确认：核心调用 `1` 次、`_busy=False`、结果为 `None`、按钮恢复可用、
状态保持 `ERROR · No output created · BLE usage: 0`，没有第二次调用。

## 6. 成功结果与 Golden 语义

成功页显示完整输出 SHA-256、351617、Builder/Pillow 版本、模板头保留、offset 0=`02`、
320×384、210×252、写后复核、输入/模板不变、determinism、重复 SHA、Golden 状态和
external usage。

| 场景 | 输出 SHA-256 | Golden | exact match | determinism | repeated SHA |
|---|---|---|---|---|---|
| 冻结照片 1 | `44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664` | `MATCH` | `true` | `NOT_EVALUATED` | `None` |
| 自定义离线图片 | `1D87836F3D985409F7787254B5ABFECAA81543D99082FAAC2FAC962B6ADBFC6C` | `NOT_APPLICABLE` | `null` | `NOT_EVALUATED` | `None` |

两份结果均为 351617 bytes、模板头保留、offset 0=`02`、写后复核通过、图片和模板不变、
external usage 全部为 `0`。MATCH 标记设备证据仍为 Level C；NOT_APPLICABLE 是普通成功，
未显示失败警告。

## 7. 与时间位置编辑强制隔离

- Builder 成功后不调用 `inspect_static_diy()` 或时间位置公共核心。
- 不自动加载生成 BIN，不替换 Stage 8A.2 当前输入，不显示 Top/Bottom。
- 成功页明确显示：Builder 输出保留模板 offset 0=`02`，尚未与只接受 `00/01` 的已验证
  时间位置编辑流程合并。
- Stage 8A.2 原有加载、Top/Bottom 编辑、黄金匹配和可靠性测试继续通过。

## 8. 新增与修改文件

修改：

- `src/ultra3_editor/gui/controllers.py`：不可变计划、单次公开 Builder 调用、结构化错误映射。
- `src/ultra3_editor/gui/main_window.py`：Builder 表单、源预览、状态机、确认、执行、结果与错误界面。
- `tests/gui/test_offline_gui.py`：将旧 Builder 硬锁断言更新为已验证集成边界。
- `tests/gui/test_time_position_integration.py`：验证 Builder 可用不影响时间位置导出。
- `README.md`：记录 Stage 8B-2 离线 Builder GUI 与 offset 0 隔离。

新增：

- `tests/gui/test_greenlion_builder_integration.py`：22 项 Builder GUI/Controller 测试。
- `scripts/capture_stage8b2_screenshots.py`：离屏截图与两类真实公共核心证据生成器。
- `artifacts/stage8b2_gui_builder/`：MATCH / NOT_APPLICABLE BIN、JSON、Markdown 与自定义输入。
- `artifacts/stage8b2_gui/screenshots/`：13 张 GUI 审计截图。
- 本报告。

未修改：

- `src/ultra3_editor/greenlion_builder.py`
- `src/ultra3_editor/time_position.py`
- `src/ultra3_editor/errors.py`
- `uploader/`
- 冻结样本、黄金 BIN、Frozen ZIP 与外部 baseline

## 9. 测试、静态边界与冻结哈希

最终回归：

- Editor：`288 passed in 6.26s`（原 266 项全部保留，新增 22 项）
- Uploader：`126 passed in 1.53s`
- `git diff -- uploader`：无输出
- `git diff -- editor/src/ultra3_editor/greenlion_builder.py`：无输出
- `git diff -- editor/src/ultra3_editor/time_position.py`：无输出
- `git diff -- editor/src/ultra3_editor/errors.py`：无输出

GUI/Controller 静态扫描未发现 Builder 私有函数、图像编码、payload/C9、Bleak、FF02、adb、
Frida、Uploader 或 subprocess 调用。

冻结复核：

- 冻结照片 1：`9FDBB04E9DD910296B44BECB98C25A0C988A4B1B98EC0DAE12A0E831BC747CB4`
- 冻结模板：`5D04DE76C94DA9D7F7069AF3E6038E1575D3B42E5E009EAD590CE4DD33F5E1CC`
- Frozen ZIP：`3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231`

## 10. 截图与视觉审查

截图清单：

1. `builder_initial.png`
2. `image_selected.png`
3. `source_preview_notice.png`
4. `template_selected_pending.png`
5. `exact_profile.png`
6. `ready_to_build.png`
7. `confirmation.png`
8. `golden_match_success.png`
9. `custom_not_applicable_success.png`
10. `template_error.png`
11. `rollback_error.png`
12. `unexpected_error_recovered.png`
13. `time_position_separation_notice.png`

使用 image-analysis 技能逐张审查，13/13 通过：中文清晰，无方框、重叠、裁切或私人绝对路径；
状态流转合理；MATCH/NOT_APPLICABLE、351617、offset 0=02、NOT_EVALUATED、External usage 0
和时间位置隔离提示均完整可见。截图仅用于 GUI 审计，不是真机显示证据。

## 11. 外部调用与未支持范围

- Bleak 初始化 / scan / connect / FF02 write：`0 / 0 / 0 / 0`
- adb / Frida / Uploader 调用：`0 / 0 / 0`
- 网络请求 / 真实上传：`0 / 0`
- 未执行真机命令，未连接手表或手机。

尚未支持：独立缩略图、可调 fit/resample/quantize/wire profile、其他模板或固件、Builder
输出与 `00/01` 时间位置编辑合并、payload/C9、GUI 上传和真实设备验证。
