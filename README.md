# Ultra3 Reverse Engineering

本仓库保存 Ultra3 表盘协议研究证据、离线编辑器和上传工具。项目已采用根目录扁平结构：

- `archives/`：冻结归档及其校验文件；
- `editor/`：Ultra3 Watchface Editor、离线分析工具、测试与样本；
- `uploader/`：Ultra3 Uploader、协议实现、测试与阶段报告。

## 当前验证范围

- Watch：ULTRA 3
- Firmware：NJ-LEJ-2.1.7
- Container：GreenLion Static DIY，351617 字节
- Main resource：320 × 384
- Thumbnail resource：210 × 252
- Time position：offset `0x00000000`，`00` = top，`01` = bottom

## 当前状态

- Stage 8A.1 Offline Read-only GUI：完成
- Stage 7B-1 time-position editing core：待实现
- Independent Uploader real upload：已验证

当前结论只适用于上述设备、固件和已验证样本，不代表支持所有 Ultra3、所有固件或通用表盘编辑。时间颜色、日期、星期、步数、卡路里、心率及 GUI 上传均未完成。

## 运行测试

Editor：

```powershell
cd .\editor
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q -p no:cacheprovider
```

Uploader：

```powershell
cd .\uploader
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider
```

`archives/`、抓包、BIN、JSONL、样本和阶段报告均属于可追溯证据。除非对应阶段明确授权，不应覆盖或重写这些文件。
