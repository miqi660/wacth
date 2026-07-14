# Stage 8C-1 — Offline Handoff Validation Core and CLI

日期：2026-07-14  
状态：**COMPLETE · OFFLINE VALIDATION ONLY**  
真实上传：**未执行**

## 1. Git 审计与修改前基线

| 项目 | 结果 |
|---|---|
| 分支 | `main` |
| 工作区 | 修改前干净 |
| HEAD | `b8fe42bd3ee5ac42a0962c7fb3360c28711bb747` |
| origin/main | `b8fe42bd3ee5ac42a0962c7fb3360c28711bb747` |
| 冻结标签 | `ultra3-editor-v0.3.6-stage8c0` 存在并指向 HEAD |
| Stage 8C-0 契约 | 已进入 HEAD |
| Editor/Uploader 差异 | 修改前均为 0 |
| 修改前 Editor | 288 项通过，6.96 秒 |
| 修改前 Uploader | 126 项通过，2.14 秒 |

执行了 `git fetch origin` 并重新确认 HEAD 与 origin/main 一致。未执行 reset、clean、checkout、commit、
tag 或 push。

## 2. 冻结 Schema 与 package data

- 契约：`ultra3-handoff/v1`
- JSON Schema Draft：2020-12
- docs Schema：`$REPO/docs/handoff/ultra3_handoff_v1.schema.json`
- 包内 Schema：`$UPLOADER/src/ultra3_uploader/schemas/ultra3_handoff_v1.schema.json`
- 两者逐字节一致：是
- SHA-256：`FB4E5BBFEC42D0E75F251B5512A374CB3E222625711B79653C3C07638B331DA5`
- 加载方式：`importlib.resources.files()`
- package data：`pyproject.toml` 明确收录 `ultra3_uploader.schemas/*.json`
- 工作目录外读取：通过
- 临时 zipimport 安装形态读取：通过，Schema SHA 精确匹配

本机环境缺少 `bdist_wheel`，因此没有联网安装 wheel 工具；改用离线 zipimport 包验证安装形态下的
`importlib.resources` 行为。临时包验证后已删除，仓库内未留下构建产物。

## 3. JSON Schema 验证器

- 依赖声明：`jsonschema>=4.21,<5`
- 实际版本：`4.26.0`
- 验证器：`Draft202012Validator`
- 每次创建验证器前调用 `check_schema()`。
- 拒绝包内 Schema 的任何非 `#` 本地 `$ref`。
- 不解析远程 reference，不下载 Schema，不执行网络请求。

## 4. 公共 API 与不可变模型

唯一公共入口：

```python
validate_handoff(
    manifest_path: Path,
    *,
    bundle_root: Path | None = None,
    target_firmware: str | None = None,
) -> UploaderHandoffValidationResult
```

公开导出：`validate_handoff`、`UploaderHandoffValidationResult`、`HandoffValidationIssue`、
`HandoffValidationStatus`、`HandoffExternalUsage`。结果、issue 和外部统计均为 frozen dataclass；状态枚举为
`valid` / `invalid`。

预期的 Bundle 或用户输入错误不抛 traceback，而是返回 INVALID 结果及结构化 issue。issue 保留
`error_code`、中文消息、逻辑路径、expected 和 actual。

## 5. Manifest 安全读取

实现顺序：

1. `lstat` 确认存在。
2. 拒绝符号链接和 Windows reparse point。
3. 确认普通文件。
4. 在读取前执行 64 KiB 上限。
5. 只读读取并记录大写 Manifest SHA-256。
6. 拒绝 UTF-8 BOM。
7. 使用严格 UTF-8 解码。
8. 使用 `object_pairs_hook` 在根和任意嵌套层拒绝重复 key。
9. 使用 `parse_constant` 拒绝 NaN、Infinity 和 -Infinity。
10. 标准 `json.loads` 拒绝 comment、无效 JSON 和尾随内容。
11. 根值必须是 object。
12. Draft 2020-12 Schema 严格验证未知字段、固定值和字段关系。

Manifest 不被修改；测试验证前后 SHA 不变，并确认验证过程不创建文件。

## 6. artifact_path、bundle containment 与链接规则

