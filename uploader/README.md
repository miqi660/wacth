# Ultra3 Uploader v0.3.0

当前版本提供动态 `BCSDIAL` 离线协议工具，以及 Stage 5 的 BLE 扫描、GATT 检查和
FF03 安全监听。`scan`、`info`、`listen` 均不会调用 FF02 写入，不发送 C8、C9 或 CA，
也不实现静态图片表盘上传。

## 安装与测试

```powershell
cd .\uploader
python -m pip install -e .
python -m pytest
```

黄金回归默认依次查找：

1. 环境变量 `ULTRA3_ARCHIVE_ROOT`；
2. `uploader` 的父目录；
3. `%USERPROFILE%\Desktop\Ultra3-Reverse_Updated_2026-07-13`。

## 离线命令

```powershell
python -m ultra3_uploader inspect "C:\path\watchface.bin"
python -m ultra3_uploader build "C:\path\watchface.bin" --output .\generated_packets.jsonl
python -m ultra3_uploader compare-capture --file "C:\path\watchface.bin" --capture "C:\path\capture_light_v2.log"
```

`build` 默认拒绝覆盖已有输出；只有显式传入 `--force` 才覆盖。

### Stage 8C-1：Handoff v1 离线预检

```powershell
python -m ultra3_uploader validate-handoff `
  --manifest .\watchface.handoff.json `
  --target-firmware NJ-LEJ-2.1.7

python -m ultra3_uploader validate-handoff `
  --manifest .\watchface.handoff.json `
  --bundle-root . `
  --json
```

该命令使用 Uploader 包内逐字节冻结的 JSON Schema Draft 2020-12，严格读取 Manifest，并独立
复核规范相对路径、bundle containment、351617 字节 artifact、SHA-256、17 字节 header、offset 0、
固定布局、firmware scope 和 `transfer.status=not_prepared`。未提供目标固件时，合法 Bundle 返回
`VALID`，但 `safe_to_prepare_transfer=false` 并产生 warning。

`safe_to_prepare_transfer=true` 只表示离线 Handoff 满足未来传输准备的前置条件，不表示静态
payload/C9 已实现，不表示可连接设备或执行真实上传。该命令不创建输出文件，不初始化 BLE，
也不接受 `--device`、`--upload`、`--force` 或 payload 相关参数。

### Stage 8C-3A：静态 Handoff 离线传输计划

Stage 8C-3A 只构建和验证离线 C9 帧，不连接 BLE。Handoff v1 仍只描述 351617-byte source BIN，
因此 payload 必须通过独立路径和期望 SHA-256 显式提供，不能从 source BIN 暗中派生：

```powershell
python -m ultra3_uploader build-static-plan `
  --manifest .\watchface.handoff.json `
  --payload .\payload_353146.bin `
  --expected-payload-sha256 "<64位SHA-256>" `
  --bundle-root . `
  --target-firmware NJ-LEJ-2.1.7 `
  --output .\static-plan `
  --json

python -m ultra3_uploader inspect-static-plan --plan .\static-plan --json
python -m ultra3_uploader verify-static-plan --plan .\static-plan --json
```

计划目录固定包含 `manifest.json` 和 `c9_frames.bin`，使用独占创建且不支持覆盖。manifest 不含
设备地址、当前时间或本机绝对路径；C8 和 CA 明确记录为 `not_implemented`。所有 C9 均复用
现有 `build_c9()`、`parse_c9()` 与 checksum 实现。此能力不构成静态真机上传，也不接受
`--device`、不初始化 Bleak、不读取 FF03、不写 FF02。

## Stage 5 BLE 命令

```powershell
python -m ultra3_uploader scan --timeout 10
python -m ultra3_uploader info --device "<扫描返回的准确设备ID>"
python -m ultra3_uploader listen --device "<准确设备ID>" --seconds 30 --log-file .\notifications.jsonl
python -m ultra3_uploader transport-self-test
```

多个同名 `ULTRA 3` 不会自动选择。GATT 通过 Service、FF02、FF03 的 UUID 定位，固定
ATT Handle 只属于历史证据，不作为连接依赖。后端无法报告最大无响应写入长度时显示
`unknown`；小于 237 字节时验证失败。

## Stage 6A：仅验证动态表盘准备握手

```powershell
python -m ultra3_uploader prepare-bcsdial --file "C:\path\watchface.bin" --dry-run
python -m ultra3_uploader prepare-bcsdial `
  --device "<准确设备ID>" `
  --file "C:\path\watchface.bin" `
  --ready-timeout 60 `
  --log-file .\stage6_prepare.jsonl
```

非 dry-run 模式只发送一个根据当前文件动态生成的 C8，随后验证 BC72 `30..0`、D1 ready
和匹配的 C8 response。成功后立即退订并断开；不发送 C9，也不发送 CA apply。

## Stage 6B：仅 Fake 完整上传模拟

```powershell
python -m ultra3_uploader simulate-upload-bcsdial `
  --file "C:\path\watchface.bin" `
  --packet-delay-ms 45 `
  --log-file .\stage6b_simulation.jsonl
```

模拟命令只创建 `FakeBleTransport`，不会导入或初始化真实 BLE 后端。每个 C9 串行发送，
完整 HEX 写入 JSONL；FakeSleeper 记录 45 ms 节奏但立即返回。

`upload-bcsdial` 的 dry-run 只校验本地文件，不创建日志或 BLE Transport：

```powershell
python -m ultra3_uploader upload-bcsdial --file "C:\path\watchface.bin" --dry-run
```

## Stage 6C-A：真实上传安全门（仅离线评审）

Fake 与 REAL Transport 共用同一个 `upload_bcsdial()` 状态机。REAL Transport 默认拒绝，
只有本地文件、显式确认、期望 SHA-256、严格 45 ms 包间隔和独占日志全部通过后才会创建
Transport；连接后还必须在 C8 前通过 Service/FF02/FF03、MTU >= 240 和最大无响应写入
长度 >= 237 的运行时检查。

真实模式没有 `--force`、自动重试或断点续传。任何失败都会停止后续 C9，不发送 CA apply，
并执行通知退订和安全断开。本阶段只完成代码和内存 Stub 测试，未执行任何非 dry-run 的
`upload-bcsdial` 命令；真机执行属于后续 Stage 6C-B。
