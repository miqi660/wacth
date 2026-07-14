# Ultra3 Editor → Uploader Handoff v1

本目录定义 GreenLion Static DIY 完整 BIN 的离线交接契约。它不是 BLE 协议定义，也不表示
当前 Uploader 已支持该静态格式。

## 当前兼容性结论

| 项目 | 当前状态 | 证据等级 |
|---|---|---|
| 动态 BCSDIAL 完整文件 | Uploader 接受；必须有 `BCSDIAL` 头和 `BCBC` 尾 | IMPLEMENTED / VERIFIED BY TEST |
| GreenLion Static DIY 完整 BIN（351617） | 当前 Uploader 拒绝，尚无 Handoff 入口 | NOT SUPPORTED |
| 冻结 Builder 派生 payload（353146） | 当前 Uploader 不接受；它不是完整 C9 帧流 | NOT SUPPORTED |
| 已组装 C9 帧 | 当前 Uploader 不接受；现有代码自行构造 C9 | NOT SUPPORTED |
| 静态 DIY 真机上传 | 尚未由当前 Uploader 实现或验证 | UNKNOWN |

现有 Uploader 对其支持的动态 BCSDIAL 文件直接按 230 字节切块，计算 sequence checksum，
包装 `BC C9 02 LEN SEQ_LE16 DATA CHECKSUM`，等待 FF03 的 CA success 后发送一次 CA apply。
该实现不能直接外推为静态 DIY 支持。

归档事实必须分开理解：

- Builder 完整输出：351617 字节。
- 静态真实抓包的 1529 个 C9 DATA 原序拼接：351617 字节。
- Frozen Builder 的 `payload_353146.bin`：353146 字节派生物；已审计为非完整 C9 帧流，
  当前 Uploader 没有对应输入契约。
- BLE C9 帧还包含协议头、LEN、sequence 和 checksum，不属于 Editor Manifest。

## Bundle 与路径

建议生产 Bundle：

```text
bundle/
  watchface.bin
  watchface.handoff.json
```

仓库内设计样例使用仓库相对路径，审计时显式以仓库根为 bundle root；生产 Bundle 应优先让 BIN
与 Manifest 同目录。

Manifest 不得包含私人绝对路径、用户名、AppData、临时目录、Python 路径、设备地址、原始照片、
payload、C9 帧或未经验证的屏幕尺寸。offset 0 只能记录整数 `2`，不得解释为时间位置。

## Canonical artifact_path

`artifact_path` 必须是指向文件的规范 POSIX 相对路径：

- 只使用 `/`，不允许反斜杠、Windows drive 或 UNC 路径。
- 不允许 `.`、`..`、空路径段、尾随 `/` 或根路径。
- 不允许冒号，因此 URI、Windows ADS 和带 scheme 的字符串均被拒绝。
- 不允许 NUL 或空字符串。

JSON Schema 只负责第一层语法和结构拒绝，不能单独保证文件系统安全。未来 Uploader 仍必须解析
Manifest 所在目录和显式 `bundle_root`，resolve `artifact_path`，确认结果仍位于 bundle root 内，
拒绝越界符号链接、artifact 符号链接和非普通文件，再独立复核实际大小、SHA-256、header 与 offset 0。
SHA-256 字段统一为 64 位大写十六进制。

## Uploader 独立预检

Uploader 不得信任 Editor 的结论，下一阶段必须独立执行：

1. 解析 Manifest，精确支持 `ultra3-handoff/v1`。
2. 安全解析 `artifact_path`，确保文件位于 bundle root。
3. 验证普通文件、351617 字节、SHA-256、17 字节头和 offset 0=`02`。
4. 验证固定布局、artifact type、firmware scope 与 `transfer.status=not_prepared`。
5. 确认 Manifest 不携带 payload、chunk count 或 BLE 帧。
6. 将 Level C 证据作为警示展示；`NOT_APPLICABLE` 是合法自定义构建，Golden 不能作为唯一许可条件。

建议结果模型：

```python
@dataclass(frozen=True)
class UploaderHandoffValidationResult:
    status: str
    schema_version: str
    artifact_path: Path
    size_valid: bool
    sha_valid: bool
    header_valid: bool
    layout_valid: bool
    firmware_compatible: bool
    transfer_unprepared: bool
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    safe_to_prepare_transfer: bool
```

建议下一阶段公开 API：

```python
def validate_handoff(
    manifest_path: Path,
    *,
    bundle_root: Path | None = None,
    target_firmware: str | None = None,
) -> UploaderHandoffValidationResult:
    ...
```

CLI 只先实现离线预检：

```powershell
python -m ultra3_uploader validate-handoff --manifest .\watchface.handoff.json
```

`upload-handoff` 不属于 Stage 8C-0。

## 所有权与错误边界

- Editor 创建并关闭 BIN/Manifest，完成后不再修改 Bundle。
- Uploader 只读打开 Bundle，不原地修改 BIN。
- payload、日志和传输记录只能写入独立且不覆盖的输出目录。
- 上传失败不得修改原 BIN；重试必须继续引用相同 artifact SHA。
- Editor 负责构建错误；Uploader 负责 Manifest、路径、artifact、固件与传输错误。

建议 Uploader 异常：`HandoffError`、`UnsupportedHandoffSchemaError`、`HandoffPathError`、
`HandoffArtifactMissingError`、`HandoffArtifactSizeError`、`HandoffArtifactHashError`、
`HandoffHeaderError`、`HandoffLayoutError`、`UnsupportedArtifactTypeError`、
`FirmwareScopeMismatchError`、`HandoffAlreadyPreparedError`。错误应保留 `error_code`、`path`、
`expected`、`actual`、`schema_version` 和 `artifact_sha256`。

## 契约验证

Schema 使用 JSON Schema Draft 2020-12，并在每层采用明确的 `additionalProperties: false`。
标准库审计命令：

```powershell
python .\editor\scripts\audit_stage8c0_handoff.py
```

脚本不导入 Editor/Uploader 生产模块，不调用 BLE、adb、Frida、网络或上传。
