# Ultra3 Uploader v0.3.0 Stage 6A 结果

## 范围

本阶段只验证动态 `BCSDIAL` 的准备握手：发送一个 C8，接收 BC72 `30..0`、D1 ready
和匹配的 C8 response。没有发送 C9 或 CA apply，没有上传文件数据。

## 离线测试

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider
```

结果：

```text
59 passed
```

新增 Fake 场景覆盖：正常倒计时、D1、匹配 C8 response、BC72 缺失、倒计时乱序、
D1 超时、C8 response 超时、文件大小不匹配、包数不匹配、中途断开、用户取消、
退订与断开、唯一 C8、零 C9、零 CA，以及未知通知原样保留。

## dry-run

```text
文件大小: 891180
包数: 3875
C8 HEX: BCC80207012C990D00230F05
FF02 writes: 0
```

## 实机验证

设备：`ULTRA 3`  
测试地址：`26:05:09:12:00:08`

实际命令：

```powershell
python -m ultra3_uploader prepare-bcsdial `
  --device "26:05:09:12:00:08" `
  --file "<Frozen 黄金 BCSDIAL BIN>" `
  --ready-timeout 60 `
  --log-file ".\stage6_prepare.jsonl"
```

结果：

```text
[OK] C8 sent: BCC80207012C990D00230F05
[OK] BC72 countdown: 31 packets, 30..0
[OK] D1 ready
[OK] C8 response matched
[OK] FF02 writes: 1
[OK] C9 writes: 0
[OK] CA writes: 0
[OK] disconnected
```

JSONL 独立统计：

```text
总记录: 43
TX: 1
唯一 TX HEX: BCC80207012C990D00230F05
RX notifications: 33
BC72: 31，顺序 30,29,...,1,0
D1: 1
C8 response: 1
C9 TX: 0
CA TX: 0
COMPLETE: 1
```

日志：`stage6_prepare.jsonl`  
日志 SHA-256：`754EFD16E70760E8BF57CA6B687609BAFFEA309F9B5BC2643D3B6ADC092F330F`

## Frozen 复核

```text
Ultra3_v0.2.4_Frozen_Baseline_2026-07-11.zip
3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231

capture_light_v2.log
CD85A7AADDCC6BD85E108335DA0E0D63AF9FF24A88C5478F6E0BEA7E9CD6AE7F

168844266159401_jump13_to_4_reconstructed_from_ble.bin
7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D
```

哈希保持不变，Frozen 变化为 0。
