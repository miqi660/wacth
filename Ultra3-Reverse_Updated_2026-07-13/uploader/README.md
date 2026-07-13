# Ultra3 Uploader v0.3.0（Stage 1–4）

当前版本只提供动态 `BCSDIAL` 离线检查、协议包生成和 Frozen Frida 抓包逐包回归。
不会扫描、连接或写入手表，也不实现静态图片表盘上传。

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

