# Ultra3 Uploader v0.3.0 Stage 5 结果

## 离线验收

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider
python -m ultra3_uploader transport-self-test
```

结果：

```text
47 passed
[OK] fake scan/connect/GATT/notify/disconnect
[OK] FF02 writes: 0
```

原 Stage 1–4 的 20 项测试全部保留且继续通过。

## 实机安全检查

运行环境：

```text
Bleak 3.0.2
Windows release=10 build=22631
```

实际命令：

```powershell
python -m ultra3_uploader scan --timeout 10 --log-file .\stage5_scan.jsonl
```

结果：发现 2 个附近 BLE 设备，但 `ULTRA 3` 匹配数为 0，命令按设计返回非零退出码。
因此未执行 `info` 和 `listen`，没有连接任何设备，也没有产生 FF02 写入。原始结构化事件见
`stage5_scan.jsonl`。

## Frozen 哈希复核

```text
Ultra3_v0.2.4_Frozen_Baseline_2026-07-11.zip
3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231

capture_light_v2.log
CD85A7AADDCC6BD85E108335DA0E0D63AF9FF24A88C5478F6E0BEA7E9CD6AE7F

168844266159401_jump13_to_4_reconstructed_from_ble.bin
7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D
```

哈希与 Stage 1–4 验收值一致，Frozen 变化为 0。

## 待实机确认

- 目标设备的准确 Windows 设备 ID。
- Service、FF02、FF03 的本机 Bleak 枚举结果。
- 后端报告的最大 Write Without Response 长度和 MTU。
- FF03 实机订阅与通知接收。

在扫描明确发现目标设备前，不执行后续实机步骤。
