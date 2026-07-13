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

目标设备最终实机验证：

```text
Device: ULTRA 3
测试地址: 26:05:09:12:00:08
Service: 000001ff-3c17-d293-8e48-14fe2e4da212
FF02: 0000ff02-0000-1000-8000-00805f9b34fb / Write Without Response
FF03: 0000ff03-0000-1000-8000-00805f9b34fb / Notify
最大 Write Without Response: 244 字节
MTU: 247
FF03 订阅: 成功
30 秒通知数: 2
FF02 writes: 0
断开: 成功
```

`stage5_scan.jsonl` 保存的是此前目标设备未处于可发现状态时的一次失败扫描，不代表最终
实机验证结果。以上最终结果来自后续成功的 `scan → info → listen` 验证记录。

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

## 尚未确认的平台行为

- Linux 上 BlueZ 对最大无响应写入长度的报告行为。
- macOS 使用平台设备 UUID 时的同名设备选择与最大写入长度报告。
