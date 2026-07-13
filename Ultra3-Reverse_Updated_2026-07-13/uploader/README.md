# Ultra3 Uploader v0.3.0（Stage 1–5）

当前版本提供动态 `BCSDIAL` 离线协议工具，以及 Stage 5 的 BLE 扫描、GATT 检查和
FF03 安全监听。`scan`、`info`、`listen` 均不会调用 FF02 写入，不发送 C8、C9 或 CA，
也不实现静态图片表盘上传。

## 安装与测试

```powershell
cd .\Ultra3-Reverse_Updated_2026-07-13\uploader
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
