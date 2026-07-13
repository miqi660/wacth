# Ultra3 Uploader v0.3.0 Stage 6C-A 安全解锁离线评审

## 1. 范围与结论

本阶段只实现真实 BLE 上传安全门并进行离线评审。没有扫描或连接真实设备，没有初始化
`BleakClient`，没有执行真实 C8、C9 或 CA apply，也没有进入 Stage 6C-B。

验收结论：本地授权、原子日志、运行时 GATT/MTU/写入长度 preflight 均已接入唯一的
`upload_bcsdial()` 状态机。只有全部检查通过后才可能写入第一笔 C8；Fake 与 REAL Stub
仍共用 Stage 6A 准备会话、Stage 6B 串行 C9、CA success/apply、进度和清理逻辑。

## 2. 新增与修改文件

| 文件 | 职责 |
|---|---|
| `src/ultra3_uploader/real_upload.py` | 不可变授权模型、本地 SHA/45 ms 授权、日志独占创建、运行时能力检查 |
| `src/ultra3_uploader/errors.py` | 真实授权、SHA、MTU、写入长度、日志和 Transport 明确异常 |
| `src/ultra3_uploader/ble_transport.py` | 增加 `TransportKind.FAKE/REAL` 和 Protocol `kind` 属性 |
| `src/ultra3_uploader/fake_transport.py` | 明确返回 `TransportKind.FAKE` |
| `src/ultra3_uploader/bleak_transport.py` | 明确返回 `TransportKind.REAL`；未改变连接实现，未在本阶段实例化 |
| `src/ultra3_uploader/stage5.py` | 允许公共准备会话把容量检查延后到 REAL runtime preflight，默认行为不变 |
| `src/ultra3_uploader/prepare_bcsdial.py` | 在 FF03 订阅后、C8 前增加可注入 `runtime_preflight` |
| `src/ultra3_uploader/upload_bcsdial.py` | 以 `TransportKind` 分流安全门，仍保留唯一 C9 循环和统一清理 |
| `src/ultra3_uploader/cli.py` | 增加真实授权参数、dry-run 输出、日志独占后才创建真实 Transport |
| `README.md` | 记录 Stage 6C-A 安全边界和 dry-run 用法 |
| `tests/real_transport_stub.py` | kind 为 REAL、全部操作仅在内存中的测试 Transport |
| `tests/test_real_upload_authorization.py` | 本地授权、SHA、45 ms、日志绑定和零连接测试 |
| `tests/test_real_upload_preflight.py` | GATT、MTU、最大写入长度失败及边界值测试 |
| `tests/test_real_upload_state_machine.py` | REAL Stub 黄金完整上传及失败/取消/0x48/清理回归 |
| `tests/test_real_upload_cli.py` | CLI 工厂调用次数、日志冲突和 dry-run 零副作用测试 |
| `tests/__init__.py` | 供离线测试共享 REAL Stub |

现有测试文件、Frozen 文件、C8/C9/checksum 算法和协议证据均未修改。

## 3. 代码安全链

真实 CLI 入口执行顺序：

1. 读取文件并由 `BCSDIALPayload` 检查非空、`BCSDIAL` 头和 `BCBC` 尾。
2. 计算实际 SHA-256。
3. 检查 `--confirm-real-upload`。
4. 检查 `--expected-sha256` 存在且为 64 位十六进制。
5. 使用 `hmac.compare_digest()` 不区分大小写比较实际与期望 SHA-256。
6. 强制 `--packet-delay-ms` 严格为 45；授权对象不能降低该值。
7. 检查设备、日志和 timeout 参数。
8. 使用 `Path.open("x")` 原子独占创建日志；不存在 `--force`。
9. 以上通过后才调用真实 Transport 工厂并连接。
10. 通过 UUID 验证 Service、FF02 Write Without Response 和 FF03 Notify。
11. 订阅 FF03。
12. 在 C8 前验证 MTU 已知且 >= 240、最大无响应写入已知且 >= 237；授权对象只能提高门槛，不能降低。
13. 全部通过后才进入原 Stage 6A 准备会话并写入一个 C8。
14. 后续继续使用原 Stage 6B 串行 C9 和 CA 状态机。

运行时 preflight 抛错时，公共准备会话执行原有清理：已订阅时停止 FF03，仍连接时安全
断开。C8、C9、CA 写入均为 0。

## 4. 离线测试结果

执行：

```powershell
$env:PYTHONPATH='src'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider
```

结果：`126 passed`；带可见计时的等价运行结果为 `126 passed in 1.48s`。

- 原有 90 项测试全部保留且继续通过。
- 新增 36 项安全与 REAL Stub 离线测试。
- 测试未创建 `BleakClient`、未调用 `BleakScanner`、未访问 Windows BLE API。

### 本地授权与日志结果

| 场景 | Transport factory | connect | FF02 writes |
|---|---:|---:|---:|
| 缺少 `--confirm-real-upload` | 0 | 0 | 0 |
| 缺少 `--expected-sha256` | 0 | 0 | 0 |
| SHA 格式非法 | 0 | 0 | 0 |
| SHA 不匹配 | 0 | 0 | 0 |
| packet delay 不为 45 ms | 0 | 0 | 0 |
| 日志已存在 | 0 | 0 | 0 |

