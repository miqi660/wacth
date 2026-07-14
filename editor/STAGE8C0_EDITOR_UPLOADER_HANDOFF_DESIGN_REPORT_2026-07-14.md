# Stage 8C-0 — Editor-to-Uploader Handoff Contract Audit and Design

日期：2026-07-14  
范围：离线审计与契约设计  
结果：**COMPLETE**  
真实上传：**未执行**

## 1. Git 审计与冻结基线

- 仓库：`$REPO`
- 分支：`main`
- 开始前工作区：干净
- `HEAD`：`98ab2e327736127f67db48320f8d1c6cba3c0b1c`
- `origin/main`：`98ab2e327736127f67db48320f8d1c6cba3c0b1c`
- `HEAD = origin/main`：是
- 冻结标签：`ultra3-editor-v0.3.5-stage8b2`，存在
- 最新提交：`98ab2e3 feat(gui): integrate verified GreenLion static Builder`
- 开始前 Editor：288 项通过，6.97 秒
- 开始前 Uploader：126 项通过，1.58 秒
- 开始前 Uploader 未提交差异：0

本阶段未修改 Builder 算法、模板、黄金 BIN、冻结 ZIP、真实抓包或任何生产源码。必须区分：

- Editor Stage 7A1 archive ZIP：`$REPO/archives/editor/Ultra3_Editor_Stage7A1_Frozen_2026-07-13.zip`，
  SHA-256 为 `D5D3A9BB55D245C2AE38D41318C6311EAB57424B603575E9D8B3667D60721D7C`，角色是
  Editor 历史阶段归档。
- Builder v0.2.4 frozen baseline ZIP：`$FROZEN_ZIP`，SHA-256 为
  `3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231`，角色是
  GreenLion Builder v0.2.4 冻结基线，也是本阶段 Builder/Handoff 事实的主要来源。

两者不是同一个文件，SHA 不同是正常现象，禁止将其中一个哈希用作另一个 ZIP 的校验值。

## 2. 当前 Uploader 输入契约审计

审计对象包括 Uploader 的 CLI、payload 校验、C8/C9 协议、准备会话、上传状态机、BLE
transport、真实上传安全门、测试、Stage 5/6A/6B/6C 报告及已归档日志。结论严格区分代码实现、
离线测试和真实抓包。

