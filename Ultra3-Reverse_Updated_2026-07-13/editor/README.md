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
python -m ultra3_editor reconstruct-c9 "<capture.log>" `
  --format auto `
  --container bcsdial `
  --output .\artifacts\reconstructed.bin `
  --json .\artifacts\reconstruction.json `
  --report .\artifacts\reconstruction.md

python -m ultra3_editor reconstruct-c9 "<static-diy-capture.log>" `
  --container greenlion-static `
  --output .\reconstructed.bin `
  --json .\reconstruction.json `
  --report .\reconstruction.md
```

报告使用独占创建，已存在时拒绝覆盖，不提供 `--force`。输入 BIN 始终只读。
`reconstruct-c9` 只提取 App→手表的 FF02 写入；C8/C9 checksum、原始 sequence、声明
包数与大小、BCSDIAL 头和 BCBC 尾必须全部通过。工具不会排序、去重、补零或修复抓包。

默认 `--container bcsdial` 继续强制 BCSDIAL/BCBC。`greenlion-static` 仅把头尾检查标记为
`NOT_REQUIRED`，其余 C8/C9/LEN/checksum/sequence/大小校验完全共用；所有 C9 DATA 原样
拼接，`transformation = none`，不会删除 `LEN=E8` 后的任何 DATA 字节。

## Ultra3 Lab 离线 GUI

Stage 8A 提供 PyQt6 深色只读 GUI 骨架：

```powershell
python -m pip install ".[gui]"
python -m ultra3_editor gui
```

当前源码中尚无 Stage 7B-1 `set_time_position()` 核心，因此 GUI 只允许打开、校验和
示意预览 351617 字节 GreenLion Static DIY BIN。目标位置、输出路径与生成按钮均被禁用；
GUI 不修改 BIN、不导入 uploader，也不提供 BLE、adb 或 Frida 功能。

静态 DIY 资源预览使用两个独立的已验证画布：主图 `320 × 384`、缩略图 `210 × 252`，
比例均为 `5:6`。它们是资源尺寸，不是物理屏幕分辨率；物理显示几何与可见区域均为
`UNKNOWN`。当前仓库没有 `Builder v0.2.4-greenlion-exact` 公共接口，因此图片导入、适配、
RGB565 编码、缩略图生成和 BIN 构建保持禁用。