运行时独立复核 canonical path，不仅依赖 Schema：非空、POSIX `/`、非根路径、无 Windows drive、
反斜杠、冒号、NUL、`.`、`..`、空路径段或尾随 slash。

未提供 `bundle_root` 时使用 Manifest 父目录；显式提供时使用调用者目录。根目录必须存在、是目录，
且不是符号链接/reparse point。实现使用 resolve 后的 normcase/commonpath containment 检查，同时逐组件
`lstat`，拒绝中间目录链接、最终 artifact 链接、junction/reparse 风险、非普通文件、缺失文件和 artifact
回指 Manifest。

一旦路径不安全，不读取 artifact。Windows 无符号链接权限的测试使用 monkeypatch 直接验证所有拒绝分支，
未删除或跳过安全测试。

## 7. artifact 只读复核

只有 Schema 和路径均通过才打开 artifact。验证内容：

- 固定大小：351617 bytes。
- Manifest SHA 为大写 64 位十六进制，并由 Uploader 流式独立重算。
- 固定 17 字节 header：`02 00 00 FF FF FF 00 00 80 01 40 01 FC 00 D2 00 00`。
- offset 0：整数 `2`，不解释为 Top 或 Bottom。
- layout：header `[0,17)`、main `[17,245777)`、thumbnail `[245777,351617)`。
- 验证前路径 stat、打开句柄前后 fstat、验证后路径 stat 的 `size/mtime_ns/dev/ino` 完全一致。

大小、SHA、header、offset、layout 和验证期间变化分别产生独立 issue。读取使用 1 MiB 流式块，不在内存
保留多份 artifact。只读权限、输入 SHA 不变、Manifest SHA 不变和无新增文件均有测试。

## 8. Firmware、Golden、Device evidence 与 transfer

固定 firmware scope 为 `NJ-LEJ-2.1.7`：

| target_firmware | status | firmware_compatible | safe | 结果 |
|---|---|---:|---:|---|
| 未提供 | VALID | `None` | `False` | warning `target_firmware_not_provided` |
| `NJ-LEJ-2.1.7` | VALID | `True` | `True` | 全部离线条件满足 |
| 其他版本 | INVALID | `False` | `False` | `firmware_scope_mismatch` |

Golden MATCH 与 Custom NOT_APPLICABLE 都执行完全相同的路径、大小、SHA、header、offset、layout 和固件
复核。MATCH 不跳过 SHA；NOT_APPLICABLE 不是 warning 或 error。

`device_evidence.level=C` 保留并产生明确 Level C warning。`transfer` 必须精确为
`not_prepared/null/null/false`；任何已准备状态均为 INVALID。

## 9. safe_to_prepare_transfer 语义

只有 errors 为空、status VALID、Schema/路径/artifact 全部复核、artifact 未变化、固件明确匹配且 transfer
未准备时才为 `True`。

`True` 只表示允许进入未来的离线“传输准备”步骤；不表示静态 payload、静态 C9、设备连接、真机验证或
真实上传已经实现。CLI 人类输出和 JSON 均显示该边界。

## 10. validate-handoff CLI

```powershell
python -m ultra3_uploader validate-handoff `
  --manifest .\watchface.handoff.json `
  --bundle-root . `
  --target-firmware NJ-LEJ-2.1.7 `
  --json
```

参数仅有 `--manifest`、可选 `--bundle-root`、`--target-firmware` 和 `--json`。没有 `--upload`、
`--device`、`--force`、`--payload`、`--chunks`、`--prepare` 或 `--connect`。

默认输出 status、schema、Manifest、相对 artifact、大小/SHA、header/offset/layout、文件不变性、固件、
transfer、Level C、Golden、safe、warnings/errors、全部零外部统计和安全边界。JSON 只写 stdout，不创建
输出文件，并用输入路径或 artifact 相对路径避免额外暴露绝对路径。

退出码：VALID=`0`，INVALID=`1`，argparse 使用错误=`2`。固件未提供时 VALID/safe=False，仍返回 0。
普通验证错误不输出 traceback。

## 11. 两个真实 Stage 8C-0 样例

规范化结果：`$UPLOADER/artifacts/stage8c1_handoff_validation/sample_validation_results.json`