| # | 审计问题 | 结论 | 证据等级 |
|---:|---|---|---|
| 1 | CLI 当前接受什么文件 | `inspect`、`build-c8`、`prepare-bcsdial`、`upload-bcsdial` 最终使用 `BCSDIALPayload`；要求非空、`BCSDIAL` 头及 `BCBC` 尾 | IMPLEMENTED |
| 2 | 是否接受完整 BIN | 接受动态 BCSDIAL 完整文件；不接受 GreenLion Static DIY 351617 字节完整 BIN | IMPLEMENTED / NOT SUPPORTED |
| 3 | 是否接受 payload | 不接受 Frozen Builder 的 353146 字节派生 payload，也没有 payload 输入 CLI | NOT SUPPORTED |
| 4 | 是否接受已组装 C9 | 不接受预组装 C9 帧流；当前代码从文件数据自行构造 C9 | NOT SUPPORTED |
| 5 | 谁负责 230-byte 数据块 | Uploader 的 C9 迭代器对受支持文件按最多 230 字节切块 | IMPLEMENTED / VERIFIED BY TEST |
| 6 | 谁负责每块 checksum | Uploader 根据 sequence 与 DATA 计算每个 C9 checksum | IMPLEMENTED / VERIFIED BY TEST |
| 7 | 谁负责 C9 包装 | Uploader 包装 `BC C9 02 LEN SEQ_LE16 DATA CHECKSUM` | IMPLEMENTED / VERIFIED BY TEST |
| 8 | 谁等待 CA | Uploader 状态机等待 FF03 的 CA success，再发送一次 CA apply | IMPLEMENTED / VERIFIED BY TEST；动态 BCSDIAL 路径 VERIFIED BY CAPTURE |
| 9 | 是否有开始、结束或状态命令 | C8 是现有准备入口，CA success/apply 是现有完成阶段；没有面向静态 Handoff 的独立 start/end/status CLI | IMPLEMENTED / NOT SUPPORTED |
| 10 | 是否有断点、重试、超时 | 有 ready/CA 等超时和进度；无自动重试、断点续传或失败后续传 | IMPLEMENTED / VERIFIED BY TEST |
| 11 | 是否验证输入 SHA | 真实 `upload-bcsdial` 在创建 transport 前校验显式 expected SHA；Fake 路径不要求真实上传授权；当前无 Handoff SHA 预检 | IMPLEMENTED / NOT SUPPORTED |
| 12 | 是否验证文件大小 | 校验非空、协议包数边界并从实际大小计算包数；不接受或验证固定 351617 静态格式 | IMPLEMENTED / NOT SUPPORTED |
| 13 | 是否验证文件头 | 强制动态 `BCSDIAL` 头和 `BCBC` 尾；没有 GreenLion 17 字节头验证入口 | IMPLEMENTED / NOT SUPPORTED |
| 14 | 是否验证固件范围 | 当前上传流程不验证 `NJ-LEJ-2.1.7` firmware scope | NOT SUPPORTED |
| 15 | 是否硬编码设备地址 | 真实 CLI 要求用户传入 `--device`，地址不在 constants；Fake 默认标识不构成真实地址选择 | IMPLEMENTED |
| 16 | 是否硬编码 MTU | 不硬编码实际 MTU；运行时读取能力，真实预检要求 MTU >= 240、最大无响应写入 >= 237；归档实测为 247/244 | IMPLEMENTED；247/244 VERIFIED BY CAPTURE |
| 17 | 是否混用动态与静态 DIY | 没有静态上传实现；相同的部分 C8/C9 现象不能证明两种容器可混用 | NOT SUPPORTED / UNKNOWN |
| 18 | 测试覆盖哪些真实协议结论 | Fake/RealTransportStub 覆盖帧、序列、checksum、状态机、失败清理与安全门；Stage 5/6A 抓包验证 GATT/C8/D1；真实 Stage 6C 日志验证动态 BCSDIAL 长传输。静态完整 BIN 上传未验证 | VERIFIED BY TEST / VERIFIED BY CAPTURE / UNKNOWN |

关键结论：**当前 Uploader 不支持 GreenLion Static DIY 351617 字节完整 BIN。** 现有真实上传证据只适用于
动态 BCSDIAL，不能外推为静态 DIY 真机上传能力。

## 3. 完整 BIN、派生 payload 与 BLE C9

| 层级 | 已知大小/形式 | 含义 | 当前 Uploader 输入 |
|---|---|---|---|
| Editor source artifact | 351617 bytes | 17 字节头 + 320×384 主资源 + 210×252 缩略图的完整 GreenLion Static DIY BIN | 不支持 |
| 静态抓包 C9 DATA 拼接 | 351617 bytes | 1529 个 C9 的 DATA 原序拼接；不是带头的 C9 帧流 | 没有静态入口 |
| Frozen Builder derived payload | 353146 bytes | 已冻结审计派生物；不是完整 C9 帧流 | 不支持 |
| BLE C9 frames | `BC C9 02 LEN SEQ_LE16 DATA CHECKSUM` | 传输层帧，包含 LEN、sequence、checksum | 不接受预组装输入 |

353146 只能作为已冻结派生物事实记录。当前真实 Uploader/抓包证据不足以把它定义为静态上传的必需 payload，
因此 Handoff v1 不包含它，也不填写 1529 包。

## 4. Editor、Uploader 与 GUI 职责边界

Editor 负责图片解码、cover/resize、GreenLion next-high RGB565、完整 BIN 组装、写后复核，以及未来由
Builder 生成 Manifest。Editor 不生成传输 payload、C9、CA 或 BLE 状态。

Uploader 负责独立读取和验证 Manifest/BIN、判断 firmware scope、在协议获得实现与验证后生成传输派生物和
C9，并独占负责设备连接、MTU、FF03、CA、超时、进度及未来明确批准的重试策略。当前实现没有自动重试或续传。

