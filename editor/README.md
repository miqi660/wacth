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

python -m ultra3_editor set-time-position `
  --input "<351617 字节 GreenLion Static DIY BIN>" `
  --position bottom `
  --output .\edited.bin `
  --json .\edited.json `
  --report .\edited.md

python -m ultra3_editor build-static-diy `
  --image .\photo.png `
  --template .\official_calibration_351617.bin `
  --output .\watchface.bin `
  --json .\build.json `
  --report .\build.md
```

报告使用独占创建，已存在时拒绝覆盖，不提供 `--force`。输入 BIN 始终只读。
`reconstruct-c9` 只提取 App→手表的 FF02 写入；C8/C9 checksum、原始 sequence、声明
包数与大小、BCSDIAL 头和 BCBC 尾必须全部通过。工具不会排序、去重、补零或修复抓包。

默认 `--container bcsdial` 继续强制 BCSDIAL/BCBC。`greenlion-static` 仅把头尾检查标记为
`NOT_REQUIRED`，其余 C8/C9/LEN/checksum/sequence/大小校验完全共用；所有 C9 DATA 原样
拼接，`transformation = none`，不会删除 `LEN=E8` 后的任何 DATA 字节。

## Stage 7B-1：时间位置公共编辑核心

`set-time-position` 只接受严格小写的 `top` 或 `bottom`，并复用静态 DIY 检查器验证输入和
写后输出。当前已验证映射只有 offset `0x00000000` 的单字节 `00 = top`、`01 = bottom`；
其余 351616 字节必须逐字节不变。请求与输入位置相同时直接拒绝，不生成输出。

BIN、JSON 和 Markdown 均使用独占创建，任何目标已存在时拒绝覆盖。任一步写入或复验失败
都会删除本次调用已创建的文件，不删除输入或调用前已有文件。该核心是纯离线 API，不导入
uploader，不调用 BLE、adb、Frida 或 Builder。

## Stage 8B-1：GreenLion Static Builder 公共核心

`build-static-diy` 只开放冻结验证的 exact 路径：PNG/JPEG 输入、Pillow `10.4.0`、`cover`、
bilinear、truncate RGB565、`greenlion-next-high`，并从同一图片分别生成 `320 × 384` 主资源
和 `210 × 252` 缩略资源。调用者必须提供逐字节匹配的 351617 字节已验证模板；模板前 17
字节原样保留，offset 0 保持 `02`。

BIN、JSON 和 Markdown 均独占创建，任一失败会清理本次调用创建的文件。第一版不提供覆盖、
时间位置、独立缩略图、其他 fit 或编码配置，也不接入 GUI 和外部设备。

## Ultra3 Lab 离线 GUI

Stage 8A.2 提供 PyQt6 深色离线时间位置编辑 GUI：

```powershell
python -m pip install ".[gui]"
python -m ultra3_editor gui
```

GUI 通过 `OfflineGuiController` 调用 Stage 7B-1 `set_time_position()`，支持选择 Top/Bottom、
新输出路径及可选 JSON/Markdown，并展示写后复验和黄金匹配。GUI 不读取或 patch BIN 字节，
不覆盖输入或已有输出，不导入 uploader，也不提供 BLE、adb、Frida 或上传功能。

静态 DIY 资源预览使用两个独立的已验证画布：主图 `320 × 384`、缩略图 `210 × 252`，
比例均为 `5:6`。它们是资源尺寸，不是物理屏幕分辨率；物理显示几何与可见区域均为
`UNKNOWN`。Builder 公共核心尚未接入 GUI，因此图片导入、适配、RGB565 编码、缩略图生成
和完整表盘构建继续硬禁用；时间位置 BIN 编辑与资源制作在界面中明确区分。