相同 SHA 的大小写不同形式通过授权。日志冲突保持原文件内容不变。

### 运行时 preflight 结果

Service 缺失、FF02 缺失、FF02 不支持 Write Without Response、FF03 缺失、FF03 不支持
Notify、MTU unknown、MTU 239、最大写入 unknown、最大写入 236 均满足：连接 1 次、FF02
写入 0、安全断开。MTU 240、最大写入 237 和实测边界 247/244 均允许进入准备流程。

### REAL Stub 正常与异常路径

黄金完整上传：

```text
final state: COMPLETE
C8 writes: 1
C9 writes: 3875
CA apply writes: 1
FF02 total writes: 3877
sequence: 0..3874
file bytes: 891180
packet delay sleeps: 3874 x 45 ms
notify stop: 1
disconnect: 1
```

写入顺序保持为：动态 C8 → C9 sequence `0..3874` → 收到 CA success → 单次 CA apply。
CA success 日志记录严格早于 CA apply。CA success 超时、中途 C9 失败、中途断开、用户
取消和 CA apply 写入失败均不会继续后续发送或重复 apply。0x48 周期通知完整记录，不改变
状态和 sequence。

### Fake Transport 回归

原黄金 Fake 回归继续通过：C8 = 1、C9 = 3875、CA apply = 1、FF02 总写入 = 3877，
重组文件等于输入。Fake 和 REAL Stub 走同一个 `upload_bcsdial()`；没有第二套 C9 循环。

## 5. 重试、续传与节奏检查

- 自动重试：不存在。
- 自动重连：不存在。
- 断点续传：不存在。
- 失败后 resume/start sequence：不存在；再次人工运行必须从 C8 和 sequence 0 开始。
- C9：每次只 `await` 一个 `write_without_response()`，未使用并发批量发送。
- packet delay：首次真实上传严格固定 45 ms。
- 最后一包后：不额外 sleep。
- C8 与第一 C9 之间：未增加固定延时。

`prepare_bcsdial.py` 中已有的 `create_task/gather` 只用于同时等待“下一条通知”和“断开
事件”，不是发送循环，也没有并发 BLE 写入。

## 6. 黄金 dry-run

本阶段实际执行的唯一 `upload-bcsdial` 命令带 `--dry-run`。结果：

```text
[OK] BCSDIAL header
[OK] BCBC footer
[OK] file size: 891180
[OK] SHA-256: 7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D
[OK] packet count: 3875
[OK] C8: BCC80207012C990D00230F05
[OK] real BLE connections: 0
[OK] FF02 writes: 0
```

dry-run 未创建日志，未创建 Transport，未扫描、连接或写入。

## 7. 真实 BLE 使用统计

```text
BleakTransport 实际初始化：0
真实 scan：0
真实 connect：0
真实 FF02 writes：0
```

所有 REAL 路径测试均使用内存 `RealTransportStub`。设备地址没有写入 `constants.py`，
也没有自动选择设备。

## 8. Frozen 与证据哈希复核

```text
Ultra3_v0.2.4_Frozen_Baseline_2026-07-11.zip
3581B0FA3D8E0B4BB952848CC45492B157DFFF4B125D57C93611FC89BF711231

capture_light_v2.log
CD85A7AADDCC6BD85E108335DA0E0D63AF9FF24A88C5478F6E0BEA7E9CD6AE7F

168844266159401_jump13_to_4_reconstructed_from_ble.bin
7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D

stage6_prepare.jsonl
754EFD16E70760E8BF57CA6B687609BAFFEA309F9B5BC2643D3B6ADC092F330F

stage6b_simulation.jsonl
910198DB1AC2C7AE8EF14B82F230CCE0B32DA337E290EBD95C87415B4DDAF877
```

五项均与预期一致。Frozen changes = 0。

## 9. 未来 Stage 6C-B 命令

以下命令只生成供后续人工评审，**NOT EXECUTED**：

```powershell
python -m ultra3_uploader upload-bcsdial `
  --device "26:05:09:12:00:08" `
  --file "<黄金BIN完整路径>" `
  --packet-delay-ms 45 `
  --ready-timeout 60 `
  --ca-timeout 30 `
  --expected-sha256 "7B25A833D431ED29622EDF4C102F4B555F1E251D1CEC842D848E8E7DCE2C015D" `
  --confirm-real-upload `
  --log-file ".\stage6c_real_upload_2026-07-13.jsonl"
```

状态：**NOT EXECUTED**。本阶段没有进入 Stage 6C-B。

## 10. 尚未确认的真实行为

REAL Stub 只能证明授权顺序、状态机、写入顺序和清理逻辑。尚未确认真实 Windows/Bleak
环境下连续 3875 个 Write Without Response、约 174.33 秒持续 45 ms 节奏时的控制器缓存、
系统调度、设备流控和长时间稳定性；这些只能在后续单独授权的 Stage 6C-B 中验证。
