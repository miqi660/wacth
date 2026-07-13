# Ultra3 BCSDIAL Inspector / Diff Core

Stage 7A-1 提供纯离线、只读的 BCSDIAL 检查和逐字节差分工具。它不依赖 uploader、Bleak
或任何操作系统 BLE API，不包含 BIN 修改、GUI、上传、重试或字段猜测逻辑。

```powershell
cd .\editor
$env:PYTHONPATH='src'

python -m ultra3_editor inspect "<BCSDIAL文件>" --offset 0x16F --context 32
python -m ultra3_editor diff "<before.bin>" "<after.bin>" `
  --context 32 `
  --json .\artifacts\diff.json `
  --report .\diff.md
python -m ultra3_editor verify-known-patch "<before.bin>" "<after.bin>"
```

报告使用独占创建，已存在时拒绝覆盖，不提供 `--force`。输入 BIN 始终只读。
