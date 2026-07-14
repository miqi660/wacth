# Stage 8C-0 Handoff 设计样例

本目录只保存规范化 Manifest 和离线审计结果，不复制 351617 字节 BIN，也不包含 payload 或 C9。

| 样例 | Golden 状态 | artifact SHA-256 |
|---|---|---|
| `golden_match.handoff.json` | `match` | `44B4893ACF6244119DE655B32C1CE760048F3128A24489B49FF24F7BB60FA664` |
| `custom_not_applicable.handoff.json` | `not_applicable` | `1D87836F3D985409F7787254B5ABFECAA81543D99082FAAC2FAC962B6ADBFC6C` |

两个 `artifact_path` 都是仓库相对路径，并由审计脚本以仓库根作为设计样例的 bundle root。
生产交接应优先把 `watchface.bin` 与 `watchface.handoff.json` 放在同一 Bundle 中。

验证结果：

- Schema：JSON Schema Draft 2020-12
- Schema/样例解析：通过
- 契约拒绝与安全测试：`51/51`
  - 原 Stage 8C-0 契约测试：20
  - 规范路径接受测试：4
  - 非规范/危险路径拒绝测试：19
  - SHA-256 大写格式测试：8
- 真实 artifact 大小/SHA/header/offset：通过
- 私人绝对路径扫描：`0`
- 设备地址与 Top/Bottom 字段扫描：`0 / 0`
- BLE/ADB/Frida/Uploader runtime/网络/真实上传：`0`

重新审计：

```powershell
python .\editor\scripts\audit_stage8c0_handoff.py
```

重新生成检查由脚本把当前样例与 Stage 8B-2 Builder JSON 的规范化结果逐字段比较；不会覆盖样例。