GUI 只创建 BIN、展示结果和打开输出位置。本阶段没有添加上传按钮，没有导入或调用 Uploader，也没有改变
Editor 与 Uploader 的进程边界。

## 5. Handoff Bundle 与 Manifest v1

建议生产 Bundle：

```text
bundle/
  watchface.bin
  watchface.handoff.json
```

版本标识为 `ultra3-handoff/v1`，artifact type 固定为
`greenlion_static_diy_complete_bin`。Manifest 记录完整 artifact 的相对路径、351617 字节大小、SHA-256、
container、firmware scope、Builder/Pillow 版本、模板身份、固定布局、资源规格、构建验证、Level C 设备证据，
以及明确未准备传输的 `transfer` 状态。

本阶段创建：

- `docs/handoff/ultra3_handoff_v1.schema.json`
- `docs/handoff/README.md`
- `editor/artifacts/stage8c0_handoff_design/golden_match.handoff.json`
- `editor/artifacts/stage8c0_handoff_design/custom_not_applicable.handoff.json`
- `editor/artifacts/stage8c0_handoff_design/README.md`
- `editor/artifacts/stage8c0_handoff_design/audit_results.json`
- `editor/scripts/audit_stage8c0_handoff.py`

## 6. JSON Schema 与固定结构

Schema 明确使用 JSON Schema Draft 2020-12，根和全部嵌套对象均为
`additionalProperties: false`。核心固定值：

- `artifact_size = 351617`
- 17 字节头：`02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00`
- `template_offset_zero = 2`
- Header：`[0, 17)`，17 bytes
- Main：`[17, 245777)`，245760 bytes，320×384
- Thumbnail：`[245777, 351617)`，105840 bytes，210×252
- `firmware_scope = ["NJ-LEJ-2.1.7"]`
- `determinism_status = not_evaluated`
- `transfer.status = not_prepared`
- `payload_size = null`
- `chunk_count = null`
- `ble_frames_present = false`

Schema 是离线交接契约，不是 BLE 协议定义。

## 7. 路径安全、SHA 与独立预检

`artifact_path` 必须为 POSIX 风格相对路径，拒绝绝对路径、Windows drive、反斜杠、NUL 和任意 `..`
路径段。Uploader 下一阶段必须以 Manifest 同目录或用户显式 bundle root 解析路径，并独立检查解析后路径仍在
bundle 内、artifact 是普通文件且不是越界符号链接。

Uploader 不得信任 Editor Manifest。建议按以下顺序离线预检：

1. 解析 JSON 并精确支持 schema。
2. 安全解析 artifact 路径。
3. 检查普通文件、固定大小和重新计算 SHA-256。
4. 读取并验证 17 字节头、offset 0=`02` 与布局边界。
5. 验证 artifact type 和目标 firmware scope。
6. 验证 `transfer.status=not_prepared`，且无 payload/chunk/C9 数据。
7. 显示 Level C 警示，生成结构化结果；在所有错误为空前不得进入传输准备。

Golden 状态不是唯一上传许可条件。`not_applicable` 表示合法自定义构建，不能仅因不匹配黄金样本而拒绝。

## 8. offset 0、时间位置与设备证据

Handoff 只记录 `template_offset_zero = 2`。`02` 是冻结 Builder 模板事实，**不得解释为 Top 或 Bottom**，
不得调用 Stage 7B-1 时间位置编辑，也不得自动改写为 `00` 或 `01`。Schema 的未知字段拒绝策略同时禁止加入
Top/Bottom 字段。

`device_evidence.level` 固定为 `C`：离线构建和归档上传文字证据存在，但逐样本真机截图/抓包尚未归档。
该级别必须显著展示，但不应自动把合法自定义构建判为无效。

## 9. 文件所有权与不可变性

