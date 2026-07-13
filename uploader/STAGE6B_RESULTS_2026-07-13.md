# Ultra3 Uploader v0.3.0 Stage 6B 结果

## 范围与安全边界

本阶段只实现动态 `BCSDIAL` 完整上传的 Fake 驱动、异常测试、进度和 JSONL 日志。
没有执行真实 BLE 扫描、连接、准备或上传。`upload_bcsdial()` 在代码层拒绝任何非
`FakeBleTransport`，`upload-bcsdial` 非 dry-run 命令保持禁用。

## 新增和修改文件

| 文件 | 职责 |
|---|---|
| `src/ultra3_uploader/upload_bcsdial.py` | 串行 C9、CA success/apply 和统一结果状态机 |
| `src/ultra3_uploader/upload_progress.py` | 不可变上传进度与速率/ETA 计算 |
| `src/ultra3_uploader/timing.py` | Real/Fake Sleeper 与可注入单调时钟 |
| `src/ultra3_uploader/upload_result.py` | 保留 COMPLETE/FAILED/CANCELLED 的最终结果 |
| `src/ultra3_uploader/prepare_bcsdial.py` | 抽取 Stage 6A 公共准备会话和统一清理 |
| `src/ultra3_uploader/fake_transport.py` | 自动准备、CA、失败、断开、取消和未知通知模拟 |
| `src/ultra3_uploader/upload_state.py` | 增加 SENDING_C9、CA 等完整上传状态 |
| `src/ultra3_uploader/cli.py` | Fake 模拟命令和真实上传硬锁 |
| `src/ultra3_uploader/constants.py` | 已确认 CA success/apply 常量 |
| `src/ultra3_uploader/errors.py` | 上传安全、取消和 CA 协议异常 |
| `tests/test_upload_bcsdial_success.py` | 黄金 3875 包完整成功回归 |
| `tests/test_upload_bcsdial_failures.py` | 准备、写入、容量、断开和取消失败路径 |
| `tests/test_upload_bcsdial_ca.py` | CA 超时、早到、重复、延迟和 apply 失败 |
| `tests/test_upload_progress.py` | 文件字节进度、速率和 100% |
| `tests/test_upload_timing.py` | FakeSleeper 调用与模拟时间 |
| `tests/test_simulate_upload_cli.py` | Fake-only CLI、覆盖保护和真实上传锁 |

没有修改原有 59 项测试、C8/C9 算法、checksum、文件验证或 capture exact-match。

## 完整测试

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider
```

结果：

```text
90 passed in 0.46s
```

新增 31 项测试。异常路径覆盖：

- BC72 缺失/乱序、D1/C8 response 超时、大小/包数不匹配。
- 准备阶段断开与任务取消，且 C9/CA 均为 0。
- C9 第一包、中间包、最后一包失败，失败后不继续。
- 指定序号断开、显式取消、最大长度 236/237/unknown。
- CA success 缺失、早到、重复、延迟，CA apply 写入失败。
- C9 期间插入 0x48 和其他 UNKNOWN，不改变序号或状态。
- 所有仍连接的失败路径均退订 FF03 并安全断开。

## 黄金 Fake 模拟

```powershell
python -m ultra3_uploader simulate-upload-bcsdial `
  --file "<Frozen 黄金 BCSDIAL BIN>" `
  --packet-delay-ms 45 `
  --log-file ".\stage6b_simulation.jsonl"
```

CLI 结果：

```text
[OK] final state: COMPLETE
C8 writes: 1
C9 writes: 3875
CA writes: 1
total FF02 writes: 3877
packets sent: 3875/3875
bytes sent: 891180/891180
FakeSleeper calls: 3874
simulated delay seconds: 174.330
real BLE connections: 0
```

## JSONL 独立分析

```text
记录总数: 4101
TX 总数: 3877
C8: 1
C9: 3875
CA apply: 1
第一 C9: sequence 0，帧长 237
最后 C9: sequence 3874，DATA 160，帧长 167
序号: 0..3874 连续
checksum: 3875/3875
BCSDIAL 文件字节: 891180
C9 wire bytes: 918305
FF02 总 wire bytes: 918323
重组 SHA-256: 7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D
重组等于输入: true
CA success record index: 4094
CA apply record index: 4096
CA success before apply: true
CA apply 次数: 1
notify_disabled: 1
disconnected: 1
最终状态: COMPLETE
```

日志：`stage6b_simulation.jsonl`  
大小：`2952291` 字节  
SHA-256：`910198DB1AC2C7AE8EF14B82F230CCE0B32DA337E290EBD95C87415B4DDAF877`

## 真实 BLE 使用统计

```text
BleakTransport 初始化: 0
真实 BLE scan: 0
真实 BLE connect: 0
真实 FF02 writes: 0
```

Fake transport 内部连接只属于内存模拟，不对应任何系统 BLE API。

## Frozen 哈希复核

```text
Ultra3_v0.2.4_Frozen_Baseline_2026-07-11.zip
3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231

capture_light_v2.log
CD85A7AADDCC6BD85E108335DA0E0D63AF9FF24A88C5478F6E0BEA7E9CD6AE7F

168844266159401_jump13_to_4_reconstructed_from_ble.bin
7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D
```

Frozen 变化为 0，Stage 6A 的 `stage6_prepare.jsonl` 未修改。

## 尚未确认的协议行为

- 真机连续 3875 包时 45 ms 是否在所有环境稳定。
- C9 是否存在未观察到的逐包确认、重传或流控。
- 数据阶段断线后的设备内部状态和重新准备要求。
- 真机重复、延迟或异常 CA success 的行为。
- Windows 之外平台的持续高频 Write Without Response 行为。

## Stage 6C 前置条件

1. 明确授权一次完整真机上传及使用的输入 SHA-256。
2. 保持默认 45 ms 串行发送，不引入并发或自动提速。
3. 确认目标设备 ID、244 字节最大无响应写入长度和 247 MTU 未变化。
4. 预先保存日志路径，确认无同名文件被覆盖。
5. 明确失败后从 C8/sequence 0 重启，不实现断点续传。
6. 单独代码评审并显式解除 Stage 6B 的真实上传硬锁。