| 样例 | artifact SHA-256 | Golden | 固件 | status | safe |
|---|---|---|---|---|---:|
| Golden | `44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664` | match | 未提供 | VALID | False |
| Golden | 同上 | match | 匹配 | VALID | True |
| Custom | `1D87836F3D985409F7787254B5ABFECAA81543D99082FAAC2FAC962B6ADBFC6C` | not_applicable | 未提供 | VALID | False |
| Custom | 同上 | not_applicable | 匹配 | VALID | True |

4/4 验证的大小均为 351617，header/offset/layout/artifact unchanged/transfer 均为 true，Device evidence
均为 C，外部调用全部为 0。结果中私人绝对路径、设备地址命中为 0。

## 12. 测试与回归

| 项目 | 结果 | 时间 |
|---|---:|---:|
| 新增 Handoff 聚焦测试 | 72 passed | 约 2.0 秒 |
| Uploader 全量 | 198 passed | 3.30 秒 |
| 原 Uploader 测试 | 126 全部保留 | — |
| Editor 全量 | 288 passed | 6.78 秒 |

新增覆盖公共导入、frozen 模型、Schema 字节/SHA/包资源、Golden/Custom、Manifest 所有解析错误、路径、
containment、链接/reparse、artifact 内容与变化、只读不变性、固件、Golden 语义、CLI 输出/退出码/禁用参数、
零文件输出和零外部副作用。

## 13. 原协议、transport 与静态边界

- `editor/src` 差异：0。
- `docs/handoff` 差异：0。
- 动态 BCSDIAL、C8/C9、prepare、real upload、upload state machine 源码差异：0。
- BLE transport 与 Bleak transport 源码差异：0。
- Handoff 核心 `handoff.py` 对禁止操作词的静态扫描：0。
- `handoff_models.py` 只包含规范强制的 frozen 零值统计字段，不含操作、导入或调用。
- Handoff 核心不导入 Editor、Pillow、Builder、GUI、BLE transport、上传状态机或帧构建器。

## 14. 外部调用与未实现边界

| 调用/产物 | 次数 |
|---|---:|
| Bleak initialization | 0 |
| BLE scan | 0 |
| BLE connect | 0 |
| FF02 write | 0 |
| FF03 notify | 0 |
| adb | 0 |
| Frida | 0 |
| network requests | 0 |
| payload generated | 0 |
| C9 frame generated | 0 |
| real upload | 0 |

本阶段没有实现 `upload-handoff`、传输准备、353146 payload、静态分包/checksum、C8、CA、设备检测或 GUI
上传按钮，也没有让现有 `upload-bcsdial` 接受静态 BIN。

## 15. 修改与新增文件

新增：

- `uploader/src/ultra3_uploader/handoff.py`
- `uploader/src/ultra3_uploader/handoff_models.py`
- `uploader/src/ultra3_uploader/schemas/__init__.py`
- `uploader/src/ultra3_uploader/schemas/ultra3_handoff_v1.schema.json`
- `uploader/tests/test_handoff.py`
- `uploader/tests/test_handoff_cli.py`
- `uploader/scripts/verify_stage8c1_handoff_samples.py`
- `uploader/artifacts/stage8c1_handoff_validation/sample_validation_results.json`
- 本报告

修改：

- `uploader/src/ultra3_uploader/__init__.py`
- `uploader/src/ultra3_uploader/cli.py`
- `uploader/pyproject.toml`
- `uploader/README.md`

## 16. 验收结论

- [OK] 冻结标签、Schema SHA 和两个真实 artifact SHA 已复核。
- [OK] `validate_handoff()` 与 `validate-handoff` 已实现。
- [OK] 严格 Manifest、Schema、路径、containment、链接和 artifact 只读复核已实现。
- [OK] 固件缺失/匹配/不匹配语义及 safe 边界正确。
- [OK] MATCH 与 NOT_APPLICABLE 均完整验证。
- [OK] Uploader 198、Editor 288 全部通过。
- [OK] 原动态协议、transport、Editor 和冻结 Handoff 契约无差异。
- [OK] payload/C9/BLE/ADB/Frida/网络/上传全部为 0。

尚未支持：静态传输派生物、静态协议分包、设备连接、传输执行和 GUI 上传。它们必须在后续阶段获得独立
协议证据与明确授权后再实现。

本阶段未提交、未打标签、未推送，等待人工验收。