- Editor 独占创建并关闭 BIN/Manifest；交接后不再修改 Bundle。
- Uploader 以只读方式打开 Bundle，不原地修改 BIN。
- payload、session、packet 和 upload log 只能写入独立、不覆盖的 transfer 输出目录。
- 上传失败不得修改 source artifact；人工重试必须复用相同 artifact SHA。
- Uploader 日志必须记录 source artifact SHA，不能只依赖文件名。
- 输入文件不得兼作临时输出；既有传输记录不得覆盖。
- 除非用户显式选择新目录，传输派生物不得写回 Editor artifact 目录。

未来 transfer 目录可包含 `session.json`、`payload.bin`、`packets.jsonl`、`upload.log`，但 Stage 8C-0
没有生成任何此类文件。

## 10. 错误模型与下一阶段 API

建议 Uploader 错误层级：

`HandoffError`、`UnsupportedHandoffSchemaError`、`HandoffPathError`、
`HandoffArtifactMissingError`、`HandoffArtifactSizeError`、`HandoffArtifactHashError`、
`HandoffHeaderError`、`HandoffLayoutError`、`UnsupportedArtifactTypeError`、
`FirmwareScopeMismatchError`、`HandoffAlreadyPreparedError`。

结构化错误至少保留 `error_code`、`path`、`expected`、`actual`、`schema_version` 和
`artifact_sha256`。Editor 只报告构建/导出错误；Uploader 负责 Handoff、固件和传输错误，不能让 GUI
代替其验证。

下一阶段建议只实现离线 API：

```python
def validate_handoff(
    manifest_path: Path,
    *,
    bundle_root: Path | None = None,
    target_firmware: str | None = None,
) -> UploaderHandoffValidationResult:
    ...
```

结果字段：`status`、`schema_version`、`artifact_path`、`size_valid`、`sha_valid`、
`header_valid`、`layout_valid`、`firmware_compatible`、`transfer_unprepared`、`warnings`、
`errors`、`safe_to_prepare_transfer`。

对应 CLI 设计：

```powershell
python -m ultra3_uploader validate-handoff --manifest .\watchface.handoff.json
```

它只输出 schema、artifact、size、SHA、header、offset 0、firmware scope、warnings 和
`safe_to_prepare_transfer`，并保证 BLE usage=0。**不要在 Stage 8C-1 同时实现 `upload-handoff`。**

## 11. 离线样例与契约测试

| 样例 | artifact | Golden 状态 | artifact SHA-256 | 结果 |
|---|---|---|---|---|
| Golden MATCH | 现有 `stage8b2_gui_builder/golden_match.bin` | `match` / `true` | `44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664` | 通过 |
| Custom NOT_APPLICABLE | 现有 `stage8b2_gui_builder/custom_not_applicable.bin` | `not_applicable` / `null` | `1D87836F3D985409F7787254B5ABFECAA81543D99082FAAC2FAC962B6ADBFC6C` | 通过 |

样例只引用既有 BIN，没有复制大型 artifact。两个样例的真实文件大小、SHA、17 字节头和 offset 0 均由
只读审计脚本重新计算。Manifest 私人绝对路径、用户名、AppData、设备地址、Top/Bottom 命中数为 0。

`editor/scripts/audit_stage8c0_handoff.py` 使用 Python 标准库，不导入生产模块。结果：

- 51/51 契约、安全、拒绝与可重复生成测试通过。
- 分类：原 Stage 8C-0 契约 20、规范路径接受 4、非规范/危险路径拒绝 19、SHA 格式 8。
- Golden 与 NOT_APPLICABLE 样例错误均为空。
- 额外使用环境现有 `jsonschema` 按 Draft 2020-12 验证：2/2 通过。
- `audit_results.json` 状态：`COMPLETE`。

覆盖错误 schema、绝对路径、`..`、错误大小/SHA/offset/header/layout、已准备 transfer、payload size、
chunk count、BLE frames、Top/Bottom、设备地址和私人路径，并验证真实 artifact SHA 与可重复生成。

## Freeze Hardening

Stage 8C-0.1 在不修改生产源码和两个标准 Manifest 语义的前提下完成冻结前补强：

- `artifact_path` 现在只接受规范 POSIX 相对文件路径；拒绝 `.`、`..`、空路径段、尾随 `/`、
  根路径、反斜杠、Windows drive/UNC、URI、冒号、ADS、NUL 和空字符串。
- Schema 与标准库运行时检查共同覆盖 4 个接受样例和 19 个拒绝样例。Schema 只是第一层结构验证；
  未来 Uploader 仍必须执行 resolve、bundle containment、符号链接、普通文件及内容复核。
- `artifact_sha256` 收紧为 64 位大写十六进制；小写、混合大小写、63/65 位、非十六进制及空格均拒绝。
- `template_sha256` 继续使用固定大写常量
  `5D04DE76C94DA9D7F7069AF3E6038E1575D3B42E5E009EAD590CE4DD33F5E1CC`。
- 待提交 Markdown/JSON 使用 `$REPO`、`$FROZEN_ZIP` 等逻辑根；本机路径扫描命中为 0。
- Editor Stage 7A1 archive ZIP 与 Builder v0.2.4 frozen baseline ZIP 已在第 1 节明确区分，修改前后
  只读哈希分别保持 `D5D3A9BB55D245C2AE38D41318C6311EAB57424B603575E9D8B3667D60721D7C`
  和 `3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231`。
- `audit_results.json` 由脚本独占重新创建；临时备份只在新结果验证完成后删除。Schema SHA-256 为
  `FB4E5BBFEC42D0E75F251B5512A374CB3E222625711B79653C3C07638B331DA5`。
- 最终契约测试为 51/51，两个标准样例继续通过，Golden/Custom artifact SHA 均未变化。
- `editor/src` 与 `uploader/src` 差异均为 0；未实现 Handoff CLI、payload、静态 C9 或上传。

## 12. 最终回归与零副作用核验

- Editor：288 项执行通过，6.81 秒；收集数量 288。
- Uploader：126 项执行通过，2.04 秒；收集数量 126。
- `git diff -- editor/src`：无输出。
- `git diff -- uploader/src`：无输出。
- `git diff -- uploader`：无输出。
- `git diff --check`：通过。
- GUI 上传按钮：未添加。
- Builder/Uploader 互相导入：未添加。

外部调用统计：

| 调用 | 次数 |
|---|---:|
| Bleak initialization | 0 |
| BLE scan | 0 |
| BLE connect | 0 |
| FF02 write | 0 |
| FF03 notify | 0 |
| adb | 0 |
| Frida | 0 |
| Uploader runtime calls | 0 |
| 网络请求 | 0 |
| 真实上传 | 0 |

## 13. 验收结论与下一阶段建议

- [OK] Stage 8B-2 标签和提交基线已确认。
- [OK] 当前 Uploader 输入类型及协议职责已审计。
- [OK] 351617 完整 BIN、353146 派生 payload 和 C9 帧已明确分层。
- [OK] 当前静态 DIY 上传状态明确为 **NOT SUPPORTED**。
- [OK] Handoff v1、Draft 2020-12 Schema、文档、两个样例和审计结果已创建。
- [OK] artifact 大小、SHA、header、offset 0、布局和 firmware scope 已固化。
- [OK] Manifest 不包含 payload、C9、设备地址、Top/Bottom 或私人绝对路径。
- [OK] `transfer.status=not_prepared`，Device evidence 保持 Level C。
- [OK] Editor/Uploader/GUI 职责、所有权、错误边界和独立复核规则明确。
- [OK] Editor 288 项、Uploader 126 项通过，生产源码差异为 0。
- [OK] BLE/ADB/Frida/网络/Uploader runtime/上传均为 0。
- [OK] 未进入 Stage 8C-1。

下一阶段仅建议实现 Uploader 侧离线 `validate_handoff()` 与 `validate-handoff` CLI，并用内存 stub/文件
fixture 测试，不连接设备、不生成传输 payload、不构造静态 C9，也不实现 `upload-handoff`。静态传输 payload
规则和长时间真机行为仍需独立协议证据后才能进入上传实现。

本阶段未提交、未打标签、未推送，等待人工验收。
